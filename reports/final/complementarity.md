# Complementarity and Lightweight Fusion

> **Methods analyzed:** LR, XGB, LSTM (representative); Suricata (CIC in-domain default only)
> **Fusion coverage:** Triple (LR+XGB+LSTM) + Pairwise (LR+XGB, LR+LSTM, XGB+LSTM); OR and AND for all

---

## Q1. Overall: Substitution or Complementarity?

**In-Domain:** Mean TP Jaccard = 0.600 across 9 pairs
  → Moderate overlap: in UNSW (all methods strong), methods are largely substitutes.
  In IoT, LSTM uniquely detects Torii/Hajime attacks that LR/XGB miss — genuine complementarity.

**Cross-Domain:** Mean TP Jaccard = 0.249 across 17 pairs
  → Low average, but this masks a bimodal split:
  - Successful blocks (CIC→IoT, UNSW→IoT, UNSW→CIC): Jaccard reflects genuine shared detection (methods converge on same attack flows)
  - Failed blocks (IoT→UNSW, IoT→CIC, CIC→UNSW): Jaccard ≈ 0 because all methods miss the same attacks — **shared weakness, not complementarity**

**After pairwise fusion补齐:** The pairwise results confirm the triple fusion pattern. Pairwise OR gains no additional insight beyond: LR+LSTM in IoT in-domain is the only pairwise combination with genuine unique-TP gain (+0.030 F1 vs LR alone).

**Conclusion:** Results support **substitution more than complementarity** overall. The only domain where true complementarity exists at the prediction level is IoT in-domain (LSTM detects Torii/Hajime patterns that LR cannot). In all cross-domain blocks, methods either jointly succeed or jointly fail on the same attack populations.

---

## Q2. Does Suricata Provide Unique TP on CIC In-Domain?

*Analysis scope: CIC in-domain, default threshold only. Suricata has no val_tuned or fixed_fpr tier.*

**Suricata vs LR (default):** Suricata unique TP = 185 / 191 total Suricata TP (TP Jaccard = 0.0002)
**Suricata vs XGB (default):** Suricata unique TP = 191 / 191 total Suricata TP (TP Jaccard = 0.000)
**Suricata vs LSTM (default):** Suricata unique TP = 185 / 191 total Suricata TP (TP Jaccard = 0.0002)

**Finding:** Suricata detects 191 Friday attacks (recall ≈ 0.001 out of 197,378). Its unique TPs are mostly DDoS signatures missed by ML. However, 191 unique detections out of 197,378 attacks is 0.097% incremental coverage. Adding Suricata to any ML method provides negligible recall gain (+0.001 at most) at the cost of ~704 FPs. Suricata's CIC in-domain value is nominal and does not justify operational complexity.

---

## Q3. Complementarity in Successful vs Failed Cross-Domain Blocks?

**Successful transfer blocks (cic_to_iot, unsw_to_iot, unsw_to_cic):**
  Mean TP Jaccard = 0.442 (8 pairs)
  → Non-trivial Jaccard: methods detect largely the same flows. Successful blocks show *shared detection*, not unique-TP complementarity.

**Failed transfer blocks (cic_to_unsw, iot_to_unsw, iot_to_cic):**
  TP Jaccard ≈ 0 or undefined (all methods produce ≈0 TPs, e.g., cic_to_iot XGB/LSTM)
  → Shared weakness. All methods miss the same attacks. Fusion cannot recover what no individual method finds.

**Finding:** Complementarity — in the sense of unique TP contribution — does not appear in cross-domain blocks. Successful blocks show convergent detection (substitution). Failed blocks show convergent failure (shared weakness). Fusion helps neither case materially.

---

## Q4. UNSW→IoT: Does Fusion Beat Best Single Model?

Best single model (default threshold): LR, F1=0.8601

