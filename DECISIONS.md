# Design Decisions

> This file records key design decisions, their rationale, and their
> implications for the project. Entries are numbered D1, D2, … and should not
> be deleted — if a decision is revised, append a new entry that supersedes
> the old one.

---

## D1 — Raw PCAP as the Formal Input

**Decision:**
The formal input to every pipeline component is raw PCAP. All flow-level
features must be derived from PCAP via a controlled extraction step (tool
TBD — e.g., CICFlowMeter, NFStream, or Zeek). Public CSV or precomputed
flow files may only serve as label references or sanity checks.

**Rationale:**
- Ensures all methods are evaluated under a truly unified input, eliminating
  discrepancies caused by different feature extraction tools or versions.
- Makes the pipeline self-contained and reproducible: given the same PCAP and
  the same extractor configuration, any researcher can reproduce the feature
  set.
- Prevents implicit reliance on preprocessing choices embedded in third-party
  CSV releases, which may differ across dataset versions.

**Implication:**
- A flow extraction stage must exist in the pipeline before any modeling.
- Runtime and storage costs are higher than starting from public CSVs.
- The extraction tool and its version must be documented and pinned.

---

## D2 — Binary Classification as the Primary Task (Initial Stage)

**Decision:**
The primary classification task at the initial stage is binary detection:
benign vs. attack. Multi-class attack-type classification may be explored
later but is not the initial focus.

**Rationale:**
- Binary detection is the most operationally relevant question for an IDS:
  "Is this flow malicious?"
- It provides a clean, common evaluation axis across all three paradigms
  (rule-based, ML, DL), since Suricata alerts can be directly mapped to a
  binary label.
- Starting with binary classification simplifies threshold analysis (E6),
  FPR budgets, and cross-domain comparisons before adding the complexity of
  multi-class boundaries.

**Implication:**
- Label mapping must collapse all attack types into a single positive class.
- Per-attack-type breakdowns are still planned but treated as a secondary
  analysis layer, not the primary evaluation metric.

---

## D3 — No Target-Domain Data for Threshold Tuning in Transfer Experiments

**Decision:**
In cross-domain transfer experiments, target-domain data must not be used for
model tuning, decision-threshold selection, or score calibration.

**Rationale:**
- The research question is whether an IDS trained in one environment can
  detect attacks in a different environment without any adaptation.
- Using even a small amount of target-domain labeled data for threshold
  selection would conflate "transferability" with "few-shot adaptation,"
  undermining the validity of the cross-domain evaluation.
- This strict discipline produces a conservative but honest measure of
  real-world portability.

**Implication:**
- Thresholds must be fixed using source-domain validation data only.
- Metrics in transfer experiments may look worse than in-domain results; this
  is expected and is the point of the analysis.
- Any future adaptation experiments (e.g., fine-tuning with limited target
  labels) must be clearly separated and labeled as such.

---

## D4 — Feature-Based ML Baselines Before DL Baselines

**Decision:**
Traditional feature-based ML models (Logistic Regression, Random Forest,
XGBoost) should be implemented and validated before deep learning models
(1D-CNN, LSTM).

**Rationale:**
- ML baselines are faster to train, easier to debug, and provide interpretable
  reference points for evaluating DL improvements.
- Establishing solid baselines first ensures that any DL gains are measured
  against a properly tuned reference, not a weak strawman.
- This order reduces the risk of spending time on complex DL pipelines before
  the data layer and evaluation framework are validated.

**Implication:**
- DL model implementation is deferred until ML baselines produce stable,
  reproducible results on at least one dataset.
- The feature extraction pipeline must be fully functional before ML baselines
  can run.

---

## D5 — Leakage-Aware Split Design

**Decision:**
Train/validation/test splits must be designed to prevent data leakage. Naive
random shuffling of individual flows is not permitted. Splits should be based
on capture-level units such as time windows, sessions, scenarios, or capture
files.

**Rationale:**
- Flows from the same session or time window share statistical properties
  (e.g., IP pairs, timing patterns). Random shuffling distributes correlated
  flows across splits, leading to inflated performance estimates that do not
  generalize.
- Leakage-aware splits produce more realistic performance estimates and are
  increasingly expected in published IDS research.

