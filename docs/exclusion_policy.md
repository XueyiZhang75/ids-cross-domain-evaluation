# Exclusion Policy

> Version: 1.0
> Frozen: 2026-03-23
> Applies to: CIC-IDS2017 (and will be extended uniformly to CSE-CIC-IDS2018, UNSW-NB15)

---

## 1. Purpose

This document defines which flows are excluded from the final training/evaluation master table, the reason categories, and how excluded flows are logged. The goal is:

- **No silent dropping.** Every excluded flow has a logged reason.
- **Full auditability.** Exclusion counts must balance across five mutually exclusive groups: `total_flows = matched_flows + unmapped_label_flows + ambiguous_flows + unmatched_flows + parse_fail_flows`.
- **No data leakage from exclusion.** Excluded flows are dropped from the master table entirely; they are not used in any training, validation, or test split.

---

## 2. Exclusion Categories

### Category A: Ambiguous (5-tuple conflict)

**Condition:** The canonical bidirectional 5-tuple of a flow appears in the label reference CSV with more than one distinct label (e.g., both `BENIGN` and `DoS Hulk`).

**Root cause:** Multiple sessions sharing the same IP:port pair but with different labels across time, without time-window disambiguation in the current implementation.

**Known occurrence:** CIC-IDS2017 Wednesday — ~158,105 flows (~31% of the day) due to DoS Hulk recycling TCP connections.

**Action:** Exclude from master table. Log in `ambiguous_log.csv`.

**Flag in labeled parquet:** `ambiguous_flag = True`, `matched_flag = False`

---

### Category B: Unmatched (key not found in CSV)

**Condition:** The canonical key of the flow is not present in the label reference CSV at all.

**Root cause:**
- Flows that started before or after the capture window recorded in the label CSV
- Broadcast/multicast flows with unusual port assignments
- Single-packet flows that may have been filtered from the label CSV's flow computation
- Edge cases in canonical key construction (e.g., port = 0)

**Action:** Exclude from master table. Log in `exclusion_log.csv` with reason `unmatched`.

**Flag in labeled parquet:** `ambiguous_flag = False`, `matched_flag = False`, `label_match_method = 'unmatched'`

---

### Category C: Parse failure (no key)

**Condition:** A row in the flow table could not produce a valid canonical key (e.g., missing IP or port field, type coercion error).

**Action:** Exclude from master table. Log in `exclusion_log.csv` with reason `parse_fail`.

**Flag in labeled parquet:** `ambiguous_flag = False`, `matched_flag = False`, `label_match_method = 'no_key'`

---

### Category D: Mapping failure (label not in mapping table)

**Condition:** The flow was matched to a label in the reference CSV, but the label string is not present in `data/external/label_mapping_master.csv`.

**Action:** Exclude from master table. Log in `exclusion_log.csv` with reason `unmapped_label`. Log the unknown label string explicitly.

**Flag in labeled parquet:** `matched_flag = True` but `binary_label = None`

---

## 3. What Is NOT Excluded

| Situation | Decision |
|-----------|----------|
| Flows with `duration_s = 0` (single-packet flows) | **Retained.** Single-packet flows are valid; they may represent scans or probes. |
| Flows with zero bytes in one direction | **Retained.** Unidirectional flows are common and informative. |
| Flows with very large packet counts | **Retained.** No outlier removal at this stage. |
| Benign flows from attack days | **Retained** if matched. Background benign traffic is part of the dataset. |
| Flows from days not used in current split | **Retained** in master table with `day` column; split assignment is done downstream. |

---

## 4. Log File Specifications

### 4.1 `parse_log.json`

Records the outcome of the PCAP extraction step.

```json
{
  "day": "wednesday",
  "pcap_file": "Wednesday-workingHours.pcap",
  "pcap_size_bytes": 13420789612,
  "flows_produced": 504461,
  "run_timestamp": "2026-03-23T00:01:00",
  "status": "complete"
}
```

If extraction was skipped (cached result reused), `status = "cached"`.

### 4.2 `ambiguous_log.csv`

One row per **flow** that was excluded due to ambiguity.

Columns: `flow_id, pcap_file, src_ip, src_port, dst_ip, dst_port, protocol, start_time, end_time, exclusion_reason`

`exclusion_reason` = `ambiguous_5tuple`

### 4.3 `exclusion_log.csv`

One row per **flow** excluded for reasons B, C, or D.

Columns: `flow_id, pcap_file, src_ip, src_port, dst_ip, dst_port, protocol, start_time, end_time, exclusion_reason`

`exclusion_reason` values: `unmatched`, `parse_fail`, `unmapped_label`

### 4.4 `summary_stats.json`

Overall per-day statistics after all steps complete.

```json
{
  "day": "wednesday",
  "total_flows": 504461,
  "matched_flows": 346335,
  "ambiguous_flows": 158105,
  "unmatched_flows": 21,
  "parse_fail_flows": 0,
  "unmapped_label_flows": 0,
  "excluded_total": 158126,
  "match_rate_pct": 68.66,
  "binary_label_dist": {"benign": 323923, "attack": 22412},
  "coarse_family_dist": {"dos_ddos": 22412},
  "protocol_dist": {"TCP_6": 0, "UDP_17": 0},
  "label_files_used": ["Wednesday-workingHours.pcap_ISCX.csv"],
  "generated_at": "2026-03-23T..."
}
```

---

## 5. Accounting Identity

Every flow belongs to exactly one of five mutually exclusive groups:

| Group | Field in summary_stats | Condition |
|-------|----------------------|-----------|
| A | `matched_flows` | `matched_flag=True` AND `binary_label IS NOT NULL` |
| B | `unmapped_label_flows` | `matched_flag=True` AND `binary_label IS NULL` |
| C | `ambiguous_flows` | `ambiguous_flag=True` (and `matched_flag=False`) |
| D | `unmatched_flows` | `label_match_method == 'unmatched'` |
| E | `parse_fail_flows` | `label_match_method == 'no_key'` |

For every day, the following identity must hold:

```
total_flows
  = matched_flows          (A)
  + unmapped_label_flows   (B)
  + ambiguous_flows        (C)
  + unmatched_flows        (D)
  + parse_fail_flows       (E)
```

`excluded_total = total_flows - matched_flows` (i.e., B + C + D + E).

The QA script (`scripts/qa_cicids2017.py`) verifies this identity for every day.

---

## 6. Master Table Membership

Only Group A flows (`matched_flag = True` AND `binary_label IS NOT NULL`) are included in `cicids2017_flows_master.parquet`.

Groups B–E are excluded and traceable through the per-day log files.
The `matched_flows` field in `summary_stats.json` always equals the number of Group A flows for that day (i.e., the row count contributed to master).
