# Cross-Domain Transferability of IDS Methods: Final Research Report

> **Datasets:** CIC-IDS2017, IoT-23, UNSW-NB15
> **Scope:** 3 in-domain + 6 cross-domain directions; threshold portability;
>   complementarity; external benign robustness; degradation analysis;
>   multisource transfer; statistical validation

---

## Abstract

We evaluate the cross-domain transferability of rule-based, traditional ML, and deep learning
IDS methods under a unified protocol. All methods receive the same formal input (raw PCAP);
no target-domain labels, thresholds, or scalers are used during cross-domain inference.
Across all 6 directed transfer directions, we find that **threshold portability — not model
discriminability — is the primary deployment bottleneck**. Models retain useful rank-ordering
ability across domains (ROC-AUC > 0.6 in most cases), but score distributions shift so
severely that fixed thresholds fail on 56% of cross-domain evaluations. Logistic Regression
is the most portable method. Random Forest, despite being the strongest in-domain method,
fails completely in all cross-domain directions.

---

## 1. Datasets and Unified Pipeline

### 1.1 Datasets

| Dataset | Environment | Test flows | Attack rate | Split type |
|---------|-------------|-----------|-------------|-----------|
| CIC-IDS2017 | Enterprise LAN simulation | 491,455 | 40.2% | Day-level (Mon–Thu train, Fri test) |
| IoT-23 | IoT honeypot | 12,865 | 57.1% | Scenario-level, **family-disjoint** |
| UNSW-NB15 | IXIA testbed | 122,175 | 5.7% | Temporal (Jan train, Feb test) |

IoT-23 uses a family-disjoint split: training captures contain Mirai botnet traffic only;
test captures contain Torii and Hajime. This makes the in-domain evaluation structurally
harder than a standard i.i.d. split.

### 1.2 Methods

- **Rule-based:** Suricata with ET Open ruleset (CIC-IDS2017 only)
- **Traditional ML:** Logistic Regression (LR), Random Forest (RF), XGBoost (XGB)
  — 19 flow-level features derived from raw PCAP
- **Deep Learning:** 1D-CNN and LSTM
  — packet-level sequences (K=16 packets, 4 features per step)

### 1.3 Evaluation Protocol

Three threshold tiers are evaluated for every method-direction combination:
- **Default (0.5):** no calibration
- **Val-tuned:** threshold that maximizes F1 on source validation set
- **Fixed-FPR:** threshold achieving ≤1% FPR on source validation set

No target-domain information is used. Source preprocessors are applied to target data
without modification.

---

## 2. In-Domain Performance

Performance varies dramatically across datasets due to structural differences:

| Dataset | Best F1 | Best Method | ROC-AUC Range | Primary Challenge |
|---------|---------|-------------|---------------|------------------|
| UNSW-NB15 | **0.830** | RF | 0.96–0.99 | Low imbalance (5.7%); full category overlap |
| IoT-23 | 0.468 | LSTM | 0.61–0.89 | Family-disjoint split (Mirai→Torii/Hajime) |
| CIC-IDS2017 | 0.320 | CNN1D/LSTM | 0.29–0.997 | High imbalance (40%); threshold calibration gap |

CIC-IDS2017's low in-domain F1 despite very high ROC-AUC (CNN1D = 0.997) reveals a
**threshold calibration gap**: models rank attacks correctly but score distributions shift
between training days and test day, so the default threshold fails.

IoT-23's low in-domain F1 is structural: Mirai-trained models memorize Mirai-specific patterns
that do not match Torii/Hajime behavior. This is not a modeling failure.

---

## 3. Cross-Domain Transfer

### 3.1 Performance Matrix

All 6 directed transfer directions, at default threshold:

| Direction | Best F1 | Method | 95% CI | Assessment |
|-----------|---------|--------|--------|------------|
| CIC → IoT | **0.892** | LR | [0.886, 0.897] | Strong transfer |
| UNSW → IoT | **0.860** | LR | [0.853, 0.866] | Strong transfer |
| UNSW → CIC | 0.731 | LR | [0.730, 0.733] | Partial success |
| CIC → UNSW | 0.143 | LR | — | Near-total failure |
| IoT → UNSW | 0.139 | LSTM | — | Near-total failure |
| IoT → CIC | 0.261* | LSTM | — | Near-total failure |

