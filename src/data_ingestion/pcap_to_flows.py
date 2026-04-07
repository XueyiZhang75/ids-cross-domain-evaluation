"""
pcap_to_flows.py — Raw PCAP -> bidirectional flow table.

Pipeline position:
    raw PCAP  ->  [this module]  ->  interim flow CSV/Parquet

Two engines available:
  - legacy (default): loads all packets into memory, then builds flows.
    Works for PCAPs up to ~1-2 GB before MemoryError.
  - streaming_v2: processes packets inline with bounded memory, flushes
    finished flows to disk in chunks. Handles PCAPs of any size.
    Added in Phase 0.6.2c to support large IoT-23 scenarios (52-1, 60-1).
"""

from pathlib import Path
from typing import Any
import tempfile

import pandas as pd
from scapy.utils import PcapReader
from scapy.layers.inet import IP, TCP, UDP

from src.utils.io_utils import ensure_dir, save_csv, save_parquet
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


# ── Public API ──────────────────────────────────────────────────────────────

def run_streaming(
    pcap_path: str | Path,
    output_path: str | Path,
    config: dict,
    chunk_size: int = 500_000,
    active_flow_guard: int = 5_000_000,
) -> Path:
    """Streaming_v2 engine: bounded-memory PCAP -> flow table.

    Processes packets inline without accumulating all packet records in RAM.
    Finishes flows are written to parquet chunks, then merged.

    Parameters
    ----------
    pcap_path : path
        Single .pcap file.
    output_path : path
        Destination parquet file.
    config : dict
        Same config dict as run().
    chunk_size : int
        Flush finished flows to a chunk parquet every this many rows.
    active_flow_guard : int
        If active flow map exceeds this size, force-idle-flush oldest flows.

    Semantics preserved vs legacy:
    - Same canonical bidirectional 5-tuple key
    - Same active_timeout / idle_timeout from config
    - Same output schema (16 columns matching legacy)
    """
    pcap_path = Path(pcap_path)
    output_path = Path(output_path)
    ensure_dir(output_path.parent)

    flow_cfg = config.get("flow", {})
    active_timeout = flow_cfg.get("active_timeout", 120)
    idle_timeout   = flow_cfg.get("idle_timeout", 60)
    pcap_filename  = pcap_path.name

    logger.info(
        "[streaming_v2] %s | active_timeout=%ss idle_timeout=%ss chunk=%d",
        pcap_filename, active_timeout, idle_timeout, chunk_size,
    )

    active: dict[tuple, dict] = {}
    pending: list[dict] = []
    chunk_paths: list[Path] = []
    flow_counter = 0
    total_pkts = 0
    accepted_pkts = 0
    filtered_pkts = 0

    tmp_dir = output_path.parent / "_streaming_chunks"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    def _flush_pending():
        nonlocal pending
        if not pending:
            return
        chunk_idx = len(chunk_paths)
        chunk_path = tmp_dir / f"chunk_{chunk_idx:06d}.parquet"
        chunk_df = _pending_to_df(pending, pcap_filename)
        chunk_df.to_parquet(chunk_path, index=False)
        chunk_paths.append(chunk_path)
        logger.info(
            "  [streaming_v2] flushed chunk %d (%d flows, total chunks=%d)",
            chunk_idx, len(pending), len(chunk_paths),
        )
        pending = []

    def _finish_flow(flow: dict):
        nonlocal flow_counter
        flow_counter += 1
        flow["flow_id"] = flow_counter
        pending.append(flow)
        if len(pending) >= chunk_size:
            _flush_pending()

    with PcapReader(str(pcap_path)) as reader:
        for pkt in reader:
            total_pkts += 1
            if total_pkts % 2_000_000 == 0:
                logger.info(
                    "  [streaming_v2] %dM pkts | active=%d flows | chunks=%d",
                    total_pkts // 1_000_000, len(active), len(chunk_paths),
                )

            if not pkt.haslayer(IP):
                filtered_pkts += 1
                continue
            ip = pkt[IP]
            if pkt.haslayer(TCP):
                transport = pkt[TCP]; proto = 6
            elif pkt.haslayer(UDP):
                transport = pkt[UDP]; proto = 17
            else:
                filtered_pkts += 1
                continue

            accepted_pkts += 1
            ts = float(pkt.time)
            ip_len = ip.len

            a = (ip.src, transport.sport)
            b = (ip.dst, transport.dport)
            key = (*min(a, b), *max(a, b), proto) if a <= b else (*b, *a, proto)
            fwd = (ip.src == key[0] and transport.sport == key[1])

            if key in active:
                flow = active[key]
                gap = ts - flow["last_time"]
                expired_idle   = gap > idle_timeout
                expired_active = (ts - flow["start_time"]) > active_timeout
                if expired_idle or expired_active:
                    _finish_flow(flow)
                    del active[key]
                    # Fall through to create new flow
                else:
                    flow["last_time"] = ts
                    flow["packet_count_total"] += 1
                    flow["bytes_total"] += ip_len
                    if fwd:
                        flow["packet_count_fwd"] += 1; flow["bytes_fwd"] += ip_len
                    else:
                        flow["packet_count_bwd"] += 1; flow["bytes_bwd"] += ip_len
                    continue

            # New flow
            active[key] = {
                "src_ip": key[0], "src_port": key[1],
                "dst_ip": key[2], "dst_port": key[3],
                "protocol": key[4],
                "start_time": ts, "last_time": ts,
                "packet_count_total": 1, "bytes_total": ip_len,
                "packet_count_fwd": 1 if fwd else 0, "bytes_fwd": ip_len if fwd else 0,
                "packet_count_bwd": 0 if fwd else 1, "bytes_bwd": 0 if fwd else ip_len,
            }

            # Active flow guard: idle-flush if map too large
            if len(active) > active_flow_guard:
                cutoff = ts - idle_timeout
                stale = [k for k, v in active.items() if v["last_time"] < cutoff]
                for k in stale:
                    _finish_flow(active.pop(k))

    # Flush remaining active flows
    for flow in active.values():
        _finish_flow(flow)
    _flush_pending()

    logger.info(
        "[streaming_v2] Done: %d pkts | %d accepted | %d filtered | %d flows | %d chunks",
        total_pkts, accepted_pkts, filtered_pkts, flow_counter, len(chunk_paths),
    )

    # Merge chunks
    if not chunk_paths:
        df = pd.DataFrame(columns=_flow_columns())
    else:
        logger.info("[streaming_v2] Merging %d chunks ...", len(chunk_paths))
        df = pd.concat([pd.read_parquet(p) for p in chunk_paths], ignore_index=True)
        for p in chunk_paths:
            p.unlink(missing_ok=True)
        try:
            tmp_dir.rmdir()
        except Exception:
            pass

    df.to_parquet(output_path, index=False)
    logger.info("[streaming_v2] Written -> %s (%d flows)", output_path, len(df))
    return output_path


