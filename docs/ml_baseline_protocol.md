# ML Baseline Protocol — CIC-IDS2017 In-Domain (Phase 3 Step 2)

> Version: 1.0
> Frozen: 2026-03-23
> Applies to: CIC-IDS2017, Phase 3 Step 2 — traditional ML in-domain baselines only

---

## A. Scope

This document governs the three formal traditional ML baselines on CIC-IDS2017.

**In scope:**
- Logistic Regression (LR)
- Random Forest (RF)
- XGBoost (XGB)
- In-domain evaluation: train/val/test all from CIC-IDS2017

**Out of scope (deferred to later phases):**
- 1D-CNN / LSTM (Phase 3 Step 3)
- Cross-domain transfer experiments (CSE-CIC-IDS2018, UNSW-NB15)
- Threshold portability across domains
- Suricata–ML fusion
- Any ensemble combining ML with other paradigms

---

## B. Inputs

| Input | Path | Frozen since |
|-------|------|-------------|
| Master feature table | `D:/ids_project_data/processed/cicids2017/cicids2017_flows_master.parquet` | Phase 1 |
| Split assignment sidecar | `D:/ids_project_data/processed/cicids2017/cicids2017_split_assignment.csv` | Phase 2 |
| ML config | `configs/ml_baselines.yaml` | Phase 3 Step 2 |

The master parquet is read-only. The split sidecar is read-only. No modifications to either.

**Formal input note (D1 compliance):** All features in the master parquet were extracted from
raw PCAP via the Phase 1 controlled pipeline (`src/data_ingestion/pcap_to_flows.py` +
`src/features/extract_flow_features.py`). No public precomputed CSV is used as training input.

---

## C. Models

| Model | Library | Version |
|-------|---------|---------|
| Logistic Regression | scikit-learn | 1.8.0 |
| Random Forest | scikit-learn | 1.8.0 |
| XGBoost | xgboost | 3.2.0 |

Saved as joblib files under `D:/ids_project_data/models/cicids2017/`.

---

## D. Label Definition

**Primary task: binary classification — `benign` (negative) vs. `attack` (positive).**

The `binary_label` column from the master parquet is the training label.
The `coarse_family` column is used only for post-hoc breakdown analysis, not as a training target.

---

## E. Split

Strictly reuse Phase 2 frozen day-level split (Decision D6):

| Split | Days | Rows | Attack % |
|-------|------|------|----------|
| train | Mon + Tue + Wed | 1,052,851 | 2.64% |
| val | Thu | 357,338 | 0.06% |
| test | Fri | 491,455 | 40.16% |

The split is loaded exclusively from `cicids2017_split_assignment.csv`. It is not re-derived
or hardcoded. Any per-flow random re-assignment is prohibited.

---

## F. Feature Columns

### F.1 Features used (19 columns)

| Column | Type | Notes |
|--------|------|-------|
| `duration_s` | float64 | Flow duration in seconds |
| `packet_count_total` | int64 | Total packets in flow |
| `bytes_total` | int64 | Total bytes in flow |
| `packet_count_fwd` | int64 | Forward direction packet count |
| `packet_count_bwd` | int64 | Backward direction packet count |
| `bytes_fwd` | int64 | Forward direction bytes |
| `bytes_bwd` | int64 | Backward direction bytes |
| `protocol` | int64 | IANA protocol number (TCP=6, UDP=17) |
| `is_tcp` | int64 | 1 if TCP else 0 |
| `is_udp` | int64 | 1 if UDP else 0 |
| `bytes_per_packet` | float64 | bytes_total / packet_count_total |
| `bytes_per_packet_fwd` | float64 | bytes_fwd / packet_count_fwd |
| `bytes_per_packet_bwd` | float64 | bytes_bwd / packet_count_bwd |
| `packets_per_second` | float64 | packet_count_total / duration_s |
| `bytes_per_second` | float64 | bytes_total / duration_s |
| `fwd_packet_ratio` | float64 | packet_count_fwd / packet_count_total |
| `bwd_packet_ratio` | float64 | packet_count_bwd / packet_count_total |
| `fwd_byte_ratio` | float64 | bytes_fwd / bytes_total |
| `bwd_byte_ratio` | float64 | bytes_bwd / bytes_total |

### F.2 Excluded columns and rationale

| Column | Reason |
|--------|--------|
| `global_flow_id` | Row identifier — not a predictive feature |
| `flow_id` | Row identifier — not a predictive feature |
| `pcap_file` | Encodes the capture day → leakage (directly encodes split membership) |
| `start_time` | Encodes the capture day → leakage (temporal) |
| `end_time` | Encodes the capture day → leakage (temporal) |
| `day` | Directly encodes split membership → leakage |
| `binary_label` | Training label — cannot be a feature |
| `coarse_family` | Derived from label — cannot be a feature |
| `matched_flag` | Pipeline metadata, not a flow property |
| `ambiguous_flag` | Pipeline metadata, not a flow property |
| `label_match_method` | Pipeline metadata, not a flow property |
| `original_label` | Label form — label leakage |

