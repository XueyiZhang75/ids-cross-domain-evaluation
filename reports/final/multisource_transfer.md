# Multisource Transfer Learning

> **Scope:** Two-source training configurations across all three datasets
> **Baselines:** Tier-matched from single-source portability results (`final_threshold_portability_table.csv`)

---

## Executive Summary

Three two-source training experiments were conducted (LR, XGB, LSTM per direction):

| Direction | Source A | Source B | Target |
|-----------|----------|----------|--------|
| CIC+IoT->UNSW | CIC (1,052,851 train) | IoT (9,735 train) | UNSW-NB15 |
| CIC+UNSW->IoT | CIC (1,052,851 train) | UNSW (115,469 train) | IoT-23 |
| IoT+UNSW->CIC | IoT (9,735 train) | UNSW (115,469 train) | CIC-IDS2017 |

**Main finding:** Multisource training provides clear gains only in specific method×tier
combinations. IoT+UNSW->CIC yields clear gains for LR and XGB at default and val_tuned tiers —
the only direction where both sources contribute comparably (~8:92 ratio). CIC+IoT->UNSW yields
a marginal LR val_tuned gain (+0.032). CIC+UNSW->IoT degrades all methods at default/val_tuned;
LSTM achieves a narrow fixed_fpr gain. LR is the most robust method across all multisource
scenarios. XGB is complementary to LR in capturing different attack families but is brittle
under CIC-dominated class imbalance. LSTM never achieves a net gain at default or val_tuned tiers.

---

## Q1. Does Multisource Training Generally Reduce Domain Shift?

**No — not in general.** The outcome depends on the proportional balance and taxonomic
complementarity of the two source datasets.

| Direction | LR default | LR val_tuned | XGB default | XGB val_tuned | LSTM default |
|-----------|-----------|--------------|------------|--------------|--------------|
| CIC+IoT->UNSW | no_change | **clear_gain** | worse | worse | worse |
| CIC+UNSW->IoT | worse | worse | worse | worse | worse |
| IoT+UNSW->CIC | **clear_gain** | **clear_gain** | **clear_gain** | **clear_gain** | worse |

Source proportion imbalance dominates outcome:

| Direction | Source A share | Source B share |
|-----------|---------------|---------------|
| CIC+IoT->UNSW | CIC: 99.1% | IoT: 0.9% |
| CIC+UNSW->IoT | CIC: 90.1% | UNSW: 9.9% |
| IoT+UNSW->CIC | IoT: 7.8% | UNSW: 92.2% |

When CIC (1M+ train rows) dominates, combined LR ≈ CIC single-source, and XGB collapses because
CIC's scale_pos_weight (~37:1) overwrites the complementary source signal.

---

## Q2. Which Target Benefits Most from Multisource?

**CIC-IDS2017 target (IoT+UNSW->CIC) benefits most.**

| Method | Tier | Multi F1 | Baseline[tier] F1 | delta | Type |
|--------|------|---------|------------------|-------|------|
| LR | default | 0.7666 | 0.7313 | **+0.035** | clear_gain |
| LR | val_tuned | **0.8027** | 0.7403 | **+0.062** | clear_gain |
| XGB | default | 0.2445 | 0.2038 | **+0.041** | clear_gain |
| XGB | val_tuned | 0.2466 | 0.1635 | **+0.083** | clear_gain |

LR val_tuned is the best result across all multisource experiments: F1=0.803, recall=0.802,
FPR=0.131 — vs tier-matched UNSW->CIC LR val_tuned (F1=0.740, FPR=0.222). Both F1 and FPR
improve simultaneously — a genuine representation gain, not a recall/FPR trade-off.

**UNSW-NB15 (CIC+IoT->UNSW):** Marginal LR val_tuned gain (+0.032); no other method/tier gains.

**IoT-23 (CIC+UNSW->IoT):** No benefit at default/val_tuned. LSTM fixed_fpr gain (F1=0.129
vs 0.078, +0.051) at thr=0.397 — narrow but real.