| Fusion | F1 | Recall | FPR | ΔF1 vs best | Gain type |
|--------|----|--------|-----|-------------|----------|
| OR (lr+xgb+lstm) | 0.7289 | 0.9950 | 0.9792 | -0.1312 | mostly_fp_relaxation |
| AND (lr+xgb+lstm) | 0.8600 | 0.7734 | 0.0335 | -0.0001 | tradeoff_not_worth_it |
| majority_vote (lr+xgb+lstm) | 0.7913 | 0.8572 | 0.4122 | -0.0688 | mostly_fp_relaxation |
| score_average (lr+xgb+lstm) | 0.8060 | 0.8838 | 0.4120 | -0.0541 | mostly_fp_relaxation |
| OR (lr+xgb) | 0.7840 | — | — | -0.0761 | mostly_fp_relaxation |
| OR (lr+lstm) | 0.7304 | — | — | -0.1297 | mostly_fp_relaxation |

**Finding:** All fusion variants perform below LR alone (F1=0.8601). No fusion combination improves on the best single method for UNSW→IoT. The OR fusion dramatically increases FPR (up to 97%) without recovering recall. **UNSW→IoT fusion is not deployment-worthy in any variant.**

---

## Q5. Hard Transfer Blocks (IoT→CIC, IoT→UNSW): Is Fusion Just FP Amplification?

| Block | Fusion | Components | F1 | Recall | FPR | ΔF1 | Gain type |
|-------|--------|-----------|-----|--------|-----|-----|----------|
| iot_to_unsw | OR | lr+xgb+lstm | 0.0589 | 0.3464 | 0.6248 | -0.0805 | mostly_fp_relaxation |
| iot_to_unsw | AND | lr+xgb+lstm | 0.0000 | 0.0000 | 0.0000 | -0.1394 | tradeoff_not_worth_it |
| iot_to_cic | OR | lr+xgb+lstm | 0.2446 | 0.1917 | 0.2520 | -0.0161 | mostly_fp_relaxation |
| iot_to_cic | AND | lr+xgb+lstm | 0.0000 | 0.0000 | 0.0036 | -0.2607 | tradeoff_not_worth_it |
| iot_to_unsw | OR | lr+lstm | 0.0522 | — | — | -0.0872 | mostly_fp_relaxation |
| iot_to_cic | OR | lr+lstm | 0.2467 | — | — | -0.0140 | mostly_fp_relaxation |

**Finding:** In hard transfer blocks, OR fusion amplifies FP catastrophically (FPR up to 62% for IoT→UNSW) without recovering meaningful recall. AND fusion kills all recall. Pairwise fusion confirms this: no pairwise variant outperforms the best single method. Fusion does not rescue fundamentally failed transfer — when all methods lack feature discriminability on the target domain, combining them does not create discriminability.

---

## Q6. Fixed FPR Budget: Which Fusions Are Worth Keeping?

Selected rows from fixed_fpr tier (eligible, F1 > 0):

| Block | Fusion | Components | F1 | Recall | FPR | ΔF1 | Gain type |
|-------|--------|-----------|-----|--------|-----|-----|----------|
| cic_to_iot | OR | lr+xgb+lstm | 0.8606 | 0.7669 | 0.0203 | +0.0356 | **true_tp_complementarity** |
| cic_to_iot | OR | lr+xgb | 0.8380 | 0.7286 | 0.0138 | +0.0130 | **true_tp_complementarity** |
| cic_to_iot | OR | lr+lstm | 0.8483 | 0.7444 | 0.0141 | +0.0233 | **true_tp_complementarity** |
| cic_to_iot | OR | xgb+lstm | 0.2012 | 0.1131 | 0.0145 | +0.0666 | **true_tp_complementarity** |
| in_domain_cic | OR | lr+xgb+lstm | 0.3144 | 0.1938 | 0.0261 | -0.0061 | no_material_gain |
| cic_to_unsw | OR | lr+xgb+lstm | 0.0877 | 0.1446 | 0.1291 | +0.0236 | tradeoff_not_worth_it |
| iot_to_unsw | OR | lr+xgb+lstm | 0.0220 | 0.0518 | 0.2190 | +0.0000 | no_material_gain |

