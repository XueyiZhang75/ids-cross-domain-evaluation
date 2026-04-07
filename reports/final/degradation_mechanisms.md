# Cross-Domain Degradation Mechanisms

> **Methods analyzed:** LR, XGB, LSTM (representative; RF/CNN1D excluded from main matrix by design)
> **Blocks:** 6/6 directed cross-domain pairs

---

## Q1. Total Overall: What Is the Primary Source of Cross-Domain Degradation?

The evidence from three independent modules converges on a consistent answer:

**The primary source of cross-domain degradation is a combination of score/calibration drift AND feature distribution shift, with the relative weight depending on the direction.**

| Source | Finding |
|--------|---------|
| Feature drift | Severe in most blocks; UNSW→IoT has max KS=0.82 on bytes_per_packet |
| Score/calibration drift | Systematic positive-class score collapse in most failed blocks |
| Threshold portability | Fixed and val_tuned thresholds misaligned with target score distributions |
| Protocol/family mismatch | Secondary; protocol conditioning alone does not rescue failed blocks |

**By degradation mode (default threshold):**

| Block | LR | XGB | LSTM | Dominant pattern |
|-------|-----|-----|------|-----------------|
| CIC→IoT | mixed | rank_preserved_thr_failed | rank_preserved_thr_failed | Threshold failure (XGB/LSTM) |
| UNSW→IoT | mixed | mixed | rank_weakened | Partial rank weakening |
| CIC→UNSW | mixed | rank_weakened | rank_weakened | Rank signal collapse |
| IoT→UNSW | rank_weakened | rank_weakened | rank_weakened | Full rank collapse |
| UNSW→CIC | rank_weakened | rank_weakened | rank_weakened | Full rank collapse |
| IoT→CIC | rank_preserved_thr_failed | rank_preserved_thr_failed | mixed | Threshold failure, rank intact |

**Key insight:** The most important distinction is between:
1. **Blocks where rank signal is preserved but threshold fails** (CIC→IoT XGB/LSTM, IoT→CIC LR/XGB): ROC-AUC is still reasonable (0.83–0.99), but the operating point (threshold=0.5) misses most attacks because positive class scores on the target domain are systematically lower than on source.
2. **Blocks where rank signal itself collapses** (IoT→UNSW all, UNSW→CIC all, CIC→UNSW XGB/LSTM): ROC-AUC drops substantially; no threshold can rescue these.

---

## Q2. Why Is IoT-Source Weak in Outgoing Directions — and Why the Two Directions Differ?

**Critical distinction (A corrected analysis):** IoT source does NOT uniformly degrade the same way in both outgoing directions. The degradation modes differ:

| Block | LR | XGB | LSTM | Dominant mode |
|-------|-----|-----|------|--------------|
| IoT→UNSW | rank_weakened | rank_weakened | rank_weakened | Full rank signal collapse |
| IoT→CIC  | rank_preserved_thr_failed | rank_preserved_thr_failed | mixed | Threshold failure, rank intact |

**IoT→UNSW (rank collapse in all 3 methods):**

Feature drift evidence:
- IoT→UNSW mean top-10 KS = 0.405, max KS = 0.703 (bytes_fwd, packet_count_total)
- LSTM sequence-channel drift: delta_t KS = 0.558 (severe), signed_pkt_len KS = 0.352 (high) — the IoT inter-packet timing patterns (Mirai repetitive C&C polling) are qualitatively different from UNSW attack timing

Score drift evidence:
- IoT LR source positive mean score = 0.021; target (UNSW) positive mean score = 0.145 — the model assigns higher scores to UNSW attacks than to IoT attacks, but ROC-AUC drops from 0.764 to 0.327, meaning the rank ordering has broken down

Root cause: UNSW contains 9 diverse attack categories (Fuzzers, Generic, DoS, Exploits, Worms, etc.) with entirely different flow signatures. IoT models learn IoT-specific discriminators (small packets, repetitive timing patterns) that carry no discriminative signal in UNSW feature space. The LSTM sequence-channel delta_t KS=0.558 confirms the timing dimension alone is severely shifted.

**IoT→CIC (rank preserved, threshold fails for LR/XGB):**

