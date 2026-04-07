# DL Baseline Protocol
## CIC-IDS2017 In-Domain Evaluation — 1D-CNN and LSTM

**Phase:** 3, Step 3
**Status:** Implemented — Phase 3 Step 3 complete (2026-03-23)
**Last updated:** 2026-03-23

---

## A. Scope

This protocol governs the **in-domain DL baseline experiments** on CIC-IDS2017 only.

It covers:
- Sequence extraction from raw PCAP
- Model training for 1D-CNN and LSTM
- Evaluation under a unified protocol shared with the ML baselines

This protocol does **not** govern:
- Cross-domain transfer experiments
- Fusion / ensemble experiments
- Calibration fitting
- Any dataset other than CIC-IDS2017

Results produced under this protocol are the DL component of the unified in-domain comparison table.
Cross-domain and fusion phases will reference these artifacts but must not alter the artifacts themselves.

---

## B. Inputs

All inputs must be present before any experiment begins. No experiment should proceed with missing or substitute inputs.

| Input | Path | Role |
|---|---|---|
| Raw PCAP files | `D:/ids_project_data/cicids2017/pcap/{Day}-WorkingHours.pcap` | Packet sequence source (formal input) |
| Interim flow files | `D:/ids_project_data/interim/cicids2017/{day}_flows.parquet` | Flow-to-packet localization (src_ip, dst_ip, src_port, dst_port, protocol) |
| Master parquet | `D:/ids_project_data/processed/cicids2017/cicids2017_flows_master.parquet` | Labels and split membership (1,901,644 rows, 31 columns) |
| Split sidecar | `D:/ids_project_data/processed/cicids2017/cicids2017_split_assignment.csv` | Frozen split assignments per flow |
| Config file | `configs/dl_baselines.yaml` | All tunable parameters |

**On raw PCAP:** The raw PCAP files are in pcapng format despite the `.pcap` extension. The packet extraction pipeline must handle pcapng transparently (e.g., via `scapy` or `pyshark` with pcapng support).

**On interim flows:** The interim parquet files carry the five-tuple fields (`src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol`) required for canonical key construction and for determining packet direction. They are not used as training features directly.

**On master parquet:** Used exclusively for labels (`label`, `coarse_family`) and split membership. Feature columns in the master parquet are not used as DL model inputs.

**On the formal input constraint:** Public precomputed CSV flow tables must not replace raw PCAP as the sequence source. Packet sequences must be derived from raw PCAP.

---

## C. Models

Two DL architectures are evaluated in this phase.

### C1. 1D-CNN

- Input: `(batch, K, F)` where K = sequence length, F = number of features
- Architecture: two 1D convolutional layers (channels 64 → 128, kernel size 3), ReLU activation, global max pooling, fully connected hidden layer (64 units), sigmoid output
- Dropout: 0.3 after convolutional stack
- Output: single logit (scalar per sample); probability via sigmoid

### C2. LSTM

- Input: `(batch, K, F)`
- Architecture: 2-layer unidirectional LSTM (hidden size 128), take last hidden state, fully connected hidden layer (64 units, dropout 0.3), sigmoid output
- Dropout between LSTM layers: 0.2
- Bidirectional: false (canonical; may be explored as future work)
- Output: single logit; probability via sigmoid

Both models share the same training loop, loss function, optimizer, and evaluation harness.

---

## D. Label

Binary classification only.

| Label value | Meaning | Source |
|---|---|---|
| 0 | Benign | `label == "BENIGN"` in master parquet |
| 1 | Attack | all other label values |

The `coarse_family` field from the master parquet is used for descriptive per-family breakdowns in evaluation reports but does not affect training targets.

Multi-class classification is deferred to a later phase and is out of scope here.

---

## E. Split

The split is frozen and must not be re-derived or altered. It is defined by calendar day of capture.