*IoT→CIC LSTM has high seed variance (std=0.149); LR F1=0.086 is the more reliable estimate.

Only 2 of 6 directions achieve F1 > 0.5. Cross-domain degradation is severe and near-universal.

### 3.2 Method Portability

| Method | In-Domain Best | Cross-Domain Best | Portability | Seed Stability |
|--------|----------------|-------------------|-------------|----------------|
| LR | UNSW: F1=0.538 | CIC→IoT: F1=0.892 | **Most portable** (4/6 directions) | Deterministic |
| RF | UNSW: F1=0.830 | All: F1≈0 | **Most brittle** | Deterministic |
| XGB | UNSW: F1=0.816 | UNSW→IoT: F1=0.808 | Brittle except IoT target | Deterministic |
| CNN1D | UNSW: F1=0.826 | UNSW→IoT: F1=0.789 | Score survives; threshold fails | Mostly stable |
| LSTM | UNSW: F1=0.812 | UNSW→CIC: F1=0.631 | Second most portable | Direction-dependent |

LR's advantage over XGB (delta +0.052, UNSW→IoT) and over LSTM in most directions is
statistically significant (p < 0.0001, paired bootstrap, Holm-corrected).

**Exception:** At IoT→CIC, LSTM (F1=0.261) outperforms LR (F1=0.086) at the default
threshold — but this LSTM result has high seed variance and should be treated with caution.

### 3.3 Structural Asymmetries

**IoT asymmetry:** IoT is the easiest target and the worst source.
- CIC→IoT (LR F1=0.892) and UNSW→IoT (LR F1=0.860) both succeed
- IoT→UNSW and IoT→CIC both fail
- Explanation: IoT botnet C&C traffic has recognizable volume/rate signatures from diverse
  source domains. Mirai-trained models learn narrow, botnet-specific boundaries.

**UNSW asymmetry:** UNSW is a hard target and a good source.
- UNSW→CIC (LR F1=0.731) and UNSW→IoT (LR F1=0.860) both succeed
- CIC→UNSW and IoT→UNSW both fail
- Explanation: UNSW's 9-category training creates a broad decision boundary; UNSW's
  laboratory attack traffic (Exploits, Shellcode, Worms) is qualitatively different from
  any source's training distribution.

### 3.4 IoT-23 Paradox

CIC→IoT LR achieves F1=0.892 while IoT in-domain LR achieves only F1=0.061. This reflects
the structural difficulty of IoT's family-disjoint split, not that cross-domain is generically
better. CIC's diverse attack training produces a volume/rate boundary that matches Torii's
C&C traffic. IoT-trained models fail their own test set because the test families (Torii, Hajime)
were absent from training.

---

## 4. Threshold Portability

### 4.1 Summary Statistics

The threshold portability analysis spans 135 rows (3 tiers × 5 methods × all directions):

| Classification | Count | % |
|---------------|-------|---|
| Non-degenerate (F1 > 0) | 83 | 61.5% |
| Degenerate threshold (→ all-benign) | 31 | 23.0% |
| True zero F1 (threshold valid, model fails) | 21 | 15.5% |

**Fixed-FPR degenerates on 56% of cross-domain rows (25/45).** A threshold calibrated to
≤1% FPR on source validation data systematically collapses to all-benign prediction when
applied to a different domain.

Val-tuned thresholds are safer (13% degenerate rate). Default threshold (0.5) never
degenerates — it is the most robust cross-domain choice.

### 4.2 Key Finding: Rank Signal vs. Threshold Collapse

Models retain useful rank-ordering ability even when F1=0 at the default threshold:
- CIC→IoT XGB: ROC-AUC=0.876, F1=0.000 at default
- CIC→IoT LSTM: ROC-AUC=0.921, F1=0.000 at default
- CIC→UNSW CNN1D: ROC-AUC=0.696, F1=0.000 at default