- IoT→CIC LR ROC-AUC = 0.621, XGB ROC-AUC = 0.834 — meaningful rank signal preserved
- IoT→CIC LR PR-AUC = 0.450, XGB PR-AUC = 0.714 — the models correctly rank CIC attacks as more attack-like than CIC benign
- Failure at default threshold=0.5: IoT source positive-class mean score is 0.021 (LR), so threshold=0.5 cuts above all positives in both source and target
- Feature drift evidence: IoT→CIC mean top-10 KS = 0.230, max KS = 0.415 (bytes_per_packet_bwd) — lower than IoT→UNSW, consistent with partial rank preservation
- LSTM sequence-channel drift: signed_pkt_len KS = 0.312, delta_t KS = 0.395 — substantial but not as severe as IoT→UNSW delta_t KS = 0.558

Root cause for IoT→CIC: IoT Mirai/PortScan and CIC DoS/reconnaissance share enough flow-level structure (elevated packet rates, distinctive byte patterns) that rank signal partially transfers. The CIC target attacks also happen to score in the same near-zero range as the source positives — threshold failure, not rank failure.

**Shared root cause (both directions):** IoT training data represents a narrow attack taxonomy (Mirai C&C, PortScan, DDoS) with very specific packet-rate and byte-size signatures. These features are too narrow to fully cover either UNSW or CIC attack diversity. The IoT source positive-class score distribution is inherently compressed (LR mean ≈ 0.021) — a structural consequence of the difficult IoT in-domain boundary that makes threshold calibration unusable in cross-domain deployment.

---

## Q3. Why Is UNSW a Relatively Good Source but a Hard Target?

**UNSW as source (UNSW→IoT, UNSW→CIC):**
- UNSW→IoT: LR F1=0.860 — successful transfer
- UNSW→CIC: LR F1=0.731 — partial success
- UNSW→IoT mean top-10 KS = 0.641 (high drift), yet UNSW→IoT LR still works

The reason UNSW source models transfer reasonably is that UNSW training data covers 9 diverse attack categories, producing models that learn broad flow-level discriminators (high bytes_per_packet, high packet rates). These are reasonably correlated with IoT Mirai (high-volume botnet) and CIC DoS attacks.

**UNSW as target (CIC→UNSW, IoT→UNSW):**
- CIC→UNSW LR F1=0.143 — near-failure
- IoT→UNSW LR F1=0.032 — failure
- CIC→UNSW mean top-10 KS = 0.430; IoT→UNSW mean top-10 KS = 0.405

Why UNSW is a hard target:
1. **Label heterogeneity**: UNSW has 9 attack categories (Fuzzers, Generic, Backdoor, DoS, Exploits, Reconnaissance, Shellcode, Worms, Analysis) with very different flow signatures. A model trained on CIC DoS/brute-force learns features that match only ~2/9 UNSW categories.
2. **Score shift**: CIC→UNSW LR target positive mean score = 0.238 vs source = 0.193. The target attacks score slightly higher than source attacks, but the threshold remains miscalibrated (still 0.5 from source perspective).
3. **Protocol composition**: UNSW has a more balanced TCP/UDP mix (UNSW test: ~50% TCP), while CIC training is TCP-dominant. The TCP-only subset shows slight improvement (CIC→UNSW F1 improves from 0.143 to 0.151 on TCP-only) but doesn't rescue the fundamental problem.

---

## Q4. Which Failed Blocks Retain Rank Signal?

| Block | Method | ROC-AUC target | Degradation mode |
|-------|--------|----------------|-----------------|
| CIC→IoT | XGB | 0.876 | rank_signal_preserved_threshold_failed |
| CIC→IoT | LSTM | 0.921 | rank_signal_preserved_threshold_failed |
| IoT→CIC | LR | 0.621 | rank_signal_preserved_threshold_failed |
| IoT→CIC | XGB | 0.834 | rank_signal_preserved_threshold_failed |

**CIC→IoT XGB/LSTM**: These models correctly rank-order IoT attacks above benign (ROC-AUC=0.876/0.921), but their default threshold=0.5 is calibrated for CIC attacks which score very low (XGB CIC positive mean = 0.078). On IoT, attacks also score near-zero (XGB target positive mean ≈ 0.000), so even correct rank ordering produces F1≈0. The **fix is threshold portability, not representation** — a lower threshold would recover recall.