---

## Q3. Which Target Is Almost Unaffected or Harmed?

**IoT-23 is most harmed.** CIC->IoT single-source LR default F1=0.892.
CIC+UNSW->IoT LR drops to 0.851 (-0.041). XGB collapses from 0.808 to 0.001 (-0.807).

XGB collapse mechanism: combined scale_pos_weight ≈ 33:1 (CIC-dominated) assigns near-zero
scores to IoT attacks. ROC-AUC=0.818 confirms rank signal is preserved — this is an operating
point failure, not a rank collapse. A target-domain threshold refit would likely recover F1, but
this is forbidden under the no-target-tuning protocol.

**UNSW-NB15 is essentially unaffected (CIC+IoT->UNSW):** IoT's 0.9% contribution shifts
no decision boundary. LR no_change; XGB and LSTM degrade.

---

## Q4. What Does Multisource Training Improve for Each Method?

### LR — genuine representation breadth gains

LR is the most reliably benefited method. In IoT+UNSW->CIC, LR val_tuned achieves F1=0.803,
FPR=0.131 — better on both dimensions than either single-source baseline. ROC-AUC=0.719 vs
single-source peaks of 0.621/0.639 confirms genuine rank signal improvement.

In CIC+UNSW->IoT, LR degrades only moderately (-0.041 default, -0.033 val_tuned) and remains
functional (F1=0.851). This is the softest failure across all multisource experiments.

### XGB — complementary family coverage, brittle under CIC-dominated imbalance

XGB captures **dos_ddos** in IoT+UNSW->CIC (recall 99.2%) where LR fails completely (recall 0%).
XGB val_tuned gains +0.083 over tier-matched baseline. This complementarity to LR is consistent
with the complementarity analysis findings.

In CIC-dominated combos: CIC+UNSW->IoT XGB (ROC-AUC=0.818, PR-AUC=0.877) has rank signal
but broken operating point (scale_pos_weight mismatch). CIC+IoT->UNSW XGB (ROC-AUC=0.275)
has genuine rank collapse — no threshold adjustment rescues this direction.

### LSTM — universally poor at default/val_tuned; narrow fixed_fpr gain in one case

LSTM never achieves clear_gain at default or val_tuned in any direction. The single exception
is CIC+UNSW->IoT LSTM fixed_fpr (F1=0.129 vs 0.078, +0.051 = clear_gain at thr=0.397).
At all default/val_tuned tiers, LSTM is worse than its tier-matched single-source baseline.

Root cause: joint normalizer across heterogeneous delta_t distributions (IoT Mirai: 1.87s vs
CIC: near-zero vs UNSW: 0.017s) destroys LSTM's temporal pattern recognition. Confirmed by
Sequence-channel drift analysis (IoT-UNSW delta_t KS=0.558 — severe).

---

## Q5. Is Multisource More Stable Than Constituent Single-Source Baselines?

**Generally no.** Only IoT+UNSW->CIC for LR and XGB shows improved stability.

- CIC+IoT->UNSW: LR stable, XGB/LSTM collapse. Net: less stable.
- CIC+UNSW->IoT: LR degrades moderately, XGB/LSTM fail badly. Net: much less stable.
- IoT+UNSW->CIC: LR/XGB improve, LSTM degrades. Net: partially more stable.

---

## Q6. Does Multisource Improve Fixed_FPR / Val_Tuned Portability?

### Corrected analysis note

The original multisource analysis `search_fixed_fpr` scanned from 1.0 downward, yielding thr ≈ 1.0 for all
9 combinations (universally degenerate). Corrected to ascending scan (MIN threshold
s.t. FPR(combined_val) ≤ 1%).

### Corrected fixed_fpr results

