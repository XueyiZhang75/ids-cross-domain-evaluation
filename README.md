# Cross-Domain Transferability of IDS Methods from Raw PCAP

A systematic evaluation of intrusion detection methods under unified cross-domain conditions —
measuring how well models trained on one network environment generalize to another.

---

## 1. What This Project Studies

Modern IDS deployments face a fundamental challenge: models trained on one network's traffic
may not detect attacks in a different environment. This project evaluates that challenge
empirically across three real-world datasets, asking:

1. How do rule-based, ML, and deep learning IDS methods compare under a unified protocol?
2. How severely does cross-domain transfer degrade detection performance?
3. Is threshold portability a first-order deployment problem?
4. Which methods transfer best across domains, and why?
5. Does training on multiple source domains improve cross-domain detection?
6. How statistically robust are these findings?

---

## 2. Datasets

| Dataset | Source | Environment | Test size |
|---------|--------|-------------|-----------|
| **CIC-IDS2017** | University of New Brunswick | Enterprise LAN simulation | 491,455 flows (40.2% attack) |
| **IoT-23** | CTU / Stratosphere Lab | IoT honeypot captures | 12,865 flows (family-disjoint split) |
| **UNSW-NB15** | UNSW Sydney | IXIA PerfectStorm testbed | 122,175 flows (5.7% attack) |

All three datasets use a **formal train/val/test split** with no target-domain leakage.
The raw PCAP is the formal input to every stage of the pipeline.

---

## 3. Methods

| Paradigm | Methods |
|----------|---------|
| Rule-based | Suricata (ET Open ruleset; CIC only) |
| Traditional ML | Logistic Regression (LR), Random Forest (RF), XGBoost (XGB) |
| Deep Learning | 1D-CNN, LSTM (packet-level sequences, K=16) |

**19 canonical flow-level features** are derived from raw PCAP:
duration, packet counts, byte counts, protocol flags, rate features, and directional ratios.

**DL sequences:** K=16 packets per flow, 4 features per step (length, direction, Δt, protocol).

---

## 4. Unified Pipeline

```
Raw PCAP
  └─► Flow extraction (src/data_ingestion/)
       └─► 19-feature matrix  ──► ML models (LR / RF / XGB)
       └─► Packet sequences   ──► DL models (CNN1D / LSTM)
                                     └─► Evaluation: F1, ROC-AUC, PR-AUC
                                     └─► Threshold analysis: default / val-tuned / fixed-FPR
```

No target-domain labels, thresholds, or scalers are used in any cross-domain evaluation.

---

## 5. Key Findings

### Cross-Domain Performance (default threshold)

| Direction | Best F1 | Method | 95% CI |
|-----------|---------|--------|--------|
| CIC → IoT | **0.892** | LR | [0.886, 0.897] |
| UNSW → IoT | **0.860** | LR | [0.853, 0.866] |
| UNSW → CIC | 0.731 | LR | [0.730, 0.733] |
| CIC → UNSW | 0.143 | LR | — |
| IoT → UNSW | 0.139 | LSTM | — |
| IoT → CIC | 0.261* | LSTM | — |

*IoT→CIC LSTM result has high seed variance (std=0.149); LR F1=0.086 is more reliable.

### Core Conclusions

1. **Threshold portability is the primary deployment bottleneck.** Models retain discriminative
   ability across domains (ROC-AUC > 0.6 in most cases) but score distributions shift so
   severely that fixed thresholds fail. The fixed-FPR threshold degenerates on 56% of
   cross-domain evaluations.

2. **Logistic Regression is the most portable method.** Best cross-domain F1 in 4 of 6
   directions; advantages over XGB and LSTM are statistically significant (p < 0.0001).

3. **Random Forest is brittle cross-domain** despite being the strongest in-domain method
   (UNSW F1 = 0.830). Near-zero cross-domain F1 in all 6 directions.

4. **IoT is the easiest target, the worst source.** CIC→IoT and UNSW→IoT both succeed;
   IoT→UNSW and IoT→CIC both fail. The asymmetry is stable and statistically confirmed.

5. **Multisource training provides real but direction-specific gains.** IoT+UNSW→CIC LR
   val-tuned: +0.062 F1 (certified, p < 0.0001). CIC-dominated mixtures show no improvement.

6. **Some DL results are seed-unstable.** UNSW→IoT LSTM (seed std = 0.184) and IoT→CIC
   LSTM (seed std = 0.149) are not reliable point estimates.

---

## 6. Results Navigation