The bottleneck is score distribution shift, not discriminability. Threshold calibration
on a small amount of target data could potentially unlock substantial latent performance.

### 4.3 UNSW→IoT Exception

UNSW→IoT is the only direction where fixed-FPR consistently produces non-degenerate results.
LR val-tuned achieves F1=0.864; all three threshold tiers are usable for UNSW→IoT LR and XGB.

---

## 5. Complementarity and Fusion

When two methods both succeed on a direction, they typically detect the same flows (high
Jaccard overlap). When both fail, they fail on the same attacks. The dominant pattern is
**substitution, not complementarity**.

OR fusion on failed directions catastrophically inflates false positives without recovering
true positives. Score averaging consistently underperforms the best single method due to
calibration mismatch.

**One exception:** CIC→IoT fixed-FPR OR fusion (LR+LSTM) achieves F1=0.848 with FPR=1.4%,
a modest but deployment-relevant improvement. This is the only cross-domain setting with
a fusion gain worth considering in practice.

---

## 6. External Benign Robustness

Models were applied to external benign traffic (hw1/part2.pcap, 2,956 flows, 600 seconds)
to assess false alarm rates in deployment-like conditions.

| Source Model | Method | External FPR | Assessment |
|-------------|--------|--------------|-----------|
| UNSW-trained | LR (default) | **37%** | Deployment risk |
| CIC-trained | CNN1D / LSTM | ~0% | Safe |
| IoT-trained | LR / DL | Low | Acceptable |

The false alarm rate is **source-dependent**, not model-quality-dependent. UNSW-trained LR
achieves strong in-domain performance (F1=0.538) but 37% FPR on external benign traffic.
CIC-trained DL models have lower in-domain F1 but near-zero FPR on the same external set.

High in-domain performance does not guarantee low false alarms in real deployment.
Source training environment must match deployment context.

*Note: This analysis is based on a single 600-second external PCAP. FPR estimates are
descriptive for this specific traffic sample.*

---

## 7. Degradation Mechanisms

Two structurally distinct degradation modes were identified:

### Mode 1: Rank Signal Preserved, Threshold Collapses
- Examples: CIC→IoT XGB/LSTM; IoT→CIC LR/XGB
- ROC-AUC remains above 0.8; F1=0 at default threshold
- Cause: Positive-class score distributions shift downward on target
  (e.g., IoT→CIC: mean positive score = 0.021; default threshold = 0.5)
- Feature KS drift: moderate (< 0.3 for most features)
- **Intervention:** Threshold recalibration on a small amount of target data may help