---

## G. Preprocessing

### G.1 Missing values and constants
The frozen master has 0 NaN values and 0 infinity values (verified by QA audit).
No imputation is required. If any NaN is encountered at runtime, an assertion fails.

### G.2 Scaling

| Model | Scaling | Rationale |
|-------|---------|-----------|
| Logistic Regression | StandardScaler (fit on train only) | LR is sensitive to feature scale |
| Random Forest | Identity (no scaling) | Tree-based; invariant to monotone transforms |
| XGBoost | Identity (no scaling) | Tree-based; invariant to monotone transforms |

Despite RF and XGB not requiring scaling, a `StandardScaler` preprocessor is still fitted and
saved for each model to provide a uniform interface for downstream consumers. RF and XGB
receive the **unscaled** feature matrix during training.

### G.3 Fit constraint
All preprocessing objects are fitted **exclusively on the train split**.
Applying any preprocessor fit step to val or test data is leakage and is prohibited.

---

## H. Class Imbalance Strategy

Train split: 27,803 attack / 1,025,048 benign ≈ 1:37 imbalance.

| Model | Strategy |
|-------|----------|
| Logistic Regression | `class_weight='balanced'` |
| Random Forest | `class_weight='balanced'` |
| XGBoost | `scale_pos_weight = benign_count / attack_count ≈ 36.87` |

These strategies are mandatory. No model is trained without explicit imbalance handling.

---

## I. Probability Output

All three models are configured to output `predict_proba` (scikit-learn) or
`predict_proba` equivalent. The `pred_score` in prediction sidecars is the probability
assigned to the **attack** class (positive class).

---

## J. Threshold Definition (3 tiers)

### J.1 Default threshold
`threshold = 0.5` applied to `pred_score`. Label = `attack` if `pred_score >= 0.5`.

### J.2 Val-tuned threshold (best F1)
For each model, sweep `pred_score` thresholds on the **val split** (Thursday) and select
the threshold that maximizes F1 score on val. This threshold is then applied to test.

### J.3 Fixed-FPR threshold (FPR budget = 1%)
For each model, find the **highest threshold** on the **val split ROC curve** such that
`FPR ≤ 0.01`. "Highest threshold" ensures we keep the FPR constraint while maximizing recall.
Formally: `t* = max{t : FPR(t, val) ≤ 0.01}`.

**Fixed FPR budget = 0.01 (1%)** — frozen in Decision D10.

If no threshold achieves FPR ≤ 0.01 on val (impossible for this dataset since threshold = 1.0
trivially achieves FPR = 0), the fallback is the threshold closest to FPR = 0.01.

This budget is chosen because:
- Val benign = 357,136 flows; FPR 1% = ≤3,571 FP, which is operationally meaningful.
- It tests whether models can operate under a realistic deployment constraint.

---

## K. Metrics

All metrics are computed separately for train, val, and test splits, and reported per model.

| Metric | Notes |
|--------|-------|
| Accuracy | Overall |
| Precision | Attack = positive class |
| Recall (TPR) | Attack = positive class |
| F1 | Harmonic mean of Precision/Recall |
| FPR | FP / (FP + TN); benign = negative class |
| ROC-AUC | Area under ROC curve |
| PR-AUC | Area under Precision-Recall curve (more informative under imbalance) |
| Confusion matrix | TP, FP, TN, FN |
| Recall@fixed-FPR | Recall achieved when FPR threshold applied to test |

**Coarse family breakdown:** For test split, per-family recall reported for each model
(descriptive only; coarse_family is not a training target).

### K.1 Calibration
Calibration (Platt scaling, isotonic regression) is **deferred to a later phase**.
Models produce uncalibrated probability scores in Phase 3 Step 2.

---

## L. Invalidation Conditions

This ML baseline freeze is invalid if any of the following changes:

1. `cicids2017_flows_master.parquet` is regenerated
2. `cicids2017_split_assignment.csv` is regenerated
3. The feature column list in Section F.1 changes
4. The preprocessing strategy in Section G changes
5. The class imbalance strategy in Section H changes
6. The model hyperparameters in `configs/ml_baselines.yaml` change
7. The FPR budget in Section J.3 changes (currently 0.01)

Re-freeze procedure: increment this document's version, update the `Frozen:` date,
re-run `scripts/train_ml_baselines_cicids2017.py --force` and discard prior results.

---

## M. What Has NOT Been Done

As of Phase 3 Step 2 freeze:
- No 1D-CNN or LSTM training
- No cross-domain transfer experiments
- No threshold portability analysis across datasets
- No Suricata–ML fusion
- No calibration (deferred)
- No CSE-CIC-IDS2018 or UNSW-NB15 processing
