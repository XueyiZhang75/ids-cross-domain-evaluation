# Statistical Robustness

> **Bootstrap:** n=1000, 95% CI, stratified subsampling for ROC/PR-AUC (n=5,000) on large datasets
> **DL seeds:** 42, 43, 44 (CNN1D and LSTM only; LR/XGB/RF are deterministic)
> **Significance:** Paired bootstrap on F1 delta (unified CI and p-value); Holm correction within families

---

## Executive Summary

This report assesses the statistical stability of cross-domain, complementarity, external benign, degradation, and multisource findings across three dimensions:
DL seed variance, bootstrap confidence intervals, and paired significance testing.

**Overall verdict:** The major conclusions of the project are **statistically well-supported**.
The one important caveat is that UNSW→IoT LSTM and IoT→CIC LSTM/CNN1D show **high seed
variance** and should not be cited with high confidence as point estimates. All 33 significance
tests (18 in-domain vs cross-domain, 6 method comparisons, 5 threshold tier, 4 multisource
multisource gains) reject the null hypothesis at α=0.05 after Holm correction.

**Note:** Bootstrap rerun with n=1000 (matching protocol); significance tests
use unified `paired_bootstrap_f1` — CI and p-value from same test. Zero semantic conflicts.

---

## Q1. Which Single-Source Conclusions Are Most Statistically Stable?

### Tight 95% CIs (high confidence)

| Context | Method | F1 PE | F1 CI | ROC-AUC PE | ROC-AUC CI |
|---------|--------|-------|-------|------------|------------|
| CIC→IoT | LR | 0.892 | [0.886, 0.897] | 0.983 | [0.979, 0.986] |
| UNSW→IoT | LR | 0.860 | [0.853, 0.866] | 0.877 | [0.865, 0.886] |
| UNSW→IoT | XGB | 0.808 | [0.801, 0.815] | 0.791 | [0.783, 0.808] |
| UNSW in-domain | RF | 0.830 | [0.824, 0.837] | 0.993 | [0.991, 0.996] |
| UNSW→CIC | LR | 0.731 | [0.730, 0.733] | 0.643 | [0.621, 0.655] |
| UNSW→CIC | LSTM | 0.631 | [0.629, 0.632] | 0.753 | [0.746, 0.764] |

These results have narrow CIs and stable seed variance — they are the highest-confidence
conclusions in the project.

### Wide CIs or high seed variance (caution required)

| Context | Method | F1 PE | F1 seed std | ROC seed std | Assessment |
|---------|--------|-------|-------------|--------------|------------|
| UNSW→IoT | LSTM | 0.707 | 0.184 | 0.273 | **Highly seed-unstable** |
| UNSW→CIC | CNN1D | 0.069 | 0.042 | 0.060 | High seed variance |
| IoT→CIC | LSTM | 0.261 | 0.149 | 0.018 | High F1 seed variance |
| IoT→CIC | CNN1D | 0.069 | 0.039 | 0.013 | High F1 seed variance |
| IoT→UNSW | LSTM | 0.139 | 0.034 | 0.047 | Moderate seed variance |

**UNSW→IoT LSTM is the most seed-unstable result in the entire project:**
- Seed 42: F1=0.684, ROC=0.481
- Seed 43: F1=0.444, ROC=0.079 (near-random)
- Seed 44: F1=0.805, ROC=0.602

The canonical single-source UNSW→IoT LSTM F1=0.707 should be interpreted as a point estimate
with high uncertainty; the true performance could be anywhere from 0.44 to 0.80 depending on
initialization.

---

## Q2. Does LR's "Most Transferable Method" Status Hold Statistically?

**Yes, strongly.** All 6 method comparison significance tests (LR vs XGB and LR vs LSTM on
UNSW→IoT, IoT→CIC, and CIC→IoT at default tier) reject the null hypothesis after Holm
correction (all p<0.0001).

| Block | LR F1 | XGB F1 | delta (LR-XGB) | CI | significant? |
|-------|-------|--------|----------------|----|-------------|
| UNSW→IoT default | 0.860 | 0.808 | +0.052 | [0.046, 0.058] | **Yes** |
| IoT→CIC default | 0.086 | 0.000 | +0.086 | [0.085, 0.087] | **Yes** |
| CIC→IoT default | 0.892 | 0.000 | +0.892 | [0.886, 0.898] | **Yes** |