### Mode 2: Rank Signal Collapses
- Examples: IoT→UNSW all methods; UNSW→CIC CNN1D/XGB
- ROC-AUC near chance; no threshold adjustment helps
- Primary driver for IoT→UNSW: Δt feature KS=0.558 (Mirai's repetitive C&C timing
  is qualitatively unlike UNSW's protocol attack timing)
- **Intervention:** Requires source retraining or domain adaptation

**Practical diagnostic:** Check ROC-AUC first. ROC-AUC > 0.6 → try threshold recalibration
(Mode 1). ROC-AUC near random → the model needs retraining (Mode 2).

---

## 8. Multisource Transfer

Three two-source training configurations were evaluated:

| Direction | Best gain | Tier |
|-----------|-----------|------|
| IoT+UNSW → CIC | LR val-tuned: +0.062 [0.062, 0.063] | Statistically certified |
| IoT+UNSW → CIC | XGB val-tuned: +0.083 [0.082, 0.084] | Statistically certified |
| CIC+IoT → UNSW | LR val-tuned: +0.032 [0.060, 0.071] | Significant but small |
| CIC+UNSW → IoT | LSTM fixed-FPR: +0.055 [0.041, 0.068] | Narrow but real |

When source datasets are balanced in size (IoT+UNSW→CIC), two-source diversity provides
genuine complementary signal. When one source dominates by size (CIC+UNSW→IoT, where CIC
has 90% of training data), the combined model approximately equals the large source alone.

Multisource gains are direction-, method-, and tier-specific — not a general solution to
cross-domain degradation.

---

## 9. Statistical Robustness

### 9.1 Bootstrap Confidence Intervals
Nonparametric bootstrap (n=1000, 95% percentile method). Stratified subsampling (n=5,000)
for ROC-AUC and PR-AUC on the large CIC test set.

### 9.2 DL Seed Stability

DL models were retrained with seeds 42, 43, 44 to assess initialization sensitivity:

| Context | Architecture | F1 std | Assessment |
|---------|-------------|--------|------------|
| CIC in-domain | CNN1D / LSTM | < 0.002 | Very stable |
| UNSW→IoT | LSTM | **0.184** | Highly unstable; range 0.44–0.80 |
| IoT→CIC | LSTM | **0.149** | Highly unstable; range 0.03–0.27 |
| UNSW→CIC | CNN1D | 0.042 | Unstable |

Results with F1 std > 0.1 should not be cited as point estimates.

### 9.3 Significance Testing
33 paired bootstrap comparisons (Holm-corrected). All 18 in-domain vs cross-domain
comparisons are significant (p < 0.0001). All 4 key multisource gains are significant.
Zero semantic conflicts between p-values and confidence intervals.

### 9.4 Confidence Tiers
23 key claims are rated in `confidence_summary.csv`:
14 Tier 1 (high), 6 Tier 2 (moderate), 3 Tier 3 (caution required).

---

## 10. Practical Recommendations

### Viable Cross-Domain Deployments

| Source → Target | Recommended Method | F1 |
|----------------|-------------------|-----|
| CIC → IoT | LR | 0.892 [0.886, 0.897] |
| UNSW → IoT | LR or XGB (avoid LSTM) | 0.860 [0.853, 0.866] |
| UNSW → CIC | LR + val-tuned threshold | 0.731 [0.730, 0.733] |

CIC→UNSW, IoT→UNSW, and IoT→CIC all fail without target-domain adaptation.

### Threshold Strategy
- Default (0.5): use as safe fallback when no target data is available
- Val-tuned: preferred when a small held-out validation set is acceptable
- Fixed-FPR: avoid cross-domain; 56% degenerate rate

### Model Selection
- LR first: most portable, deterministic, no seed uncertainty
- XGB: competitive on IoT-target directions only
- RF: never for cross-domain despite strong in-domain performance
- LSTM: verify seed stability for your specific direction before deploying

---

## 11. Limitations and Future Work

### Current Limitations
- Suricata evaluated on CIC only (binary unavailable for IoT/UNSW)
- IoT-23 uses a family-disjoint split; in-domain metrics reflect this structural choice
- UNSW-NB15 uses a 12-file subset (of 80 available)
- 19 flow features only
- No threshold calibration transfer attempted

### Future Directions
1. Threshold calibration transfer (Platt scaling, temperature scaling)
2. Domain adaptation for Mode 2 failure cases
3. Balanced multisource training (dataset weighting)
4. Expanded IoT-23 coverage (additional scenarios)
5. Richer feature representations (80+ features)
6. Attention-based sequence models

---

## 12. Companion Data

| Content | File |
|---------|------|
| Core results (46 rows, with confidence tiers) | `final_results_master_table.csv` |
| Threshold portability (135 rows, 3 tiers) | `final_threshold_portability_table.csv` |
| Threshold classification labels | `final_threshold_portability_classification.csv` |
| Bootstrap CI (105 rows, n=1000) | `final_bootstrap_ci_results.csv` |
| Significance tests (33 rows) | `final_significance_tests.csv` |
| DL seed stability (192 rows) | `final_dl_seed_stability_results.csv` |
| Complementarity matrix | `final_complementarity_matrix.csv` |
| Fusion strategy results | `final_lightweight_fusion_results.csv` |
| External benign metrics | `final_out_of_domain_benign_metrics.csv` |
| Feature drift summary | `final_feature_drift_summary.csv` |
| Multisource transfer results | `final_multisource_transfer_results.csv` |
| Project summary (7 sections) | `project_summary_table.csv` |
| Confidence tier map (23 claims) | `confidence_summary.csv` |

All files are in `reports/final/`. Figures are in `reports/figures/final/`.
