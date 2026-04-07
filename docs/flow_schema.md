# Flow Schema and Processing Protocol

> Version: 1.0
> Frozen: 2026-03-23
> Applies to: CIC-IDS2017 (and will be extended uniformly to CSE-CIC-IDS2018, UNSW-NB15)

---

## 1. Canonical Bidirectional 5-Tuple

A flow is identified by a **direction-agnostic canonical 5-tuple**:

| Field | Source column | Notes |
|-------|--------------|-------|
| `src_ip` | smaller of the two IP addresses | lexicographic ordering |
| `src_port` | port paired with the smaller IP | |
| `dst_ip` | larger of the two IP addresses | |
| `dst_port` | port paired with the larger IP | |
| `protocol` | IP protocol number (6=TCP, 17=UDP) | |

The canonical key is computed as:

```python
a = (src_ip, src_port)
b = (dst_ip, dst_port)
if a <= b:
    key = (a[0], a[1], b[0], b[1], protocol)
else:
    key = (b[0], b[1], a[0], a[1], protocol)
```

Both forward (A→B) and backward (B→A) packets belong to the same flow.
Only IPv4 packets with TCP or UDP transport are accepted; all others are discarded and counted.

---

## 2. Packet Filtering Rules

| Rule | Action |
|------|--------|
| No IPv4 layer | Discard (counted as `skipped_no_ip`) |
| IPv4 but no TCP/UDP | Discard (counted as `skipped_no_transport`) |
| IPv4 + TCP | Accept (protocol = 6) |
| IPv4 + UDP | Accept (protocol = 17) |

---

## 3. Flow Aggregation (Timeouts)

Parameters from `configs/feature_config.yaml`:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `active_timeout` | 120 s | A flow is split if its total duration exceeds this |
| `idle_timeout` | 60 s | A flow is split if there is a gap larger than this between packets |

When a timeout triggers, the current flow is finalized and a new flow is opened for the same 5-tuple.

---

## 4. Flow Table Schema (Intermediate / Labeled)

Output of `src/data_ingestion/pcap_to_flows.py` followed by `src/labeling/flow_label_aligner.py`.

### Core flow columns

| Column | Type | Description |
|--------|------|-------------|
| `flow_id` | int | Sequential ID within a single PCAP extraction run |
| `pcap_file` | str | Filename of the source PCAP |
| `start_time` | float | Unix timestamp of the first packet |
| `end_time` | float | Unix timestamp of the last packet (`= last_time`) |
| `duration_s` | float | `end_time - start_time` (seconds) |
| `protocol` | int | 6 = TCP, 17 = UDP |
| `src_ip` | str | Canonical source IP (smaller side) |
| `src_port` | int | Canonical source port |
| `dst_ip` | str | Canonical destination IP (larger side) |
| `dst_port` | int | Canonical destination port |
| `packet_count_total` | int | Total packets (both directions) |
| `bytes_total` | int | Total bytes (both directions, IP header included) |
| `packet_count_fwd` | int | Packets in the forward direction |
| `packet_count_bwd` | int | Packets in the backward direction |
| `bytes_fwd` | int | Bytes in the forward direction |
| `bytes_bwd` | int | Bytes in the backward direction |

### Label alignment columns (added by aligner)

| Column | Type | Description |
|--------|------|-------------|
| `matched_flag` | bool | True if a clean (unambiguous) label was found |
| `ambiguous_flag` | bool | True if the canonical key maps to conflicting labels in the reference CSV |
| `label_match_method` | str | `canonical_5tuple` / `ambiguous_canonical_5tuple` / `unmatched` / `no_key` |
| `original_label` | str \| None | Raw label string from the reference CSV |
| `binary_label` | str \| None | `benign` or `attack` (from label_mapping_master.csv) |
| `coarse_family` | str \| None | Coarse attack family (e.g., `dos_ddos`, `brute_force`) |

---

## 5. Feature Table Schema

Output of `src/features/extract_flow_features.py`.
Metadata columns are preserved; feature columns are numeric only.
**No normalization is applied at this stage** — normalization is fitted on the training split only.

### Feature columns (19 total)