| Split | Days | Flows |
|---|---|---|
| Train | Monday + Tuesday + Wednesday | 1,052,851 |
| Val | Thursday | 357,338 |
| Test | Friday | 491,455 |

**Class imbalance (train):**
- Attack flows: 27,803
- Benign flows: 1,025,048
- Ratio: approximately 1:37
- Computed `pos_weight` = 36.87 (used in loss function)

Split membership is read from the split sidecar CSV (`cicids2017_split_assignment.csv`). The sidecar is the authoritative source. Do not re-derive splits from the master parquet columns independently.

**Leakage note:** Flows are assigned to splits by day, not by random sampling. This prevents session-level leakage across splits.

---

## F. Canonical Sequence Protocol

This section is the authoritative specification for packet sequence construction. Any deviation from this specification invalidates all DL results (see Section L).

### F1. Canonical Hyperparameters

| Parameter | Value |
|---|---|
| K (canonical baseline) | 16 |
| K_MAX (stored in cache) | 32 |
| Number of features (F) | 4 |
| Feature set | B (canonical) |

### F2. Time-Step Features

Each time step in the sequence is a 4-dimensional vector. Features are listed in index order.

| Index | Name | Description |
|---|---|---|
| 0 | `signed_packet_len` | IP total length (`ip.len`) multiplied by +1 if forward, −1 if backward |
| 1 | `direction_flag` | 1 if forward packet, 0 if backward packet |
| 2 | `delta_t` | Seconds elapsed since the previous packet in this flow (0.0 for the first packet) |
| 3 | `protocol_id` | TCP → 0, UDP → 1 |

**Direction definition:**
A packet is "forward" if its source IP matches the `src_ip` of the flow record in the interim flows parquet. Otherwise it is "backward". The comparison is performed on string representations of IP addresses.

**`signed_packet_len` detail:**
`signed_packet_len = ip.len × (+1 if forward else −1)`.
Approximate range: [−1500, +1500] (before normalization).
For non-IP packets, the packet should be skipped or assigned length 0 with a note in the log.

**`delta_t` detail:**
`delta_t[i] = timestamp[i] − timestamp[i−1]` for i > 0.
`delta_t[0] = 0.0`.
Timestamps come from the PCAP packet headers. Do not derive timestamps from flow-level fields.

**`protocol_id` detail:**
Only TCP (proto=6) and UDP (proto=17) are assigned. If a flow uses a different protocol, log it and exclude the flow from DL evaluation (do not fabricate a protocol_id).

### F3. Canonical Flow Key

The same bidirectional canonical key used in `flow_schema.md` applies here.

```
a = (src_ip_str, src_port)
b = (dst_ip_str, dst_port)

if a <= b:
    key = (a[0], a[1], b[0], b[1], proto)
else:
    key = (b[0], b[1], a[0], a[1], proto)
```

This ensures that forward and reverse packets of the same connection map to the same flow record, regardless of observation direction.

### F4. Truncation and Padding

- **Truncation:** Only the first K_MAX = 32 packets of each flow are stored in the cache. For the canonical run (K = 16), only the first 16 packets are used.
- **Padding:** If a flow has fewer than K packets, zero-pad on the right to length K.
- Padding vectors are all zeros across all F features.

### F5. Masking

Masking is **not** used in the canonical baseline. Padded positions are not masked in the attention or recurrent computation. Masking is noted as a future work item and may be explored in ablation or a later phase.

### F6. Normalization

Normalization is applied per feature. Scalers are fit **only on non-padded train-split time steps**. Padded positions are excluded from scaler fitting. After normalization is applied to all splits, padded positions are re-zeroed.

| Feature | Normalization |
|---|---|
| `signed_packet_len` | `StandardScaler` (fit on non-padded train steps) |
| `delta_t` | `log1p` transform, then `StandardScaler` (fit on non-padded train steps) |
| `direction_flag` | None (already binary 0/1) |
| `protocol_id` | None (already binary 0/1) |