def _flow_columns() -> list[str]:
    return [
        "flow_id", "pcap_file", "start_time", "end_time", "duration_s",
        "protocol", "src_ip", "src_port", "dst_ip", "dst_port",
        "packet_count_total", "bytes_total",
        "packet_count_fwd", "packet_count_bwd", "bytes_fwd", "bytes_bwd",
    ]


def _pending_to_df(pending: list[dict], pcap_filename: str) -> pd.DataFrame:
    """Convert pending flow dicts to DataFrame with correct schema."""
    df = pd.DataFrame(pending)
    df["pcap_file"] = pcap_filename
    df["end_time"]  = df["last_time"]
    df["duration_s"] = df["end_time"] - df["start_time"]
    df.drop(columns=["last_time"], inplace=True, errors="ignore")
    for col in _flow_columns():
        if col not in df.columns:
            df[col] = None
    return df[_flow_columns()]


def run(
    pcap_path: str | Path,
    output_path: str | Path,
    config: dict,
    max_packets: int | None = None,
    skip_packets: int = 0,
) -> Path:
    """End-to-end entry point: PCAP in -> flow table out.

    Parameters
    ----------
    pcap_path : path
        A single .pcap file or a directory of .pcap files.
    output_path : path
        Destination file for the exported flow table.
    config : dict
        Parsed contents of ``configs/feature_config.yaml``.
    max_packets : int, optional
        If set, stop reading after this many packets (per file).

    Returns
    -------
    Path
        The path to the written flow table.
    """
    pcap_path = Path(pcap_path)
    output_path = Path(output_path)

    # 1. Validate input
    pcap_files = _resolve_pcap_files(pcap_path)

    # 2. Load flow-definition settings
    flow_cfg = config.get("flow", {})
    logger.info(
        "Flow settings — key_fields: %s, active_timeout: %s s, idle_timeout: %s s",
        flow_cfg.get("key_fields"),
        flow_cfg.get("active_timeout"),
        flow_cfg.get("idle_timeout"),
    )

    # 3. Parse packets and build flows (per file, then concatenate)
    all_flows: list[pd.DataFrame] = []
    for pf in pcap_files:
        packets = parse_pcap(pf, max_packets=max_packets, skip_packets=skip_packets)
        flows = build_bidirectional_flows(packets, flow_cfg, pcap_filename=pf.name)
        logger.info("  %s -> %d flows", pf.name, len(flows))
        all_flows.append(flows)

    if not all_flows:
        logger.warning("No flows produced.")
        combined = pd.DataFrame()
    else:
        combined = pd.concat(all_flows, ignore_index=True)

    logger.info("Total flows: %d", len(combined))

    # 4. Export
    fmt = config.get("output", {}).get("format", "parquet")
    written = export_flows(combined, output_path, fmt=fmt)
    logger.info("Flow table written -> %s", written)
    return written