**IoT→CIC LR/XGB**: ROC-AUC=0.621/0.834, rank signal partially preserved. IoT LR positive mean score = 0.021 on source vs 0.050 on CIC target — the model correctly identifies CIC attacks as slightly more attack-like than benign, but at threshold=0.5 this tiny separation is invisible.

**Implication**: For CIC→IoT XGB/LSTM and IoT→CIC LR/XGB, the cross-domain problem is **not representation quality** but **threshold calibration**. These models are informationally useful but operationally broken at default thresholds.

---

## Q5. Does Protocol/Subset Conditioning Change Conclusions?

**Protocol analysis (LR default):**

| Block | TCP recall | UDP recall | Interpretation |
|-------|-----------|-----------|----------------|
| CIC→IoT | 0.815 (≈full) | 0.0 (2 UDP attacks) | IoT attacks ≈all TCP; protocol neutral |
| UNSW→IoT | 0.861 (≈full) | 1.0 (2 UDP) | Protocol neutral for main attack set |
| CIC→UNSW | 0.246 (↑ from 0.200) | 0.023 (↓) | TCP attacks better captured; UDP attacks harder |
| IoT→UNSW | 0.181 (↑ slight) | 0.001 (↓) | TCP slightly better; UDP fails |
| UNSW→CIC | 0.803 (≈full) | 0.0 | CIC attacks ≈all TCP |
| IoT→CIC | 0.050 (≈full) | 0.0 | Protocol irrelevant for IoT→CIC failure |

**Key finding**: Protocol conditioning does NOT materially change conclusions for the failed blocks. IoT→UNSW and IoT→CIC fail on both TCP and UDP attacks. CIC→UNSW shows marginal improvement on TCP-only (F1: 0.143 → 0.151) but the fundamental rank collapse on UDP attacks (F1 drops) confirms the issue is not protocol-specific.

**High-volume / high-pps conditioning:**

| Block | Full F1 | High-vol F1 | Delta | Interpretation |
|-------|---------|------------|-------|---------------|
| CIC→IoT (LR) | 0.892 | **0.947** | +0.055 | High-volume IoT attacks easier — large Mirai flows |
| UNSW→IoT (LR) | 0.860 | **0.881** | +0.021 | High-vol attacks better detected |
| CIC→UNSW (LR) | 0.143 | 0.007 | -0.136 | High-volume UNSW attacks harder — opposite! |
| IoT→UNSW (LR) | 0.032 | 0.027 | -0.005 | No improvement |
| UNSW→CIC (LR) | 0.731 | 0.581 | -0.150 | Large CIC DoS/Hulk flows harder for UNSW models |
| IoT→CIC (LR) | 0.086 | 0.131 | +0.045 | Slightly better, but F1 still very low |

**Key finding**: High-volume conditioning improves IoT-targeted blocks (CIC→IoT, UNSW→IoT) — where Mirai DDoS flows are large and distinctive. It HARMS CIC/UNSW-targeted blocks — high-volume attacks (DoS Hulk, Generic) are exactly the ones that cross-domain models fail on, because their volume features differ most from training data.

---

## Q6. Target-Local Family/Category Breakdown

From family analysis and degradation subset data:

**CIC target (coarse_family taxonomy):**
- `reconnaissance_scan` (158k flows): CIC→IoT and IoT→CIC models both fail on this dominant family (recall ≈ 0)
- `dos_ddos` (37k): IoT→CIC LSTM captures 99.98% recall but with catastrophic FPR
- `botnet_malware` (1.2k): near-zero detection by IoT models

**IoT target (detailed_label taxonomy):**
- `C&C-Torii` (7,031 flows): CIC→IoT LR captures 86% recall; UNSW→IoT LR captures 88%
- `DDoS-Hajime` (211): Both CIC and UNSW models struggle (recall <5% for most methods)
- `PartOfAHorizontalPortScan` (106): Near-zero detection across all cross-domain directions

**UNSW target (attack_cat taxonomy):**
- CIC→UNSW fails most consistently on `Generic` and `Reconnaissance` categories
- IoT→UNSW fails across all 9 categories