| Direction | Method | thr | F1 | baseline[fixed_fpr] F1 | delta | type |
|-----------|--------|-----|----|------------------------|-------|------|
| CIC+IoT->UNSW | LR | 0.708 | 0.071 | 0.064 | +0.007 | no_change |
| CIC+IoT->UNSW | XGB | 0.0001 | 0.035 | 0.057 | -0.022 | no_change |
| CIC+IoT->UNSW | LSTM | 0.244 | 0.000 | 0.058 | -0.058 | worse |
| CIC+UNSW->IoT | LR | 0.9997 | 0.001 | 0.825 | -0.824 | **blocked** |
| CIC+UNSW->IoT | XGB | 0.528 | 0.001 | 0.135 | -0.134 | worse |
| CIC+UNSW->IoT | LSTM | 0.397 | **0.129** | 0.078 | **+0.051** | **clear_gain** |
| IoT+UNSW->CIC | LR | 0.951 | 0.007 | 0.002 | +0.005 | no_change |
| IoT+UNSW->CIC | XGB | 0.996 | 0.000 | 0.000 | 0.000 | **blocked** |
| IoT+UNSW->CIC | LSTM | 0.978 | 0.023 | 0.000 | +0.023 | no_change |

**Per-direction fixed_fpr analysis:**

**CIC+IoT->UNSW:** fixed_fpr is achievable for all methods. LR no_change (+0.007).
LSTM fails due to collapsed score distribution (ROC-AUC=0.622). Not a threshold issue.

**CIC+UNSW->IoT:** LR blocked (thr=0.9997). Mechanism: 415,293-flow combined_val (CIC+UNSW
benign dominated) + mixed score distributions make FPR≤1% unachievable below near-degenerate
threshold. LSTM gains: thr=0.397 is genuine, F1=0.129 vs 0.078.

**IoT+UNSW->CIC:** LR and XGB near-degenerate (val score overlap). LSTM marginal no_change.

### val_tuned portability

- **IoT+UNSW->CIC LR val_tuned:** F1=0.803 vs 0.740 (+0.062). Best multisource result.
- **CIC+IoT->UNSW LR val_tuned:** F1=0.072 vs 0.040 (+0.032). Marginal gain.
- **CIC+UNSW->IoT:** All three methods worse than tier-matched baselines.
- **LSTM val_tuned:** Never reaches tier-matched baseline in any direction.

---

## Q7. Which Directions Only "Look Better" Due to FPR Trade-offs?

**IoT+UNSW->CIC LR val_tuned (F1=0.803, FPR=0.131):** Genuine — F1 up AND FPR down vs
tier-matched baseline (F1=0.740, FPR=0.222).

**IoT+UNSW->CIC LR default (F1=0.767, FPR=0.200):** F1 gain real (+0.035) but FPR=20%.
Suitable for research, not for production deployment.

**IoT+UNSW->CIC XGB default (F1=0.245, FPR=0.243):** XGB captures dos_ddos (recall 99.2%)
but FPR=24.3% is not operationally deployable. F1 gain (+0.041) is real, cost is high.

---

## Q8. Is the Multisource Gain About Fixing Representation or Operating Point?

### IoT+UNSW->CIC LR — genuine representation improvement

IoT->CIC LR ROC-AUC=0.621; UNSW->CIC LR ROC-AUC=0.639.
Multisource IoT+UNSW LR ROC-AUC=0.719 — improved rank discrimination. The combined model
covers CIC's reconnaissance_scan (recall 99.8%) and botnet_malware (recall 94.3%) by drawing
on IoT's PortScan/Mirai patterns and UNSW's DoS/Fuzzing features. This is representation gain,
not threshold adjustment.

### CIC+UNSW->IoT XGB — rank preserved, operating point broken (NOT rank collapse)

ROC-AUC=0.818, PR-AUC=0.877. Rank signal substantially preserved. All threshold tiers fail
(F1<0.002) because combined scale_pos_weight (33:1 from CIC dominance) maps IoT attacks into
near-zero score range. A target-domain threshold refit would likely recover significant F1 —
but this is forbidden. This is a **threshold portability failure layered on scale_pos_weight
mismatch**, not a representation collapse.