**Implication:**
- Split logic must be implemented as a dedicated, configurable module
  (not ad-hoc in training scripts).
- The split strategy and its parameters must be recorded in config files and
  experiment logs.
- Performance numbers may be lower than those reported in papers that use
  random splits; this is acceptable and should be discussed explicitly.

---

## D6 — CIC-IDS2017 Day-Level Split Assignment (Phase 2 Freeze)

**Decision:**
The CIC-IDS2017 train/val/test split is frozen at day granularity with the
following immutable assignment:

| Split | Days |
|-------|------|
| train | Monday, Tuesday, Wednesday |
| val   | Thursday |
| test  | Friday |

This mapping is recorded in `docs/split_protocol.md` (Version 1.0, frozen
2026-03-23) and implemented by `scripts/freeze_phase2_cicids2017.py`.

**Rationale:**
- Day-level split satisfies the leakage-aware design principle (D5): all flows
  from a given capture day share network context, timing, and IP structure; mixing
  them across splits would inflate generalization estimates.
- The specific day assignment places Wednesday (DoS Hulk, the largest attack day)
  in train to ensure the model sees high-volume attack patterns; Thursday
  (web attacks + infiltration) and Friday (reconnaissance + botnet) provide
  structurally different attack types in val and test, giving a realistic
  generalization test.
- Day-level splits are fully deterministic and require no random seed.

**Implication:**
- The day→split mapping must not be changed to improve model performance.
  Any change requires a new version of `docs/split_protocol.md` and a full
  re-freeze, with all prior results discarded.
- Any preprocessing object (scaler, normalizer, imputer, calibration object) must
  be fitted on the train split only.

---

## D7 — Sidecar Split Assignment CSV (Master Table Immutability)

**Decision:**
The split assignment is stored as a separate sidecar file
(`cicids2017_split_assignment.csv`) rather than being written into the master
parquet. The master parquet is read-only from Phase 1 onward.

**Rationale:**
- Modifying the master parquet to add a split column would change the SHA-256
  hash of the frozen Phase 1 asset, making it impossible to verify that the
  feature data itself has not changed.
- A sidecar CSV is trivially regenerable from the frozen master and the frozen
  split protocol; it can be verified independently.
- This pattern keeps the data asset (master parquet) and the experimental
  protocol (split assignment) as separate, independently auditable artifacts.

**Implication:**
- Downstream scripts that need both features and split labels must join on
  `global_flow_id` at load time; they must not rely on a split column in master.
- If the master parquet is ever regenerated, the sidecar must also be regenerated
  via `scripts/freeze_phase2_cicids2017.py --force`.

---

## D8 — Phase 2 Frozen Input Asset Scope

**Decision:**
The following assets are declared frozen for all Phase 2 CIC-IDS2017 experiments:

**Direct inputs (models may consume):**
- `{day}_features.parquet` (5 days)
- `cicids2017_flows_master.parquet`
- `cicids2017_split_assignment.csv`

**Protocol / config / mapping (govern how inputs are used):**
- `docs/flow_schema.md`
- `docs/exclusion_policy.md`
- `docs/split_protocol.md`
- `configs/feature_config.yaml`
- `data/external/label_mapping_master.csv`

**Audit reference (not direct inputs):**
- Per-day `summary_stats.json` (5 days)
- `reports/cicids2017_qa_report.md`
- `reports/cicids2017_split_audit.md`

SHA-256 hashes and file sizes for all assets are recorded in
`reports/cicids2017_input_asset_manifest.csv` (generated 2026-03-23).

**Rationale:**
- Explicitly bounding the input scope prevents silent drift: if any frozen asset
  changes, the manifest hash will no longer match, making the change detectable.
- A structured manifest supports reproducibility audits in the final report.

**Invalidation condition:** If any frozen asset changes, the Phase 2 freeze is
invalid. Re-run `scripts/freeze_phase2_cicids2017.py --force` and discard all
results from Phase 3 onward that were produced under the old freeze.

---

## D9 — pcapng Timestamp Offset Correction for Suricata Alignment

**Decision:**
When aligning Suricata eve.json alert timestamps against scapy-extracted flow timestamps for
CIC-IDS2017, subtract a constant offset of **7200 seconds** from all Suricata timestamps before
performing the time-window match. This value is recorded as `PCAP_TS_OFFSET_S = 7200` in
`scripts/align_suricata_alerts_to_master.py` and is frozen in `docs/suricata_baseline_protocol.md`.