The degradation is NOT uniformly distributed: in IoT target, CIC/UNSW source models concentrate their TP on C&C-Torii (the dominant family) while completely missing DDoS and PortScan. This suggests the models transfer when the dominant target attack family resembles something they've seen, but fail on minority families even at high-recall overall settings.

---

## Q7. Connecting Threshold Portability and External Benign False Alarms

Most cross-domain fixed_fpr thresholds degenerate (thr→1.0) because source-domain fixed_fpr calibration is meaningless on target domain score distributions.

The score drift analysis reveals why. For example:
- IoT source LR: positive mean score=0.021, threshold=0.5 already misses 97% of positives
- Fixed_fpr threshold for IoT LR = 0.9999+ because the calibration on IoT val gives near-zero scores even for val attacks
- When applied to UNSW or CIC (which have higher absolute scores), the threshold cuts incorrectly

External benign analysis finding: External benign FPR is often uncontrolled even with fixed_fpr thresholds.

The Brier score shifts substantially across domains in most cross-domain blocks (e.g., CIC LR source Brier=0.337 → target on UNSW Brier=0.119; IoT LR source Brier=0.563 → CIC target Brier=0.418). Note: lower Brier = better calibration, so these shifts do not uniformly represent degradation — some cross-domain blocks show improved numerical calibration while failing operationally. The key point is that the calibration structure changes materially across domains: score values that represented calibrated probabilities on the source no longer have the same meaning on the target, causing both attack recall and benign specificity to become unreliable.

**Unified explanation**: The threshold portability failures and the external benign false alarm rates (External benign analysis) are both downstream consequences of the same phenomenon: models learn source-domain score distributions that are not transferable. When positive-class scores collapse on the target (CIC→IoT XGB), threshold=0.5 misses attacks. When positive-class scores inflate artificially (UNSW-trained LR on NFS benign), threshold=0.5 fires on benign traffic. Both are calibration/distribution shift problems.

---

## Q9. LSTM Sequence-Channel Drift (the degradation analysis Supplement)

For LSTM, flow-level feature importance is not available (DL model). the degradation analysis adds sequence-channel drift computed from the DL sequence npz files (32 packets × 4 channels per flow). Channel means per flow were compared between source test and target test splits using KS statistic and Wasserstein distance.

**Channels:** signed_pkt_len (ch0), direction_flag (ch1), delta_t (ch2), protocol_id (ch3)

| Block | ch0 signed_pkt_len KS | ch1 direction_flag KS | ch2 delta_t KS | ch3 protocol_id KS |
|-------|----------------------|----------------------|-----------------|---------------------|
| CIC→IoT | 0.312 (high) | 0.450 (high) | 0.395 (high) | 0.017 (low) |
| UNSW→IoT | 0.352 (high) | 0.382 (high) | **0.558** (severe) | 0.102 (low) |
| CIC→UNSW | 0.184 (moderate) | 0.145 (low) | 0.446 (high) | 0.119 (low) |
| IoT→UNSW | 0.352 (high) | 0.382 (high) | **0.558** (severe) | 0.102 (low) |
| UNSW→CIC | 0.184 (moderate) | 0.145 (low) | 0.446 (high) | 0.119 (low) |
| IoT→CIC | 0.312 (high) | 0.450 (high) | 0.395 (high) | 0.017 (low) |

**Key findings:**

1. **delta_t (inter-packet timing) is the most drifted channel** in IoT-involved blocks. UNSW→IoT and IoT→UNSW have delta_t KS=0.558 (severe), driven by the fundamental difference between IoT Mirai's repetitive C&C polling (large inter-packet intervals, source_mean=1.87s) vs UNSW attacks (source_mean=0.017s — near-zero delta_t, high-rate continuous traffic).

2. **signed_pkt_len and direction_flag drift consistently across all blocks** (KS=0.18–0.45). IoT Mirai flows have negative signed_pkt_len mean (-14.1, meaning backward packets dominate) vs CIC flows (-68.5, larger backward packets) and UNSW flows (+23.2, forward-dominated). This packet size asymmetry is a fundamental distributional difference.

3. **protocol_id is stable** (KS≤0.12 in all blocks). The protocol distribution (TCP/UDP mix) is relatively consistent, confirming that protocol conditioning alone does not drive degradation.

