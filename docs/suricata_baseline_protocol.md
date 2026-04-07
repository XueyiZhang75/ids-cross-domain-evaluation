# Suricata Baseline Protocol — CIC-IDS2017 Phase 3 Step 1

> Version: 1.0
> Frozen: 2026-03-23
> Applies to: CIC-IDS2017, Phase 3 first step (in-domain rule-based IDS baseline)

---

## 1. Scope

This document governs the Suricata offline PCAP scanning and alert-to-flow alignment
protocol for the CIC-IDS2017 in-domain baseline. It does **not** apply to:

- Cross-domain transfer experiments
- ML/DL model training
- Threshold portability analysis
- Any other dataset (CSE-CIC-IDS2018, UNSW-NB15)

---

## 2. Inputs

| Input | Path | Frozen |
|-------|------|--------|
| Raw PCAPs (5 days) | `D:/ids_project_data/cicids2017/pcap/{day}.pcap` | Phase 1 |
| Master feature table | `D:/ids_project_data/processed/cicids2017/cicids2017_flows_master.parquet` | Phase 1 |
| Split assignment | `D:/ids_project_data/processed/cicids2017/cicids2017_split_assignment.csv` | Phase 2 |
| Interim labeled flows (5 days) | `D:/ids_project_data/interim/cicids2017/{day}_flows_labeled.parquet` | Phase 1 |
| ET Open rules | `D:/ids_project_data/suricata/rules/cicids2017.rules` | Phase 3 |
| Suricata config | `D:/ids_project_data/suricata/config/suricata_offline.yaml` | Phase 3 |

The interim labeled parquets are used for alignment because they contain the canonical
5-tuple (src_ip, src_port, dst_ip, dst_port, protocol) and flow time window
(start_time, end_time) not present in the master feature table.

---

## 3. Environment

| Item | Value |
|------|-------|
| Suricata version | 7.0.10 |
| Install path | `C:/Program Files/Suricata/suricata.exe` |
| Install method | `winget install OISF.Suricata --silent` |
| Rules source | Emerging Threats Open (ET Open) |
| Rules URL | `https://rules.emergingthreats.net/open/suricata-7.0.10/emerging.rules.tar.gz` |
| Rules download date | 2026-03-23 |
| Combined rules file | `D:/ids_project_data/suricata/rules/cicids2017.rules` |
| Rules loaded | 48,713 (9 failed: `file.magic` keyword not supported in 7.0.10) |
| Network dependency | Npcap (pre-installed at `C:/Windows/System32/Npcap/`) |
| HOME_NET | `192.168.10.0/24` |
| EXTERNAL_NET | `!$HOME_NET` |

---

## 4. Offline Scan Method

Each PCAP day is scanned separately. The scan command template is:

```
C:\Program Files\Suricata\suricata.exe \
  -c D:/ids_project_data/suricata/config/suricata_offline.yaml \
  -r D:/ids_project_data/cicids2017/pcap/{PCAP_FILENAME} \
  -l D:\ids_project_data\suricata\cicids2017\{day} \
  -k none
```

Key flags:
- `-r`: offline PCAP replay mode (not live capture)
- `-l`: output log directory (must use Windows backslash separators on Windows)
- `-k none`: disable checksum verification (CIC-IDS2017 PCAPs have checksum offloading artifacts)
- Original PCAPs are never modified

Output per day (under `D:/ids_project_data/suricata/cicids2017/{day}/`):
- `eve.json`: JSON event log containing alert events (primary output)
- `suricata.log`: engine log with packet counts, error messages, timing

Script: `scripts/run_suricata_cicids2017.py`

---

## 5. Alert-to-Flow Alignment Protocol

This is the core of the Suricata baseline. Alerts from `eve.json` must be mapped
to flows in the master table to produce flow-level binary predictions.

### 5.1 Alert Extraction

From `eve.json`, extract only events with `event_type == "alert"`. For each alert:

| Field extracted | Source in eve.json |
|----------------|--------------------|
| `alert_time` | `timestamp` (parsed to Unix seconds) |
| `src_ip` | `src_ip` |
| `src_port` | `src_port` |
| `dst_ip` | `dest_ip` |
| `dst_port` | `dest_port` |
| `proto` | `proto` (TCP=6, UDP=17) |
| `signature` | `alert.signature` |
| `sid` | `alert.signature_id` |
| `category` | `alert.category` |
| `severity` | `alert.severity` |

### 5.2 Canonical 5-Tuple Normalization

Each alert is normalized to a canonical bidirectional 5-tuple consistent with
the master table convention:

```
canon_src_ip   = min(src_ip, dst_ip)
canon_dst_ip   = max(src_ip, dst_ip)
canon_src_port = port corresponding to min IP
canon_dst_port = port corresponding to max IP
canon_proto    = protocol number (TCP=6, UDP=17)
```

The string comparison on IP addresses uses Python's default string comparison
of dotted-decimal IP strings, which matches the canonical key construction in
`src/labeling/flow_label_aligner.py`.

### 5.3 PCAP Timestamp Correction