**Rationale:**
- The CIC-IDS2017 capture files are in pcapng format and contain an `if_tsoffset = 7200` in
  the Interface Description Block. Suricata reads and applies this offset when interpreting
  packet timestamps; our scapy `PcapReader` does not apply it.
- As a result, Suricata eve.json timestamps are systematically 7200 seconds (2 hours) ahead
  of the flow `start_time` / `end_time` values stored in the master table.
- Without this correction, the time-window match rate drops from ~94% to ~0.03%.
- This is a data engineering artifact, not a tunable model parameter; the offset was
  verified empirically on the Monday PCAP and confirmed to be constant.

**Implication:**
- `PCAP_TS_OFFSET_S = 7200` is a frozen constant for CIC-IDS2017 only.
- For other datasets (CSE-CIC-IDS2018, UNSW-NB15), the pcapng offset must be independently
  verified; a different or zero offset may apply.
- The correction is applied only during alignment; no output file stores the corrected
  timestamps.

---

## D10 — Fixed FPR Budget = 1% for Threshold Selection

**Decision:**
For all in-domain ML baseline experiments on CIC-IDS2017, a fixed false-positive-rate (FPR)
budget of **1% (0.01)** is used when selecting the "operational" threshold tier. The threshold
is chosen as the lowest score value such that FPR ≤ 0.01 on the val split.

**Rationale:**
- A 1% FPR is a practically meaningful ceiling for a production IDS: at the CIC-IDS2017
  master scale (~294k benign test flows), 1% FPR ≈ 2,940 false alarms per day — already
  operationally demanding. Tighter budgets (0.1%) would suppress recall entirely for weak
  models.
- Fixing the budget in advance (before seeing test data) keeps threshold selection
  target-domain-free and aligned with D3.
- The same 1% budget will be applied uniformly to LR, RF, XGBoost, and DL baselines,
  ensuring cross-paradigm comparability under identical operating constraints.

**Implication:**
- The fixed-FPR threshold is derived from val only; test FPR at this threshold may differ.
- If val has very few positive examples (e.g., Thursday: 202 attacks), the val-tuned
  threshold is unreliable, but the fixed-FPR threshold remains stable because it depends
  only on the negatives.
- For future datasets, the same 0.01 budget applies unless superseded by a new decision.

---

## D11 — class_weight='balanced' as Formal Baseline Strategy for LR and RF

**Decision:**
Logistic Regression and Random Forest baselines use `class_weight='balanced'` to handle
class imbalance. XGBoost uses `scale_pos_weight = n_neg / n_pos` (computed from train).
No oversampling or undersampling is applied.

**Rationale:**
- CIC-IDS2017 train has ≈1:37 benign:attack ratio (1,025,048 benign / 27,803 attack).
  Without imbalance correction, both LR and RF converge to predicting all-benign, producing
  near-zero recall.
- `class_weight='balanced'` and `scale_pos_weight` are the standard sklearn/XGBoost
  mechanisms for this; they reweight the loss function without altering the training data,
  preserving the original class distribution in any downstream analysis.
- Oversampling (SMOTE) or undersampling would change data statistics and introduce
  additional degrees of freedom that complicate comparison with the rule-based baseline.

**Implication:**
- Future DL baselines should use an equivalent loss-reweighting strategy (e.g.,
  `class_weight` in Keras or `pos_weight` in PyTorch BCEWithLogitsLoss) for fair comparison.
- If a later experiment deliberately removes imbalance correction as an ablation, that must
  be documented as a separate decision entry.

---

## D12 — Canonical DL Sequence Setting (Phase 3 Step 3)

**Decision:**
The canonical DL baseline sequence configuration for CIC-IDS2017 is frozen as:

| Parameter | Value |
|-----------|-------|
| K (sequence length) | 16 |
| Feature set | B: [signed_packet_len, direction_flag, delta_t, protocol_id] |
| K_MAX (cache storage) | 32 (supports ablation K∈{8,16,32}) |
| signed_packet_len | IP total length × (+1 forward / −1 backward) |
| direction_flag | 1=forward (src_ip matches flow.src_ip), 0=backward |
| delta_t | seconds since previous packet; 0 for first packet |
| protocol_id | TCP(6)→0, UDP(17)→1 |
| Truncation | First K packets only; remaining discarded |
| Padding | Zero-pad at end if flow has fewer than K packets |
| Normalization | signed_packet_len: StandardScaler; delta_t: log1p then StandardScaler; direction_flag, protocol_id: none |
| Scaler fitting | Train non-padded steps only; val/test transform-only |
| Masking | Not used in canonical baseline |

**Rationale:**
- K=16 captures the opening exchange of most flows without excessive padding overhead; the
  majority of CIC-IDS2017 flows have <16 packets (89.5% padded after build).
- Features A (direction_flag + protocol_id, indices [1, 3]) proved insufficient in ablation
  (CNN val PR-AUC 0.008 vs 0.031 for features B); signed_packet_len and delta_t in set B
  add packet-size and timing context absent from set A.
- K_MAX=32 stored in cache allows ablation without re-reading PCAPs.
- This setting is for CIC-IDS2017 only. For other datasets it must be independently validated.

**Implication:**
- Any change to K, the feature set, normalization, or padding strategy invalidates all
  Phase 3 Step 3 results and requires full re-run from sequence build.
- Cross-domain experiments must use the same sequence definition to ensure comparability.

---

## D13 — Dataset Set Revision: CSE-CIC-IDS2018 Replaced by IoT-23 (2026-03-25)

**Decision:**
The project dataset combination is formally revised from {CIC-IDS2017, CSE-CIC-IDS2018, UNSW-NB15}
to {CIC-IDS2017, IoT-23, UNSW-NB15}. CSE-CIC-IDS2018 is removed from all future formal
experiments. IoT-23 is introduced as the second dataset for cross-domain evaluation.

**Rationale:**
1. **PCAP storage constraint:** CSE-CIC-IDS2018 raw PCAPs total ~477 GB compressed on S3,
   exceeding the available disk budget (~193 GB) required for full formal extraction.
2. **Label join structural limitation:** The CSE-CIC-IDS2018 CICFlowMeter CSVs (the only
   available label reference) contain 80 feature columns but no Src IP, Dst IP, or Src Port
   fields. A 5-tuple-based flow-label join (as used successfully for CIC-IDS2017) is not
   directly feasible, requiring a complex workaround.
3. **IoT-23 advantages:** IoT-23 provides per-scenario PCAP + Zeek conn.log.labeled files
   with full 5-tuple fields, enabling a straightforward flow-label join. The dataset
   represents a meaningfully different domain (IoT traffic, diverse malware families),
   making cross-domain evaluation more informative.

**Scope of change:**
- CIC-IDS2017 Phase 1/2/3 results are unaffected; all frozen assets remain valid.
- UNSW-NB15 remains as the third dataset; its planned intake is unchanged.
- CSE-CIC-IDS2018 is not used for training, evaluation, or any formal experiment going forward.
  The brief intake work performed on 2026-03-25 has been reverted and is not retained.

**Implication:**
All future cross-domain experiments reference IoT-23 (not CSE-CIC-IDS2018) as the second dataset.
UNSW-NB15 remains the third dataset. This decision is permanent unless explicitly superseded.

---

## D14 — UNSW-NB15 Formal Split Protocol (Phase 5 Step 1)

**Decision:**
UNSW-NB15 formal split is file-based, aligned with the two capture dates:

| Split | Source | Files | Capture period |
|-------|--------|-------|----------------|
| train | pcaps 22-1-2015 | files 1–10 (Phase 5 Step 1 subset) | Jan 22, 2015 (morning) |
| val | pcaps 22-1-2015 | files 44–53 (Phase 5 Step 1 subset) | Jan 22, 2015 (late afternoon) |
| test | pcaps 17-2-2015 | files 24–27 (Phase 5 Step 1 subset) | Feb 17-18, 2015 |

The train/test boundary is the capture date boundary (Jan 22 vs Feb 17-18).
No random flow-level shuffling across dates. Full dataset expansion defers pcaps 22-1-2015
files 11-43 and pcaps 17-2-2015 files 1-23.