### CIC+IoT->UNSW XGB — rank signal collapsed

ROC-AUC=0.275 (below random). Genuine rank collapse: CIC-dominated training with IoT at 0.9%
contribution inverts rank ordering for UNSW attacks. No threshold adjustment can rescue this.

### CIC+UNSW->IoT LSTM — partial rank signal, temporal normalization disrupted

ROC-AUC=0.752, PR-AUC=0.743. Rank partially preserved but weaker than UNSW->IoT LSTM (0.991).
Joint normalization of delta_t across CIC/UNSW/IoT timing distributions reduces LSTM's temporal
discriminability. This is a representation quality problem, not purely a threshold problem.

---

## Q9. Final Research / Deployment Recommendations

### Which targets benefit from multisource?

**CIC-IDS2017 target with IoT+UNSW sources:** Real gains. LR val_tuned: F1=0.803, FPR=0.131.
XGB captures complementary dos_ddos (recall 99.2%). Recommended if the combined 20%/13% FPR
is acceptable.

**UNSW-NB15:** Marginal LR val_tuned gain (+0.032). Not actionable at default tier.

**IoT-23:** Do not use CIC-containing source combinations. CIC dominance destroys XGB and
degrades LR. No method×tier combination beats the UNSW->IoT single-source baseline.

### Which source combinations are most valuable?

**IoT + UNSW (->CIC):** Best balance (~8:92). Complementary taxonomies. Only direction with
clear_gain for both LR and XGB at default and val_tuned.

**CIC + any small dataset:** 9:1 to 108:1 ratio swamps the smaller source. LR may yield
marginal val_tuned gains; XGB/LSTM fail.

### Which methods for multisource?

1. **LR** — most reliable. Recommended when sources are within ~10x size ratio.
2. **XGB** — valuable for complementary family coverage but requires per-source class weight
   normalization to avoid combined scale_pos_weight collapse in CIC-dominated combos.
3. **LSTM** — not suitable for naive multisource concatenation. Requires domain-specific
   batch sampling or separate normalizers per source to preserve temporal patterns.

### Negative conclusions (formally stated)

- Multisource training in naive concatenation does NOT generally solve domain shift.
- Adding a source 100x smaller than the primary provides negligible benefit.
- CIC's 1M+ training set dominates any combined training when used as primary source.
- LSTM's temporal representation breaks under joint normalization across heterogeneous
  inter-packet timing distributions.