4. **CIC→UNSW and UNSW→CIC show lower sequence-channel drift** (max KS=0.45 vs 0.558 for IoT blocks). This is consistent with both CIC and UNSW containing similar attack taxonomies (DoS, scanning) at the packet sequence level. Yet CIC→UNSW LSTM still exhibits rank_signal_weakened — the delta_t KS=0.446 drift is enough to disrupt LSTM's temporal pattern recognition.

5. **The sequence-channel drift is symmetric by direction**: IoT↔UNSW and IoT↔CIC pairs have identical drift statistics regardless of source/target direction. This confirms the drift is an intrinsic property of the dataset pair, not direction-dependent.

---

## Q8. Final Deployment and Research Recommendations

### Primary recommendation: Fix threshold portability before representation

The degradation analysis confirms that for **CIC→IoT XGB/LSTM and IoT→CIC LR/XGB**, the rank signal is preserved but the threshold is the blocker. These represent the highest-ROI improvement opportunity: a target-domain threshold calibration (even using a small unlabeled target sample) could recover substantial F1 without any model retraining.

For blocks with full rank collapse (IoT→UNSW all, UNSW→CIC XGB, CIC→UNSW XGB/LSTM), the problem is deeper — no threshold can fix a model that doesn't discriminate. Here, representation improvement (feature engineering, retraining on more diverse source data) is needed.

### Source dataset recommendations

**Use UNSW-NB15 as source for IoT targets:** UNSW→IoT achieves LR F1=0.860 with preserved rank signal. UNSW's diverse attack taxonomy produces broader discriminators that transfer to IoT.

**Avoid IoT-23 as sole source for general deployment:** IoT source models have compressed score ranges and narrow feature coverage. They should be used only in IoT-specific contexts.

**CIC-IDS2017 is a strong source for IoT targets only:** CIC→IoT LR F1=0.892. CIC source models fail significantly on UNSW (F1=0.143) — their discriminators are too DoS-specific.

### Feature engineering recommendation

The UNSW→IoT high drift (max KS=0.82 on bytes_per_packet: source mean=251, target mean=85) suggests that flow-size normalization or relative feature encoding could reduce this discrepancy. IoT Mirai flows are smaller (85 bytes/packet) than UNSW flows (251 bytes/packet), but the rank signal persists in UNSW→IoT LR, suggesting the model compensates via the combination of features.

For IoT→UNSW (rank_signal_weakened), the fundamental issue is that IoT attacks look like nothing in the UNSW feature space. Feature engineering alone is unlikely to fix this without expanding the training taxonomy.

### Threshold Tier Verdict

- **Default (0.5)**: Works when source and target score distributions are compatible (UNSW→IoT, CIC→IoT LR). Fails when positive scores collapse.
- **Val_tuned**: Optimized for source recall, not target specificity or calibration. Generally not recommended for cross-domain deployment (confirmed by External benign analysis benign analysis).
- **Fixed_fpr (≤1% source FPR)**: Degenerates for most IoT/UNSW cross-domain combinations. Useful only for CIC→IoT where the source positive score distribution is high enough that fixed_fpr threshold is still informative.
- **Recommended**: Target-domain validation set calibration (small unlabeled sample with estimated attack/benign ratio) would be the most impactful practical improvement for the rank_preserved_threshold_failed blocks.

### Negative findings (mandatory)

1. **Protocol conditioning does not rescue failed blocks.** Restricting to TCP or UDP does not materially change conclusions for IoT→UNSW or IoT→CIC.
2. **High-volume/high-pps conditioning sometimes makes things worse.** UNSW→CIC high-volume F1 = 0.581 vs full 0.731 — the large CIC flows are harder, not easier, for UNSW models.
3. **UNSW as a source still fails on UNSW as a target from IoT/CIC source.** The same features that make UNSW a good source make it a hard target for other sources.
4. **Fusion cannot compensate for rank signal collapse.** OR fusion in IoT→UNSW (all rank_weakened) only amplifies FP without recovering TP.
5. **The IoT→UNSW block is the most comprehensively broken:** rank signal weakened for all 3 methods, high feature drift, low Brier improvement, no protocol or volume subset that helps.