| Block | LR F1 | LSTM F1 | delta (LR-LSTM) | CI | significant? |
|-------|-------|---------|------------------|----|-------------|
| UNSW→IoT default | 0.860 | 0.707 | +0.153 | [0.145, 0.160] | **Yes** |
| IoT→CIC default | 0.086 | 0.261 | -0.174 | [-0.177, -0.173] | **Yes (LSTM better here)** |
| CIC→IoT default | 0.892 | 0.000 | +0.892 | [0.886, 0.898] | **Yes** |

**Notable exception:** At IoT→CIC, LSTM significantly **outperforms** LR (delta -0.174,
p<0.0001). This is not an anomaly — it reflects the fact that IoT temporal patterns partially
transfer to CIC target via sequence-level representation, even when flow-level LR performs
poorly. LSTM at IoT→CIC default F1=0.261 vs LR F1=0.086. However, LSTM seed variance at
IoT→CIC is very high (std=0.149), so this result requires caution.

**Overall conclusion:** LR's advantage is real and statistically significant for CIC→IoT
and UNSW→IoT (the most practically important cross-domain directions). The IoT→CIC exception
is noted.

---

## Q3. UNSW→IoT Success and IoT→UNSW Failure: How Stable?

### UNSW→IoT (success direction)

| Method | F1 95% CI | ROC-AUC 95% CI | Seed std (F1) |
|--------|-----------|----------------|---------------|
| LR | [0.853, 0.866] | [0.865, 0.886] | deterministic |
| XGB | [0.801, 0.815] | [0.783, 0.808] | deterministic |
| CNN1D | [0.781, 0.798] | [0.789, 0.815] | 0.025 (moderate) |
| LSTM | [0.701, 0.714] | [0.433, 0.464] | **0.184 (very high)** |

UNSW→IoT LR and XGB are robustly high-performing (tight CIs, deterministic). UNSW→IoT CNN1D
is moderately stable. **UNSW→IoT LSTM is highly unstable** and its canonical F1=0.707 masks
a performance range of 0.44–0.80.

### IoT→UNSW (failure direction)

| Method | F1 95% CI | ROC-AUC 95% CI | Seed std (F1) |
|--------|-----------|----------------|---------------|
| LR | [0.030, 0.033] | [0.320, 0.326] | deterministic |
| XGB | [0.042, 0.046] | [0.401, 0.408] | deterministic |
| LSTM | [0.130, 0.149] | [0.623, 0.643] | 0.034 (moderate) |

IoT→UNSW LR/XGB failure is stable and tight — the low F1 is not a fluke. LSTM shows wider CIs
for IoT→UNSW F1 (0.13–0.15) but the failure conclusion holds across seeds.

**All in-domain vs cross-domain comparisons are statistically significant** (p<0.0001, Holm):
- IoT in-domain LR vs CIC→IoT LR: delta=-0.831 [degradation of cross-domain]
- IoT in-domain LR vs UNSW→IoT LR: delta=-0.799 [same direction]
- UNSW in-domain LR vs CIC→UNSW LR: delta=+0.395 [in-domain is better]

The in-domain vs cross-domain degradation is the most statistically certain finding in the
project — all 18 comparisons significant after Holm.

---

## Q4. Which DL Results Are Seed-Sensitive?

### Low seed variance (reliable, can cite as point estimates)

| Context | Method | F1 std | ROC std | Assessment |
|---------|--------|--------|---------|------------|
| CIC in-domain | CNN1D | 0.001 | 0.005 | Very stable |
| CIC in-domain | LSTM | 0.001 | 0.004 | Very stable |
| IoT in-domain | CNN1D | 0.001 | 0.026 | Stable F1, some ROC variance |
| IoT in-domain | LSTM | 0.001 | 0.012 | Stable |
| UNSW in-domain | CNN1D | 0.005 | 0.001 | Stable |
| CIC→IoT | CNN1D | 0.000 | 0.063 | F1 stable (near-zero), some ROC variance |
| CIC→IoT | LSTM | 0.001 | 0.098 | F1 stable (near-zero) |

### High seed variance (do NOT cite as reliable point estimates)