| # | Column | Description |
|---|--------|-------------|
| 1 | `duration_s` | Flow duration in seconds |
| 2 | `packet_count_total` | Total packets |
| 3 | `bytes_total` | Total bytes |
| 4 | `packet_count_fwd` | Forward packet count |
| 5 | `packet_count_bwd` | Backward packet count |
| 6 | `bytes_fwd` | Forward bytes |
| 7 | `bytes_bwd` | Backward bytes |
| 8 | `protocol` | Protocol number (6 or 17) |
| 9 | `is_tcp` | 1 if TCP, else 0 |
| 10 | `is_udp` | 1 if UDP, else 0 |
| 11 | `bytes_per_packet` | `bytes_total / packet_count_total` |
| 12 | `bytes_per_packet_fwd` | `bytes_fwd / packet_count_fwd` |
| 13 | `bytes_per_packet_bwd` | `bytes_bwd / packet_count_bwd` |
| 14 | `packets_per_second` | `packet_count_total / duration_s` |
| 15 | `bytes_per_second` | `bytes_total / duration_s` |
| 16 | `fwd_packet_ratio` | `packet_count_fwd / packet_count_total` |
| 17 | `bwd_packet_ratio` | `packet_count_bwd / packet_count_total` |
| 18 | `fwd_byte_ratio` | `bytes_fwd / bytes_total` |
| 19 | `bwd_byte_ratio` | `bytes_bwd / bytes_total` |

Division-by-zero → `0.0` (safe division, no inf/NaN in feature columns).

---

## 6. Label Mapping Hierarchy

Three tiers, defined in `data/external/label_mapping_master.csv`:

| Tier | Column | Example values |
|------|--------|---------------|
| Raw | `original_label` | `BENIGN`, `DoS Hulk`, `Web Attack – Brute Force` |
| Binary | `binary_label` | `benign`, `attack` |
| Coarse | `coarse_family` | `dos_ddos`, `brute_force`, `web_attack`, `botnet_malware`, `infiltration`, `port_scan` |

The `coarse_family` is `None`/empty for benign flows.

---

## 7. Label–Flow Join Method

**Method:** canonical bidirectional 5-tuple exact match against the reference CSV.

**Inputs:**
- Flow table (from PCAP extraction)
- Label reference CSV(s) (from public CIC dataset, used only as label reference)

**Outcome categories:**

| Outcome | `matched_flag` | `ambiguous_flag` | Included in master table? |
|---------|---------------|-----------------|--------------------------|
| Clean match | True | False | YES |
| Ambiguous key | False | True | NO — logged in ambiguous_log |
| No match in CSV | False | False | NO — logged in exclusion_log |
| Parse error (no key) | False | False | NO — logged in exclusion_log |

**Ambiguity definition:** a canonical key that appears in the label reference CSV mapped to more than one distinct label (e.g., the same 5-tuple is labeled both `BENIGN` and `DoS Hulk` across different rows — this occurs in CIC-IDS2017 Wednesday due to DoS Hulk reusing TCP connections).

**Time-window disambiguation:** NOT currently implemented. All ambiguous flows are excluded and logged. This is a documented limitation; future work may refine this.

---

## 8. Output Directory Structure

```
D:/ids_project_data/
├── cicids2017/
│   ├── pcap/           # raw PCAP (read-only input)
│   └── label_ref/      # label reference CSVs (read-only, not training input)
├── interim/
│   └── cicids2017/
│       ├── {day}_flows.parquet          # raw extracted flows (no labels)
│       └── {day}_flows_labeled.parquet  # flows + label columns
├── processed/
│   └── cicids2017/
│       ├── {day}_features.parquet       # ML-ready feature tables
│       └── cicids2017_flows_master.parquet  # merged master (matched only)
└── logs/
    └── cicids2017/
        └── {day}/
            ├── parse_log.json
            ├── ambiguous_log.csv
            ├── exclusion_log.csv
            └── summary_stats.json
```

`{day}` values: `monday`, `tuesday`, `wednesday`, `thursday`, `friday`

---

## 9. Flow ID Uniqueness

`flow_id` is sequential within a single PCAP extraction run and is NOT globally unique across days. The master table uses a composite unique identifier: `(pcap_file, flow_id)`. The master table also adds a global `global_flow_id` column.

---

## 10. Known Limitations

1. **Wednesday ambiguous flows (~31%):** DoS Hulk reuses TCP 5-tuples shared with benign flows. Without time-window disambiguation, these are excluded from training. The count is logged.
2. **ICMP and non-TCP/UDP traffic:** Discarded at parse time. Not relevant for the current feature set.
3. **flow_id is not stable across re-runs:** If the PCAP is re-extracted, flow_id values may differ. The stable identifier is the canonical 5-tuple + start_time.
4. **Label CSV encoding:** CIC-IDS2017 CSVs may use cp1252 encoding; the loader applies latin-1 fallback and normalizes en-dash characters in Web Attack labels.