**Fixed FPR conclusion:**
- The only cross-domain block with deployment-worthy fixed_fpr OR gains is **CIC→IoT** (FPR ≤ 2.0%, F1 gain +0.013 to +0.036 depending on components). This is because CIC source models have non-degenerate fixed_fpr thresholds that, when fused via OR, catch complementary attacks at low FPR.
- All other cross-domain blocks at fixed_fpr either degenerate (→all-benign) or produce no material gain.
- In-domain fixed_fpr fusion produces no improvement over best single methods.

---

## Q7. Deployment Recommendation

### Worth combining (deployment-worthy gains confirmed)

**CIC→IoT, fixed_fpr OR (lr+xgb+lstm or any pairwise including LR):**
The only cross-domain block with genuine fixed_fpr fusion gain.
OR fusion achieves F1=0.861 (+0.036 vs best single 0.825) at FPR=2.0% — operationally acceptable.
LR+LSTM OR is the most parsimonious effective pair (F1=0.848, FPR=1.4%).
This gain comes from LR capturing high-volume C&C flows and the non-degenerate fixed_fpr variants of XGB/LSTM capturing residual attack patterns.

**IoT in-domain, default OR (any pair including LSTM):**
LSTM uniquely detects Torii/Hajime attacks (unique TP ≈ 2,374) that LR/XGB miss.
LR+LSTM OR: F1=0.498 vs LSTM alone F1=0.468, delta=+0.030, FPR=9.6% (vs LSTM's 8.5%).
This is a genuine mechanistic complementarity — LR and LSTM exploit different temporal features.
Note: this is in-domain evaluation with family-disjoint test split; the absolute F1 is low regardless.

### Not worth combining (confirmed by both triple and pairwise results)

**UNSW→IoT (all fusion variants at default):** Every fusion variant performs below LR alone (F1=0.860). OR catastrophically inflates FPR. No pairwise or triple combination improves on the best single method.

**CIC→IoT default OR:** F1=0.892 ≈ LR alone F1=0.892. Delta=-0.0001. Fusion adds nothing — LR dominates entirely. XGB and LSTM have 0 TPs at default threshold; OR = LR alone.

**IoT→UNSW, IoT→CIC (all variants):** Shared weakness. OR amplifies FP without recovering TP. No fusion variant comes close to the best single method's F1.

**CIC→UNSW (all variants at fixed_fpr):** Even though delta_f1 > 0 in some cases, the absolute FPR (8.6–12.9%) is too high for operational use. Classified as `tradeoff_not_worth_it`.

**UNSW→CIC (all variants):** No fusion variant improves on LR alone (F1=0.731). XGB+LSTM OR at default achieves F1=0.681 (+0.051 vs XGB/LSTM best, but -0.05 vs LR). OR with LR produces FPR=0.64, making it worse than LR alone.

**Score average (all cross-domain blocks):** Score average consistently underperforms the best single method in cross-domain settings due to calibration mismatch (XGB/LSTM scores dilute LR's well-calibrated signal in successful blocks; in failed blocks, averaging scores that are all near 0 for attacks produces nothing useful).

**Suricata + ML fusion:** Suricata contributes ~185 unique TPs out of 197,378 CIC Friday attacks. The absolute coverage gain is 0.094% — below any deployment threshold.

### Summary verdict

**Pairwise fusion confirms triple fusion findings — main conclusion unchanged.**

The evidence strongly supports **substitution more than complementarity** across all 9 evaluation blocks:
- When methods succeed, they detect largely the same attack flows (high TP Jaccard in successful blocks)
- When methods fail, they fail on the same attacks (shared weakness in failed blocks)
- Pairwise OR fusions almost universally perform no better than — and often worse than — the best single constituent method

**The only two deployment-worthy fusion scenarios:**
1. **CIC→IoT fixed_fpr OR** — small but real gain at low FPR; LR+LSTM is the optimal pair
2. **IoT in-domain OR (LSTM-including)** — real mechanistic complementarity; LSTM unique TPs cover different attack behavior than LR/XGB

The primary bottleneck is not method complementarity but **threshold portability and feature distribution shift**. Fusion cannot compensate for threshold collapse or distribution shift by combining more broken predictions.