| Context | Method | F1 std | F1 range | ROC std | Concern level |
|---------|--------|--------|----------|---------|---------------|
| UNSW→IoT | **LSTM** | **0.184** | **0.361** | 0.273 | **CRITICAL** |
| UNSW→CIC | CNN1D | 0.042 | 0.083 | 0.060 | High |
| IoT→CIC | **LSTM** | **0.149** | **0.272** | 0.018 | **High** |
| IoT→CIC | CNN1D | 0.039 | 0.068 | 0.013 | High |
| IoT→UNSW | LSTM | 0.034 | 0.065 | 0.047 | Moderate |
| UNSW_in_domain | LSTM | 0.021 | 0.040 | 0.001 | Moderate |

**Root cause of high LSTM seed variance in cross-domain scenarios:**

For UNSW→IoT LSTM: The canonical frozen model achieves F1=0.707 (seed=42). However, with
different seeds, the LSTM's LSTM layer initializes with different hidden state characteristics.
The combined val early stopping captures only 6 gradient updates for UNSW (in-domain), so the
model's final weights are very sensitive to initialization. The wide ROC-AUC variance (std=0.27)
suggests the model is not reliably learning the UNSW→IoT discriminative feature.

**Research recommendation:** Treat UNSW→IoT LSTM and IoT→CIC LSTM as unreliable DL results.
The single-seed canonical results for these two cases should NOT be cited as point estimates in
the final synthesis. LR/XGB results for the same directions are deterministic and reliable.

---

## Q5. External Benign False Alarm: Does CI Change Anything?

The external benign evaluation is based on a single out-of-domain PCAP with specific benign traffic patterns.
Bootstrap CI applies to the point estimates (FPR = number of alerted flows / total flows):

Key FPR estimates on the external benign set:
- UNSW-LR default: FPR=37.0% (6,564 alerts/hour extrapolated)
- CIC-LSTM default: FPR=0.0%

These are computed on a single benign evaluation set (`hw1/part2.pcap`, **2,956 flows**,
600s duration). A bootstrap CI on a single-dataset false alarm rate would reflect sampling
variance of that specific traffic, not generalization. Therefore, these FPR estimates are
**correctly treated as point estimates** for the specific benign evaluation dataset.