# ── Helpers ─────────────────────────────────────────────────────────────────

def _resolve_pcap_files(pcap_path: Path) -> list[Path]:
    """Return a list of PCAP files from a file or directory path."""
    if not pcap_path.exists():
        raise FileNotFoundError(f"PCAP path does not exist: {pcap_path}")

    if pcap_path.is_file():
        logger.info("Input is a single file: %s", pcap_path)
        return [pcap_path]

    if pcap_path.is_dir():
        pcaps = sorted(pcap_path.glob("*.pcap")) + sorted(pcap_path.glob("*.pcapng"))
        if not pcaps:
            raise FileNotFoundError(
                f"No .pcap / .pcapng files found in: {pcap_path}"
            )
        logger.info("Found %d PCAP file(s) in %s", len(pcaps), pcap_path)
        return pcaps

    raise ValueError(f"Unexpected path type: {pcap_path}")


# ── Step 1: Parse packets ──────────────────────────────────────────────────

def parse_pcap(
    pcap_file: Path,
    max_packets: int | None = None,
    skip_packets: int = 0,
) -> list[dict]:
    """Stream-read a single PCAP file and extract per-packet records.

    Only IPv4 packets with TCP or UDP transport are kept.
    Other packets are counted and skipped.

    Parameters
    ----------
    skip_packets : int
        Number of packets to skip at the start of the file before reading.

    Returns a list of dicts, one per accepted packet.
    """
    parts = []
    if skip_packets:
        parts.append(f"skip {skip_packets:,}")
    if max_packets:
        parts.append(f"max {max_packets:,}")
    suffix = f" ({', '.join(parts)})" if parts else ""
    logger.info("Parsing %s%s ...", pcap_file.name, suffix)

    records: list[dict] = []
    total_read = 0
    processed = 0
    skipped_no_ip = 0
    skipped_no_transport = 0

    with PcapReader(str(pcap_file)) as reader:
        for pkt in reader:
            total_read += 1

            # Skip phase.
            if total_read <= skip_packets:
                continue

            processed += 1
            if max_packets and processed > max_packets:
                break

            # Must have IPv4 layer.
            if not pkt.haslayer(IP):
                skipped_no_ip += 1
                continue

            ip = pkt[IP]

            # Must have TCP or UDP.
            if pkt.haslayer(TCP):
                transport = pkt[TCP]
                proto = 6
            elif pkt.haslayer(UDP):
                transport = pkt[UDP]
                proto = 17
            else:
                skipped_no_transport += 1
                continue

            records.append({
                "timestamp": float(pkt.time),
                "src_ip": ip.src,
                "dst_ip": ip.dst,
                "src_port": transport.sport,
                "dst_port": transport.dport,
                "protocol": proto,
                "ip_len": ip.len,
            })

    logger.info(
        "  Scanned %s packets (skipped first %s): %s processed, %s accepted, "
        "%s filtered (no IP: %s, no TCP/UDP: %s)",
        f"{total_read:,}", f"{skip_packets:,}", f"{processed:,}",
        f"{len(records):,}",
        f"{skipped_no_ip + skipped_no_transport:,}",
        f"{skipped_no_ip:,}", f"{skipped_no_transport:,}",
    )
    return records


# ── Step 2: Build bidirectional flows ───────────────────────────────────────