**Rationale:**
- Capture date provides a natural leakage-free split boundary (26-day gap between Jan and Feb).
- File ordering within each date provides temporal ordering for train/val split within Jan 22.
- Disk constraint (135 GB free) prevents downloading the full ~107 GB dataset in one phase.
- Deferred files can be added to expand train/val/test without changing split boundaries.

**Implication:**
- All UNSW-NB15 in-domain and cross-domain experiments must use this file-based split.
- The split boundary (Jan vs Feb) cannot be changed in later phases without creating a new
  superseding decision entry.
- When deferred files are added, they expand existing splits without modifying this boundary.

---

## D15 — UNSW-NB15 Flow-Label Join Protocol (Phase 5 Step 1)

**Decision:**
UNSW-NB15 flow-label join uses:
1. **Primary key**: canonical bidirectional 5-tuple (min_ip, min_port, max_ip, max_port, proto_int)
   - proto_int: 'tcp'→6, 'udp'→17 (only these two are extractable from pcap_to_flows.py)
2. **Disambiguation**: |flow.start_time − csv.Stime| < 5.0 seconds for ambiguous matches
3. **Scope**: Only TCP and UDP flows can be joined; all other protocols (OSPF, ICMP, ARP, etc.)
   are formally excluded and counted as unmatched

**Rationale:**
- UNSW-NB15 CSV was generated by Argus; scapy-based extraction uses different flow
  aggregation, so exact matches are not guaranteed. Timestamp tolerance handles small offsets.
- Restricting to TCP/UDP is consistent with the project's existing extractor, which only
  handles these two protocols.
- The canonical bidirectional form matches the project's established join convention (used
  for CIC-IDS2017 and IoT-23).

**Implication:**
- Join rate will be <100% even for TCP/UDP flows; this is expected and documented.
- Non-TCP/UDP protocol flows in the CSV are informative but not joinable in this pipeline;
  their attack categories are not representable in the formal training set.

---

## D16 — UNSW-NB15 Formal Split Protocol v2 (Phase 5 Step 1 Remedial Revision)

> **Date:** 2026-03-31
> **Supersedes:** D14 (UNSW-NB15 Formal Split Protocol v1)

**Decision:**
UNSW-NB15 formal subset v2 uses the following split:

| Split | Capture Date | PCAP Files | Time Coverage (UTC) | Attack Present |
|-------|-------------|------------|---------------------|----------------|
| train | Jan 22, 2015 | pcaps_22-1-2015/1–6 | 11:50–13:10 | YES |
| val   | Jan 22, 2015 | pcaps_22-1-2015/7–9 | 13:10–13:52 | YES |
| test  | Feb 17–18, 2015 | pcaps_17-2-2015/24–26 | 10:56–12:21 | YES |

Files excluded: Jan 22 files 10, 44–53 (all benign); Feb files 27 (past CSV label window).

D14 is superseded and must not be used as the formal split for any UNSW experiments.
D15 (join protocol) is UNCHANGED.

**Rationale:**
Formal diagnosis (reports/unsw_nb15_remedial_diagnosis.md) showed two structural defects
in the D14 split:

1. **val全benign**: Jan 22 label CSV attacks are confined to 11:49–13:59 UTC. D14's val
   (files 44–53, 22:18–00:25 UTC) fell entirely outside this window → 0 attacks.
   D16 moves val to files 7–9 (13:10–13:52 UTC, within the attack window) → 3,126 attacks.

2. **27.pcap low join rate**: file 27 starts at exactly the last CSV label timestamp
   (02-18 12:21 UTC). 11,514 flows have no matching label row. D16 excludes file 27;
   test = files 24–26 only, all with ≥99.9% join rate.

**v2 characteristics:**
- Total: 295,599 labeled flows (vs v1: 506,385)
- val: 57,955 flows, 3,126 attacks (5.4%) — attack-aware validation enabled
- test: 122,175 flows, all ≥99.9% join rate — no low-quality file dependency
- Jan vs Feb leakage-aware boundary preserved
- No new PCAP downloads required; split reassignment of existing 12 parquets

**Implication:**
- D14 archive: unsw_nb15_master_v1_archive.parquet (retained, not deleted)
- D16 formal: unsw_nb15_master.parquet (295,599 rows, v2)
- All UNSW experiments use D16 from this point forward

---