The two scaler objects (for `signed_packet_len` and `delta_t`) are serialized to disk after fitting and reused for val and test preprocessing. They must not be re-fit on val or test data.

### F7. Sequence Cache

Sequences are stored at:
```
D:/ids_project_data/processed/cicids2017/dl_sequences/
```

Each cached file stores K_MAX = 32 time steps per flow. Shorter K values (K = 8, K = 16) are obtained by slicing `[:K]` at load time, without rebuilding the cache.

The cache schema per flow:
- `flow_id`: matching the master parquet index
- `sequence`: ndarray of shape `(K_MAX, F_MAX)` (float32, post-normalization)
- `n_packets`: number of actual (non-padded) packets in the flow

If the cache already exists and the protocol parameters have not changed, rebuilding is not required.

---

## G. Ablation Protocol

Two ablation dimensions are defined. Ablations use the same sequence cache (different slices).

### G1. K Ablation (fixing feature set B)

| K value | Description |
|---|---|
| 8 | Short context |
| 16 | Canonical |
| 32 | Long context |

For each K, the model is trained from scratch with the same architecture and hyperparameters, using only the first K packets from the cache.

### G2. Feature Set Ablation (fixing K = 16)

| Feature set | Indices | Features |
|---|---|---|
| A | [1, 3] | `direction_flag`, `protocol_id` |
| B | [0, 1, 2, 3] | `signed_packet_len`, `direction_flag`, `delta_t`, `protocol_id` (canonical) |

### G3. Scope Limit

No further hyperparameter search (learning rate, architecture depth, hidden size, etc.) is performed beyond the K × feature-set dimensions above. Additional search is deferred to a later phase.

---

## H. Training Rules

All training must follow these rules exactly.

| Parameter | Value |
|---|---|
| Train data | Train split only |
| Batch size | 512 |
| Max epochs (canonical) | 30 |
| Max epochs (ablation) | 15 |
| Optimizer | Adam |
| Learning rate | 1e-3 |
| Loss function | `BCEWithLogitsLoss` with `pos_weight = 36.87` |
| Random seed | 42 |
| Device | CUDA if available, else CPU |

**Early stopping:**
- Metric: val PR-AUC (area under precision-recall curve on validation split)
- Patience: 5 epochs (stop if val PR-AUC does not improve for 5 consecutive epochs)
- Save the checkpoint with the best val PR-AUC; use this checkpoint for all evaluation

**Val usage during training:**
- Val split is used for early stopping and model selection only
- Val split is used for threshold selection (see Section I)
- Val split is never used to adjust architecture, loss weights, or optimizer settings after the run begins

**Test usage:**
- Test split is used exclusively for final result reporting
- No tuning, threshold adjustment, or model selection may use test data

**Reproducibility:**
- Set `torch.manual_seed(42)` and `numpy.random.seed(42)` before any data loading or model initialization
- DataLoader workers should use a fixed worker seed derived from 42

---

## I. Probability and Threshold

### I1. Output Probability

The model outputs a scalar logit. The attack probability is:

```
p = sigmoid(logit)  ∈ [0, 1]
```

This probability is stored for all val and test flows before any threshold is applied.

### I2. Threshold Tiers

Three operating thresholds are reported for each model.

| Tier | Label | Definition |
|---|---|---|
| Default | `thresh_default` | 0.5 (fixed) |
| Val-tuned | `thresh_val_f1` | Threshold maximizing F1 on val split |
| Fixed-FPR | `thresh_fpr_d10` | Lowest threshold achieving FPR ≤ 0.01 on val split |

The fixed-FPR tier corresponds to the **D10 operating point** (FPR budget ≤ 1%).

### I3. Selection Discipline

All three thresholds are derived from val split probabilities only. Test split probabilities are never used to select or adjust thresholds. The selected thresholds are then applied to the test split for final reporting.

---

## J. Metrics

The following metrics are computed and reported for each model, each threshold tier, and each data split (train, val, test).

