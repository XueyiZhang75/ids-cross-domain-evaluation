# Threshold Portability — Cross-Dataset Synthesis

> **Scope:** All in-domain + 6 cross-domain directions (all pairs)
> **Companion data:** `final_threshold_portability_table.csv` (135 rows: 45 in-domain + 90 cross-domain)

---

## 1. Summary Finding

**Threshold portability is a first-order problem across all three datasets and all method families.**

No single threshold selection strategy—default, val_tuned, or fixed_fpr—consistently produces usable performance when transferred from a source domain to a target domain. This is not a failure of any individual model, but a structural property of cross-domain IDS evaluation.

The **135-row portability table** covers 45 rows per threshold tier (default / val_tuned / fixed_fpr) across 15 in-domain method-dataset combinations and 30 cross-domain method-direction combinations (6 directions × 5 methods). All three tiers are present for all 6 directions.

---

## 2. Three-Way Row Classification

Every row in the portability table falls into one of three categories:

| Classification | Count | Fraction | Definition |
|----------------|-------|----------|------------|
| **observed_nonzero** | 83 | 61.5% | F1 > 0 with a non-degenerate threshold |
| **degenerate_threshold** | 31 | 23% | Threshold ≈ 1.0, model predicts all-benign |
| **observed_true_zero** | 21 | 15.5% | Non-degenerate threshold but F1 = 0 (true failure) |

The 31 degenerate rows are split across tiers (45 rows each, all six transfer directions):
- **fixed_fpr:** 25 of 45 rows degenerate (56% of cross-domain rows)
- **val_tuned:** 6 of 45 rows degenerate (13% of cross-domain rows; IoT→CIC XGB val_tuned is one such case)
- **default:** 0 of 45 rows degenerate (0%)

**UNSW→IoT exception:** UNSW→IoT is the only cross-domain direction where fixed_fpr does not universally degenerate. LR and XGB val_tuned achieve meaningful F1 (0.864, 0.815) — the only cross-domain direction where val_tuned succeeds reliably.

---

## 3. Fixed-FPR Degeneracy

The fixed_fpr tier (1% FPR budget on source val) degenerates to threshold ≈ 1.0 (effectively all-benign prediction) in **17 of 35 rows (49%)**:

| Source | In-Domain Degenerate | Cross-Domain Degenerate |
|--------|---------------------|------------------------|
| CIC-IDS2017 | 0/5 | 0 (CIC thresholds are non-degenerate) |
| IoT-23 | 4/5 (LR, RF, XGB, CNN1D) | 4/5 IoT→UNSW (LR, RF, XGB, CNN1D) |
| UNSW-NB15 | 5/5 (all methods) | 4/5 UNSW→CIC (LR, RF, XGB, CNN1D) |

When a non-degenerate fixed_fpr threshold exists (e.g., CIC RF: 0.005, CIC CNN1D: 0.122) and is transferred to other domains:
- CIC RF fixed_fpr (0.005) → IoT: F1=0.57, FPR=0.08 (partially useful)
- CIC RF fixed_fpr (0.005) → UNSW: F1=0.14, FPR=0.26 (degraded)
- CIC CNN1D fixed_fpr (0.122) → IoT: F1=0.06, FPR=0.04 (poor)

Even non-degenerate source thresholds fail to maintain ≤1% FPR on target domains.

---

## 4. Val-Tuned Degeneracy

The val_tuned tier degenerates in **5 of 35 rows (14%)**. All 5 originate from CIC LR's degenerate val_tuned threshold of 1.0, which propagates to its cross-domain applications (CIC→IoT LR, CIC→UNSW LR).

Val_tuned degeneracy is far less common than fixed_fpr degeneracy because val_tuned optimizes F1 on the source validation set, which typically finds a useful operating point even when the FPR-based criterion cannot.

---

## 5. Default Threshold (0.5) Behavior

The default threshold produces **0 degenerate rows**. Its usefulness varies dramatically by setting:

### In-Domain
| Dataset | Best F1 (default) | Worst F1 (default) | Pattern |
|---------|-------|--------|---------|
| CIC | 0.320 (CNN1D/LSTM) | 0.074 (RF) | Consistently low F1 despite high ROC; threshold calibration issue |
| IoT | 0.468 (LSTM) | 0.002 (RF) | Family-disjoint test; most models fail |
| UNSW | 0.830 (RF) | 0.538 (LR) | Strong default performance; best-calibrated dataset |

### Cross-Domain
| Direction | Best F1 (default) | Result |
|-----------|-------|--------|
| CIC→IoT | 0.892 (LR) | **Anomalous success** — CIC LR generalizes to IoT |
| UNSW→CIC | 0.731 (LR) | **Partial success** — UNSW LR generalizes to CIC |
| CIC→UNSW | 0.143 (LR) | Near-total collapse |
| IoT→UNSW | 0.139 (LSTM) | Near-total collapse |

**Observation:** LR at default threshold is the most portable method, but this reflects its simpler decision boundary rather than better feature learning.

---

## 6. Val-Tuned Threshold Transfer

Source val_tuned thresholds almost never improve cross-domain F1:

| Direction | Method | Source val_tuned | Target F1 (val_tuned) | Target F1 (default) | Better? |
|-----------|--------|-----------------|----------------------|--------------------|----|
| CIC→IoT | LR | 1.0 | 0.002 | 0.892 | No |
| CIC→UNSW | RF | 0.036 | 0.071 | 0.000 | Yes (from zero) |
| UNSW→CIC | LR | 0.799 | 0.740 | 0.731 | Marginal |
| UNSW→CIC | LSTM | 0.900 | 0.720 | 0.631 | Yes |

In only 2/20 cases does val_tuned meaningfully help on the target domain. This is expected: val_tuned optimizes for a source-specific score distribution.

---

## 7. Cross-Domain Coverage

The portability table has complete threshold-tier coverage for all 4 completed cross-domain directions:

| Direction | default | val_tuned | fixed_fpr | Total rows |
|-----------|---------|-----------|-----------|------------|
| CIC→IoT | 5 | 5 | 5 | 15 |
| CIC→UNSW | 5 | 5 | 5 | 15 |
| IoT→UNSW | 5 | 5 | 5 | 15 |
| UNSW→CIC | 5 | 5 | 5 | 15 |
| **Cross-domain total** | 20 | 20 | 20 | **60** |

Combined with 45 in-domain rows (15 method-dataset combinations × 3 tiers), this yields the full 105-row table.

---

## 8. Formal Conclusions

1. **Threshold portability is a first-order problem**: Score calibration shifts under domain transfer are so large that no source-selected threshold reliably works on a target domain.

2. **fixed_fpr is the most failure-prone strategy**: It degenerates on 17/35 rows (49%), and even non-degenerate thresholds produce uncontrolled FPR on target domains.

3. **val_tuned degenerates less often (5/35, 14%)** but still rarely transfers usefully to a target domain.

4. **Default threshold (0.5) is the least-bad cross-domain option**: It never degenerates and at least sometimes produces non-zero recall, even though it is calibration-unaware.

5. **Rank-ordering signal (ROC-AUC) survives where threshold-dependent metrics (F1) collapse**: This is the clearest evidence that threshold portability, not feature quality, is the primary cross-domain bottleneck.