| What to read | File |
|-------------|------|
| **Main report** (complete findings) | `reports/final/main_report.md` |
| Core results table (46 rows + confidence tiers) | `reports/final/final_results_master_table.csv` |
| Threshold portability analysis | `reports/final/threshold_portability.md` |
| Attack family transfer patterns | `reports/final/family_transfer.md` |
| Method complementarity and fusion | `reports/final/complementarity.md` |
| External benign false-alarm robustness | `reports/final/external_benign_robustness.md` |
| Degradation source analysis | `reports/final/degradation_mechanisms.md` |
| Multi-source transfer results | `reports/final/multisource_transfer.md` |
| Statistical robustness (bootstrap CI, seed stability) | `reports/final/statistical_robustness.md` |
| Summary table (7 sections) | `reports/final/project_summary_table.csv` |
| Confidence tier map (23 claims) | `reports/final/confidence_summary.csv` |
| Final figures (11 PNG) | `reports/figures/final/` |

---

## 7. Repository Structure

```
.
├── README.md
├── requirements.txt
├── DECISIONS.md                   # Design decisions D1–D16
├── configs/                       # YAML configuration
├── src/                           # Pipeline library code
│   ├── data_ingestion/            #   PCAP → flow extraction
│   ├── labeling/                  #   Label loading and join
│   ├── features/                  #   19-feature extraction
│   ├── evaluation/                #   Threshold analysis
│   └── models_ml/                 #   ML training utilities
├── scripts/
│   ├── cicids2017/                # CIC processing and evaluation
│   ├── iot23/                     # IoT processing and evaluation
│   ├── unsw_nb15/                 # UNSW processing and evaluation
│   ├── shared/                    # Dataset-agnostic utilities
│   ├── final/                     # Figure generation
│   └── phase6/                    # Statistical robustness scripts
├── reports/
│   ├── final/                     # ← Main results (start here)
│   ├── figures/final/             # 11 final figures (PNG, 300 DPI)
│   ├── cicids2017/                # CIC per-experiment reports
│   ├── iot23/                     # IoT per-experiment reports
│   ├── unsw_nb15/                 # UNSW per-experiment reports
│   └── predictions/               # Cross-domain prediction sidecars
└── docs/
    ├── flow_schema.md             # Flow feature schema
    ├── label_schema.md            # Label taxonomy
    ├── split_protocol.md          # Split protocol
    └── internal/                  # Process history and audit artifacts
```

Large files (raw PCAP, processed parquet, trained models) live outside the repository at
`<external_data_root>/`. Paths are configured in `configs/datasets.yaml`.

---

## 8. Reproducing Results

### In-Domain Baselines

```bash
# CIC-IDS2017
python scripts/cicids2017/train_ml_baselines_cicids2017.py
python scripts/cicids2017/train_dl_baselines_cicids2017.py

# IoT-23
python scripts/iot23/train_ml_baselines_iot23.py
python scripts/iot23/train_dl_baselines_iot23.py

# UNSW-NB15
python scripts/unsw_nb15/train_ml_baselines_unsw_nb15.py
python scripts/unsw_nb15/train_dl_baselines_unsw_nb15.py
```

### Cross-Domain Evaluation

```bash
python scripts/iot23/eval_iot23_cross_domain.py        # CIC→IoT, UNSW→IoT
python scripts/unsw_nb15/run_unsw_cross_domain.py      # remaining 4 directions
```

### Figures

```bash
python scripts/final/generate_final_figures.py
# Output: reports/figures/final/ (11 PNG, 300 DPI)
```

### Statistical Robustness

```bash
python scripts/phase6/run_phase6b_patch.py             # Bootstrap CI + significance
```

---

## 9. Limitations

- Suricata evaluated on CIC-IDS2017 only (binary unavailable for IoT/UNSW)
- IoT-23 uses a family-disjoint split (Mirai train, Torii/Hajime test); in-domain F1 is structurally low
- UNSW-NB15 uses a 12-file subset (of 80 available)
- 19 flow features only; richer feature sets may differ
- No threshold calibration transfer attempted (Platt scaling, temperature scaling)
- UNSW→IoT LSTM and IoT→CIC LSTM results have high seed variance — interpret with caution

---

## 10. Formal Input and Transfer Constraints

> **Every pipeline stage takes raw PCAP as its formal input.**
> Public label CSVs are used only as references for flow-label joining.

All cross-domain experiments follow a strict transfer discipline:
no target-domain model fitting, threshold selection, scaler refit, or label access.

---

*Development history and internal audit artifacts are archived under `docs/internal/`.*
*A deferred IoT v2 side-branch exists in internal history but is not part of the canonical result chain.*