The CIC-IDS2017 capture files are in pcapng format and contain an `if_tsoffset = 7200` in
the Interface Description Block. Suricata applies this offset when interpreting packet
timestamps; our scapy `PcapReader` does not. As a result, all Suricata eve.json timestamps
are exactly 7200 seconds (2 hours) ahead of the scapy-based flow timestamps stored in the
master table.

Before performing the time-window match, the alignment script subtracts this constant:

```
alert_time_corrected = alert_time_from_eve_json - PCAP_TS_OFFSET_S
```

**PCAP_TS_OFFSET_S = 7200 seconds** (frozen; verified empirically on the Monday PCAP, applied
uniformly to all 5 days).

This correction is a data engineering artifact, not a tunable parameter. The corrected
timestamp is stored as the `alert_time` column in `suricata_alerts_flat.csv`; all downstream
consumers of that file therefore see the scapy-aligned timestamp, not the raw eve.json value.

### 5.4 Match Candidates

Alignment is performed per-day. For each alert in day D:

1. Filter master flows where `pcap_file` matches day D
2. Among those, find flows where:
   - Canonical 5-tuple matches exactly
   - Corrected alert timestamp falls within the flow time window with tolerance T:
     `flow_start_time - T ≤ alert_time_corrected ≤ flow_end_time + T`
3. **Tolerance T = 2.0 seconds** (fixed constant, not tuned)
   - Rationale: CIC-IDS2017 flows use active_timeout=120s, idle_timeout=60s.
     A 2-second tolerance accommodates residual timestamp precision differences
     after the pcapng offset correction.

### 5.5 Match Status Classification

| Status | Condition |
|--------|-----------|
| `matched_unique` | Exactly 1 candidate flow matches the alert |
| `matched_ambiguous` | 2+ candidate flows match the alert |
| `alert_unmatched` | 0 candidate flows match the alert |

All three statuses are logged in `suricata_alert_flow_matches.csv`. No alerts
are silently discarded.

### 5.6 Flow-Level Prediction Rule

For each flow in the master table:

```
if (flow has ≥ 1 alert with match_status == 'matched_unique'):
    suricata_pred = 'attack'
else:
    suricata_pred = 'benign'
```

Rationale for excluding `matched_ambiguous`:
- Ambiguous matches indicate that the alert cannot be deterministically attributed
  to a single flow. Including them would risk false attributions.
- Ambiguous alerts are counted in `alert_count_ambiguous` for diagnostic purposes.
- This is a conservative rule that may underestimate recall slightly.

Note: Suricata does not produce a continuous score — it produces binary alerts.
Therefore, ROC-AUC and PR-AUC are **not reported** for this baseline.

---

## 6. Output Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Per-day eve.json | `D:/ids_project_data/suricata/cicids2017/{day}/eve.json` | Raw alert events |
| Per-day suricata.log | `D:/ids_project_data/suricata/cicids2017/{day}/suricata.log` | Engine log |
| Flat alerts CSV | `D:/ids_project_data/processed/cicids2017/suricata_alerts_flat.csv` | All alert events, standardized |
| Alert-flow matches | `D:/ids_project_data/processed/cicids2017/suricata_alert_flow_matches.csv` | Per-alert match result |
| Flow predictions | `D:/ids_project_data/processed/cicids2017/suricata_flow_predictions.csv` | Per-flow sidecar predictions |

Master parquet is **not modified**.

---

## 7. Invalidation Conditions

This baseline must be re-run if any of the following change:

1. Suricata version changes
2. ET Open rules are updated (different rule date/version)
3. `HOME_NET` or other key config settings change
4. The alignment tolerance (T = 2.0 seconds) is changed
5. The pcapng timestamp offset correction (`PCAP_TS_OFFSET_S = 7200 seconds`) is changed
6. The match status → prediction rule changes
7. Any Phase 1 or Phase 2 frozen asset changes (master parquet, interim labeled parquets, split assignment)

---

## 8. Limitations

- **No training process**: Suricata uses fixed rule signatures; there is no model fitting or threshold tuning.
- **Split relevance**: train/val/test splits are used only for organizing evaluation results, not for fitting or tuning.
- **Binary output**: Suricata alerts are binary (alert / no-alert); no continuous score is available.
- **ET Open rules vs CIC-IDS2017 attacks**: ET Open rules were created for general threats. CIC-IDS2017 attack patterns (especially synthetic/tool-generated DoS, brute-force) may not be covered by ET Open signatures.
- **9 rule failures**: Rules using `file.magic` keyword fail to load in Suricata 7.0.10. These are deep-packet inspection rules for file type analysis; their absence is unlikely to affect CIC-IDS2017 network-level attack detection.
- **Ambiguous alerts excluded**: Conservative policy may underestimate true attack recall.
- **pcapng timestamp offset**: CIC-IDS2017 PCAPs contain a 7200-second `if_tsoffset` in the pcapng Interface Description Block. Suricata applies this offset; scapy does not. The alignment script corrects for this with a constant subtraction. If a future dataset has a different pcapng offset, `PCAP_TS_OFFSET_S` must be updated.