| Metric | Description |
|---|---|
| Accuracy | Overall classification accuracy |
| Precision | Precision on attack class |
| Recall | Recall on attack class (TPR) |
| F1 | Harmonic mean of precision and recall |
| FPR | False positive rate (FP / (FP + TN)) |
| ROC-AUC | Area under ROC curve (threshold-independent) |
| PR-AUC | Area under precision-recall curve (threshold-independent) |
| Confusion matrix | TP, FP, TN, FN counts |
| Recall@fixed-FPR | Recall achieved at the fixed-FPR threshold (D10) |

**Per-family breakdown:**
A descriptive (non-primary) breakdown of recall per `coarse_family` is reported for val and test splits. This breakdown is informational only and does not affect model selection.

**Primary model selection metric:** val PR-AUC (used for early stopping and for ranking models in the unified comparison table).

---

## K. Calibration

Calibration (e.g., Platt scaling, temperature scaling, isotonic regression) is **not performed in this phase**.

Model outputs are uncalibrated sigmoid probabilities. All thresholds and metrics in this phase are applied to uncalibrated probabilities.

Calibration is deferred to a later phase. When calibration is eventually applied, it must use val split data only and must not touch test data. The calibrated and uncalibrated results must be reported separately.

---

## L. Invalidation Conditions

Any change to the following invalidates all DL experiment results produced under this protocol. Affected experiments must be re-run from the invalidated stage.

| Change | Invalidates |
|---|---|
| Raw PCAP files modified or replaced | Entire sequence cache and all downstream results |
| Interim flows parquet modified | Sequence cache (direction assignments may change) |
| Master parquet modified | Labels, split assignments, all results |
| Split sidecar modified | Split assignments, all results |
| K (canonical value) changed | Canonical model results |
| Feature set (canonical) changed | Canonical model results |
| Normalization procedure changed | All model results (scaler re-fit required) |
| Model architecture config changed | Corresponding model results |
| `pos_weight` value changed | All model results |
| Random seed changed | All model results (non-determinism) |

When in doubt about whether a change is invalidating, treat it as invalidating and re-run. Do not carry forward results from a prior protocol version into a new one without explicit re-validation.

---

## Appendix: Implementation Notes (Phase 3 Step 3 Complete)

All items below were implemented and executed on 2026-03-23. This appendix records implementation details for audit purposes.

- Packet extraction: `scripts/build_dl_sequences_cicids2017.py` using `dpkt.pcapng.Reader` (~570k pkt/s). All 5 PCAPs processed; 1,901,644 / 1,901,644 flows covered (100%).
- Canonical key matching: bidirectional 5-tuple key defined in `flow_schema.md`; join on `(flow_id, pcap_file)` from interim parquet to recover IP/port fields.
- Sequence cache: `{day}_dl_seq.npz` files at `D:/ids_project_data/processed/cicids2017/dl_sequences/`; shape `(N, 32, 4)` float32.
- Normalization: `StandardScaler` for `signed_packet_len`, `log1p`+`StandardScaler` for `delta_t`; fitted on train non-padded steps; padded positions re-zeroed post-normalization; serialized to `dl_preprocessor.json`.
- Models: `scripts/train_dl_baselines_cicids2017.py`; CNN1D best epoch 3 (val PR-AUC 0.0367), LSTM best epoch 1 (val PR-AUC 0.0096); both use `BCEWithLogitsLoss` pos_weight=36.87.
- Threshold selection: implemented for all 3 tiers; derived from val split only.
- Evaluation: `scripts/eval_dl_baselines_cicids2017.py`; 3 reports generated.
- Ablation: K ∈ {8, 16, 32} × features {A, B}, 15 epochs each; results in `dl_ablation_results.json`.
- Per-family recall breakdown: included in `cicids2017_dl_baseline_main.md`.
- Non-TCP/UDP flows: logged; no fabricated protocol_id assigned.