- fixed_fpr threshold is blocked or near-degenerate in 4 of 9 method×direction combinations,
  confirming that combined_val calibration (dominated by CIC's rare-attack val split) prevents
  reliable 1% FPR budget calibration in CIC-dominated source combos.

---

## Appendix: Full Results

Full table: `final_multisource_transfer_results.csv` (27 rows).

### CIC+IoT→UNSW (target: 6,916/122,175 attacks)

| Method | Tier | F1 | Recall | FPR | ROC-AUC | Baseline[tier] F1 | delta | Type |
|--------|------|----|--------|-----|---------|-------------------|-------|------|
| LR | default | 0.1435 | 0.205 | 0.099 | 0.644 | 0.143 | +0.001 | no_change |
| LR | val_tuned | 0.0722 | 0.088 | 0.080 | 0.644 | 0.040 | **+0.032** | **clear_gain** |
| LR | fixed_fpr | 0.0708 | 0.086 | 0.080 | 0.644 | 0.064 | +0.007 | no_change |
| XGB | default | 0.0000 | 0.000 | 0.000 | 0.275 | 0.044 | -0.044 | worse |
| XGB | val_tuned | 0.0000 | 0.000 | 0.000 | 0.275 | 0.055 | -0.055 | worse |
| XGB | fixed_fpr | 0.0350 | 0.064 | 0.156 | 0.275 | 0.057 | -0.022 | no_change |
| LSTM | default | 0.0000 | 0.000 | 0.000 | 0.622 | 0.139 | -0.139 | worse |
| LSTM | val_tuned | 0.0000 | 0.000 | 0.000 | 0.622 | 0.118 | -0.118 | worse |
| LSTM | fixed_fpr | 0.0000 | 0.000 | 0.000 | 0.622 | 0.058 | -0.058 | worse |

### CIC+UNSW->IoT (target: 7,348/12,865 attacks)

| Method | Tier | F1 | Recall | FPR | ROC-AUC | Baseline[tier] F1 | delta | Type |
|--------|------|----|--------|-----|---------|-------------------|-------|------|
| LR | default | 0.8514 | 0.763 | 0.039 | 0.953 | 0.892 | -0.041 | worse |
| LR | val_tuned | 0.8316 | 0.720 | 0.016 | 0.953 | 0.864 | -0.033 | worse |
| LR | fixed_fpr | 0.0014 | 0.001 | 0.001 | 0.953 | 0.825 | -0.824 | blocked |
| XGB | default | 0.0011 | 0.001 | 0.001 | 0.818 | 0.808 | -0.807 | worse |
| XGB | val_tuned | 0.0005 | 0.000 | 0.000 | 0.818 | 0.815 | -0.815 | worse |
| XGB | fixed_fpr | 0.0011 | 0.001 | 0.001 | 0.818 | 0.135 | -0.134 | worse |
| LSTM | default | 0.1244 | 0.066 | 0.002 | 0.752 | 0.707 | -0.583 | worse |
| LSTM | val_tuned | 0.0303 | 0.015 | 0.000 | 0.752 | 0.459 | -0.429 | worse |
| LSTM | fixed_fpr | **0.1285** | 0.069 | 0.002 | 0.752 | 0.078 | **+0.051** | **clear_gain** |

### IoT+UNSW->CIC (target: 197,378/491,455 attacks)

| Method | Tier | F1 | Recall | FPR | ROC-AUC | Baseline[tier] F1 | delta | Type |
|--------|------|----|--------|-----|---------|-------------------|-------|------|
| LR | default | 0.7666 | 0.807 | 0.200 | 0.719 | 0.731 | **+0.035** | clear_gain |
| LR | val_tuned | **0.8027** | 0.802 | 0.131 | 0.719 | 0.740 | **+0.062** | **clear_gain** |
| LR | fixed_fpr | 0.0072 | 0.004 | 0.051 | 0.719 | 0.002 | +0.005 | no_change |
| XGB | default | 0.2445 | 0.190 | 0.243 | 0.294 | 0.204 | **+0.041** | clear_gain |
| XGB | val_tuned | 0.2466 | 0.178 | 0.176 | 0.294 | 0.164 | **+0.083** | **clear_gain** |
| XGB | fixed_fpr | 0.0000 | 0.000 | 0.033 | 0.294 | 0.000 | 0.000 | blocked |
| LSTM | default | 0.1025 | 0.074 | 0.245 | 0.544 | 0.631 | -0.528 | worse |
| LSTM | val_tuned | 0.0927 | 0.066 | 0.236 | 0.544 | 0.720 | -0.627 | worse |
| LSTM | fixed_fpr | 0.0225 | 0.014 | 0.147 | 0.544 | 0.000 | +0.023 | no_change |

---

## Protocol Compliance Declaration

- All results use the canonical IoT v1 chain (no v2/side-branch assets).
- Canonical tables untouched (MD5-verified at each multisource analysisx pass).
- Thresholds derived only from combined_val — no target data used.
- fixed_fpr: ascending scan 0→1, MIN threshold s.t. FPR(combined_val) ≤ 1%.
- Baselines: tier-matched from `final_threshold_portability_table.csv` (cross_domain).
- No model retraining in This analysis/5c/5d; all scores from saved multisource analysis-local artifacts.
- Asset paths: `D:/ids_project_data/phase5_multisource/{direction}/`.