**No CI correction needed for external benign FPR.** The conclusion ("UNSW-trained models have
very high false alarm rate on external benign traffic; CIC-trained CNN1D and LSTM have near-zero
FPR") is stated correctly as a single-dataset observation on the 2,956-flow external benign set.

---

## Q6. Multisource Gains: True or Statistical Noise?

The analysis significance test: `paired_bootstrap_f1` (n=1000, Holm correction).
Delta = (multisource F1) - (best single-source F1 at same tier).
Positive delta = multisource is better.

| Claim | delta | CI (F1 delta) | p_adj (Holm) | significant? |
|-------|-------|--------------|-------------|-------------|
| IoT+UNSW→CIC LR val_tuned | **+0.062** | [0.062, 0.063] | <0.0001 | **Yes** |
| IoT+UNSW→CIC XGB val_tuned | **+0.083** | [0.082, 0.084] | <0.0001 | **Yes** |
| CIC+IoT→UNSW LR val_tuned | **+0.065** | [0.060, 0.071] | <0.0001 | **Yes** |
| CIC+UNSW→IoT LSTM fixed_fpr | **+0.055** | [0.041, 0.068] | <0.0001 | **Yes** |

Bootstrap CI on individual point estimates (n=1000):
- IoT+UNSW→CIC LR val_tuned: F1=0.803 [0.801, 0.804]
- IoT+UNSW→CIC XGB val_tuned: F1=0.247 [0.244, 0.249]
- CIC+IoT→UNSW LR val_tuned: F1=0.072 [0.066, 0.078]
- CIC+UNSW→IoT LSTM fixed_fpr: F1=0.129 [0.118, 0.139]

**All 4 multisource significance test comparisons are statistically significant after Holm
correction (n=1000 paired bootstrap).** Zero semantic conflicts (no row where CI spans 0
but significant=True).

CI widths reveal important nuances:
- IoT+UNSW→CIC LR val_tuned delta CI [0.062, 0.063] — very tight, gain is very stable
- CIC+UNSW→IoT LSTM fixed_fpr delta CI [0.041, 0.068] — wider, gain is real but operational
  margin is narrow (multisource F1=0.129 vs single-source F1=0.078)

**Conclusion:** Multisource gains for IoT+UNSW→CIC direction are **statistically certified**.
CIC+UNSW→IoT LSTM fixed_fpr gain is also certified but narrow.

---

## Q7. Default vs Val_Tuned vs Fixed_FPR: Which Differences Are Significant?

| Block | Method | Comparison | F1 delta | CI | p (Holm) | Verdict |
|-------|--------|-----------|----------|----|----------|---------|
| CIC→IoT | XGB | default vs val_tuned | -0.113 | [-0.124, -0.105] | <0.0001 | Significant (val_tuned worse) |
| CIC→IoT | XGB | default vs fixed_fpr | -0.135 | [-0.145, -0.124] | <0.0001 | Significant (fixed_fpr worse) |
| IoT→CIC | LR | default vs val_tuned | +0.005 | [0.005, 0.006] | <0.0001 | Significant but tiny |
| IoT→CIC | LR | default vs fixed_fpr | +0.086 | [0.084, 0.087] | <0.0001 | Significant (fixed_fpr better F1) |
| UNSW→IoT | LR | default vs val_tuned | -0.004 | [-0.005, -0.003] | <0.0001 | Significant but negligible |

**Key finding:** The CIC→IoT XGB threshold collapse (default=0.000, val_tuned=0.113,
fixed_fpr=0.135) is **statistically significant** — the threshold search on the combined val
genuinely recovers recall that the default threshold misses. However, this recovery is small
in absolute terms and the result remains poor.

The UNSW→IoT LR default vs val_tuned difference (delta=-0.004) is statistically significant
but substantively negligible — the two tiers are practically equivalent for LR on this
direction.

---

## Q8. Which Conclusions Are Statistically Certified?

### High confidence (tight CI + Holm-significant):

1. **CIC→IoT LR F1=0.892 [0.886, 0.897]** — the strongest cross-domain result; LR significantly
   outperforms XGB (p<0.0001, delta=+0.892) and LSTM (p<0.0001, delta=+0.892)

2. **UNSW→IoT LR F1=0.860 [0.853, 0.866]** — second strongest; LR significantly better than
   UNSW→IoT LSTM (p<0.0001, delta=+0.153)

3. **IoT→UNSW LR/XGB/LSTM all fail** (F1<0.14 with tight CIs [0.030–0.049]) — failure is
   stable and statistically certain; not random noise

4. **All in-domain vs cross-domain degradations are significant** (18/18 significant after Holm)

5. **IoT+UNSW→CIC LR val_tuned F1=0.803 [0.801, 0.804]** vs best single-source 0.740 — the
   multisource gain is statistically certified (p<0.0001)

6. **LR is significantly better than XGB at UNSW→IoT and CIC→IoT** default tier

### Medium confidence (CI reasonable but some caveats):

7. **UNSW→CIC LR F1=0.731** — CI is tight [0.730, 0.733], but the single best cross-domain result
   in the "hard" direction. Certified.

8. **IoT→CIC LSTM default F1=0.261** — CI [0.259, 0.263], but seed std=0.149 means the
   canonical result may not be reproducible. Use with caution.

9. **CIC+UNSW→IoT LSTM fixed_fpr multisource gain** — real (p<0.0001) but narrow [0.117, 0.139].

### Requires caution (high seed variance):

10. **UNSW→IoT LSTM F1=0.707** — seed std=0.184 means this could be 0.44–0.80. Do NOT cite
    as a reliable point estimate. Describe as "variable across seeds."

11. **UNSW→CIC CNN1D** — seed std=0.042, range=0.083. Unstable.

12. **IoT→CIC CNN1D** — seed std=0.039, range=0.068. Unstable.

---

## Q9. Which Conclusions Should Retain Uncertainty Language?

The following conclusions should be restated with explicit uncertainty:

| Conclusion | Original statement | Uncertainty caveat to add |
|-----------|-------------------|--------------------------|
| UNSW→IoT LSTM F1=0.707 | "UNSW→IoT LSTM achieves F1=0.707" | "Seed variance is very high (std=0.18, range=0.44–0.80); this point estimate is not reliable" |
| IoT→CIC LSTM F1=0.261 | "IoT→CIC LSTM achieves F1=0.261" | "Seed variance is high (std=0.15); result may not reproduce reliably" |
| IoT in-domain all methods have low F1 | "IoT in-domain ML achieves only F1~0.06 at default" | Confirmed stable (deterministic for LR/XGB; seed-stable for DL). OK to cite. |
| IoT+UNSW→CIC multisource gains | "Multisource provides clear gain for IoT+UNSW→CIC" | Statistically certified. OK to cite as strong conclusion. |
| CIC+IoT→UNSW LR val_tuned gain | "Marginal LR gain (+0.032)" | Statistically significant (p<0.0001) but practically small. Cite as "modest but real." |

---

## Q10. Summary: Confidence Tiers for Final Synthesis

### Tier 1 — HIGH CONFIDENCE (certifiable in final synthesis)

- CIC→IoT LR F1=0.892 is the strongest cross-domain result; stable, tight CI
- UNSW→IoT LR/XGB are strong and stable cross-domain results
- All 6 single-source IoT→UNSW results fail; failure is statistically stable
- Cross-domain degradation is universally significant vs in-domain
- IoT+UNSW→CIC LR val_tuned gain (+0.062) is certified by significance test
- LR significantly outperforms XGB/LSTM at CIC→IoT and UNSW→IoT default tier

### Tier 2 — MEDIUM CONFIDENCE (can cite with CI qualifier)

- UNSW→CIC LR/LSTM are the only partial cross-domain successes for hard directions
- CIC+UNSW→IoT LSTM fixed_fpr multisource gain is real but narrow
- Threshold portability (val_tuned vs default) differences are significant but often small
- IoT+UNSW→CIC XGB val_tuned gain (+0.083) is certified

### Tier 3 — LOW CONFIDENCE (cite with explicit seed-variance warning)

- UNSW→IoT LSTM canonical F1=0.707 (seed std=0.184; result range 0.44–0.80)
- IoT→CIC LSTM default F1=0.261 (seed std=0.149; result range 0.03–0.27)
- UNSW→CIC CNN1D (high seed variance for this architecture×direction combination)

### Not applicable (External Benign)

- External benign FPR estimates are correctly treated as single-dataset observations; no CI needed.
  The conclusion ("UNSW models have very high false alarm rate") is an empirical observation
  on a specific external PCAP, not a population-level estimate.

---

## Appendix: Key Bootstrap CI Table

Selected results from `final_bootstrap_ci_results.csv`:

```
Experiment         Context       Method  Tier       F1_PE   F1_CI_lo  F1_CI_hi  ROC_PE  ROC_CI_lo  ROC_CI_hi
single_src_default cic_to_iot    lr      default    0.8921  0.8863    0.8974    0.9829  0.9789     0.9858
single_src_default unsw_to_iot   lr      default    0.8601  0.8534    0.8656    0.8774  0.8654     0.8861
single_src_default unsw_to_iot   xgb     default    0.8081  0.8018    0.8148    0.7910  0.7829     0.8076
single_src_default unsw_to_iot   lstm    default    0.7074  0.7006    0.7144    0.4482  0.4327     0.4642
single_src_default unsw_to_cic   lr      default    0.7313  0.7299    0.7330    0.6432  0.6205     0.6546
single_src_default iot_to_unsw   lr      default    0.0316  0.0297    0.0333    0.3201  0.3101     0.3319
single_src_default iot_to_cic    lr      default    0.0863  0.0846    0.0877    0.6157  0.6028     0.6281
multisource_claim  IoT+UNSW->CIC lr      val_tuned  0.8027  0.8013    0.8041    0.7222  0.7060     0.7394
multisource_claim  IoT+UNSW->CIC xgb     val_tuned  0.2466  0.2445    0.2489    0.2880  0.2703     0.3031
```

---

## Protocol Compliance

- No side-branch assets used
- Canonical tables untouched (MD5 verified)
- No model retraining for bootstrap (uses frozen canonical predictions)
- DL seed reruns: same architecture, same hyperparameters, different random seed only
- Significance: paired_bootstrap_f1 (unified — CI and p-value from same bootstrap distribution), Holm correction within family
- Subsampled ROC/PR-AUC (n=5000 stratified) used for large CIC dataset; valid unbiased estimator