def _make_bidir_key(rec: dict) -> tuple:
    """Create a canonical bidirectional flow key from a packet record.

    The key is ordered so that (A->B) and (B->A) produce the same tuple.
    The smaller (ip, port) pair is always first.
    """
    a = (rec["src_ip"], rec["src_port"])
    b = (rec["dst_ip"], rec["dst_port"])
    proto = rec["protocol"]
    if a <= b:
        return (a[0], a[1], b[0], b[1], proto)
    else:
        return (b[0], b[1], a[0], a[1], proto)


def _is_forward(rec: dict, flow_key: tuple) -> bool:
    """True if this packet goes in the 'forward' direction of the flow."""
    return (rec["src_ip"] == flow_key[0] and rec["src_port"] == flow_key[1])


def build_bidirectional_flows(
    packets: list[dict],
    flow_cfg: dict,
    pcap_filename: str = "",
) -> pd.DataFrame:
    """Aggregate parsed packets into bidirectional flows.

    Uses active_timeout and idle_timeout from flow_cfg to split long-lived
    or idle connections into separate flows.

    Returns a DataFrame with one row per flow.
    """
    active_timeout = flow_cfg.get("active_timeout", 120)
    idle_timeout = flow_cfg.get("idle_timeout", 60)

    # Sort packets by timestamp.
    packets.sort(key=lambda r: r["timestamp"])

    # Active flow state: key -> list of flow accumulators.
    # Each accumulator is a dict tracking per-flow stats.
    active: dict[tuple, dict] = {}
    finished: list[dict] = []
    flow_counter = 0

    for rec in packets:
        key = _make_bidir_key(rec)
        ts = rec["timestamp"]
        ip_len = rec["ip_len"]
        fwd = _is_forward(rec, key)

        if key in active:
            flow = active[key]
            gap = ts - flow["last_time"]

            # Check idle timeout.
            if gap > idle_timeout:
                finished.append(flow)
                del active[key]
                # Fall through to create a new flow below.
            # Check active timeout.
            elif (ts - flow["start_time"]) > active_timeout:
                finished.append(flow)
                del active[key]
            else:
                # Update existing flow.
                flow["last_time"] = ts
                flow["packet_count_total"] += 1
                flow["bytes_total"] += ip_len
                if fwd:
                    flow["packet_count_fwd"] += 1
                    flow["bytes_fwd"] += ip_len
                else:
                    flow["packet_count_bwd"] += 1
                    flow["bytes_bwd"] += ip_len
                continue

        # Create new flow.
        flow_counter += 1
        new_flow = {
            "flow_id": flow_counter,
            "pcap_file": pcap_filename,
            "src_ip": key[0],
            "src_port": key[1],
            "dst_ip": key[2],
            "dst_port": key[3],
            "protocol": key[4],
            "start_time": ts,
            "last_time": ts,
            "packet_count_total": 1,
            "bytes_total": ip_len,
            "packet_count_fwd": 1 if fwd else 0,
            "bytes_fwd": ip_len if fwd else 0,
            "packet_count_bwd": 0 if fwd else 1,
            "bytes_bwd": 0 if fwd else ip_len,
        }
        active[key] = new_flow

    # Flush remaining active flows.
    for flow in active.values():
        finished.append(flow)

    if not finished:
        return pd.DataFrame()

    df = pd.DataFrame(finished)

    # Compute derived columns.
    df["end_time"] = df["last_time"]
    df["duration_s"] = df["end_time"] - df["start_time"]
    df.drop(columns=["last_time"], inplace=True)

    # Reorder columns.
    col_order = [
        "flow_id", "pcap_file", "start_time", "end_time", "duration_s",
        "protocol", "src_ip", "src_port", "dst_ip", "dst_port",
        "packet_count_total", "bytes_total",
        "packet_count_fwd", "packet_count_bwd", "bytes_fwd", "bytes_bwd",
    ]
    df = df[col_order]
    return df


# ── Step 3: Export ──────────────────────────────────────────────────────────

def export_flows(flows: pd.DataFrame, output_path: Path, fmt: str = "parquet") -> Path:
    """Write the flow table to disk."""
    ensure_dir(output_path.parent)
    if fmt == "parquet":
        return save_parquet(flows, output_path)
    elif fmt == "csv":
        return save_csv(flows, output_path)
    else:
        raise ValueError(f"Unsupported output format: {fmt!r}")
