# External Benign Robustness

> **Dataset:** `hw1/part2.pcap` (external benign traffic)
> **Flows:** 2,956 | **Duration:** 600s | **All flows are benign by construction**
> **Methods:** LR, RF, XGB, CNN1D, LSTM (× 3 source datasets = 15 method-source combinations)
> **Suricata:** not evaluated (binary unavailable in this environment)

---

## Q1. Which Benign-Only External Set Was Used and Why Is It Valid?

**Dataset:** `hw1/part2.pcap` — a 366.8 MB packet capture from UVA Network Security course homework.

**Why it is benign-only:**
The traffic profile is consistent with benign local network services: NFS file sharing (port 2049), print services (port 631), SSH administration (port 22), and some HTTP. No scan patterns, SYN floods, botnet C&C signatures, or attack indicators were observed. The homework context is packet analysis, not attack injection.

**Why it is external:**
Not from CIC-IDS2017 (UNB 2017), IoT-23 (CTU Prague 2018-2019), or UNSW-NB15 (UNSW 2015). Represents UVA lab/campus network traffic, a completely separate environment from all three benchmark datasets.

**Limitations documented:** Small flow count (2,956); NFS-heavy traffic may not represent enterprise diversity; exact capture context unknown. See `final_out_of_domain_benign_dataset_selection.md` for full discussion.

---

## Q2. Which Method Family Is Most Prone to False Alarms on External Benign?

FPR at default threshold (= alerted_flows / total_flows, since all flows are benign):

| Method | CIC-trained | IoT-trained | UNSW-trained | Pattern |
|--------|-------------|------------|-------------|---------|
| **CNN1D** | **28.5%** | 1.7% | **20.5%** | Worst for CIC/UNSW |
| **LSTM** | 0.0% | **10.2%** | **23.2%** | Worst for IoT/UNSW |
| **LR** | 6.2% | 4.6% | **37.0%** | Catastrophic for UNSW |
| **RF** | 0.3% | 7.6% | 8.2% | Moderate across all |
| **XGB** | 0.2% | 8.9% | 17.5% | Moderate-high |

**Key finding:** **No single method family is consistently "safe"** on external benign traffic. The worst offenders depend on source:
- **CIC-trained CNN1D**: 28.5% FPR — outputs high scores on NFS/UDP traffic
- **UNSW-trained LR**: 37.0% FPR — UNSW's diverse training causes LR to misclassify NFS flows as attacks
- **IoT/UNSW-trained LSTM**: 10.2% / 23.2% FPR — LSTM learns temporal patterns that fire on repeated NFS packet sequences
- **CIC-trained LSTM**: 0.0% FPR — the best performer (CIC's DoS/brute-force boundary doesn't fire on NFS)

**DL models (CNN1D, LSTM) are not consistently better or worse than ML models** — their false alarm behavior depends heavily on the source domain's training distribution.

---

## Q3. Which Source Dataset Produces the Most Stable Models on External Benign?

Ranking by mean FPR across 5 methods at **default threshold (0.5)** — basis is consistent throughout:

| Rank | Source | Mean FPR (default) | Best Method (default) | Worst Method (default) |
|------|--------|-------------------|----------------------|------------------------|
| 1 (most stable) | **IoT-23** | **6.6%** | CNN1D (1.7%) | LSTM (10.2%) |
| 2 | **CIC-IDS2017** | **7.0%** | LSTM (0.0%) | CNN1D (28.5%) |
| 3 (least stable) | **UNSW-NB15** | **21.3%** | RF (8.2%) | LR (37.0%) |

All values are from `final_out_of_domain_benign_metrics.csv`, `threshold_type=default`, `eligible=True` rows. No val_tuned results are mixed into this ranking.

**IoT-23 source models are the most stable** (mean FPR=6.6%), narrowly ahead of CIC-IDS2017 (7.0%). UNSW-NB15 is decisively the least stable (21.3%).

**Why UNSW-NB15 is the worst source for benign stability:** UNSW's training data contains 9 diverse attack categories, many of which share feature-space overlap with legitimate high-volume network traffic (Generic attacks at 40k flows look similar to legitimate high-bandwidth NFS traffic). The models trained to detect these attacks end up with a broad decision boundary that also fires on external benign NFS flows.

**Why IoT-23 is the most stable:** IoT models were trained primarily on Mirai C&C/PortScan (specific byte-pattern signatures). They are less likely to fire on NFS/UDP traffic, except when repeated short UDP packet sequences resemble C&C polling — which explains why IoT-LSTM still reaches 10.2% FPR.

---

## Q4. Default vs Val_Tuned vs Fixed_FPR on Benign-Only External Traffic

### Default threshold (0.5)
The most balanced tier. FPR ranges from 0% to 37% across all source × method combinations.

### Val_tuned threshold
Optimized on source validation F1 — intended to detect more attacks. On external benign:
- **CIC RF val_tuned**: FPR surges to 17.2% (from 0.3% at default) — val-tuned threshold is very low (0.036)
- **CIC CNN1D val_tuned**: FPR = 64.5% — catastrophic (val_tuned threshold = 0.316, lower than default)
- **IoT CNN1D val_tuned**: FPR = 0.0% — benign-safe (threshold = 0.990, very conservative)
- **UNSW LR val_tuned**: FPR = 32.4% — slightly better than default but still very high

**Conclusion:** Val_tuned thresholds optimize for attack detection recall, not benign specificity. In many cases they INCREASE FPR on external benign compared to default.

### Fixed_fpr threshold (tuned for ≤1% FPR on source val)
The fixed_fpr tier degenerates (threshold ≥ 0.99 → all-benign) for most cross-domain and IoT/UNSW in-domain combinations For the benign evaluation:
- **CIC fixed_fpr** is non-degenerate for all 5 methods (eligible=True). Results on external benign:
  - LR: FPR=5.2%, slightly lower than LR default (6.2%)
  - RF: FPR=55.3% — worst result in the entire evaluation
  - XGB: FPR=8.7%
  - CNN1D: FPR=85.4% — catastrophic
  - LSTM: FPR=0.2% — the best result in this entire fixed_fpr analysis
- **IoT LSTM fixed_fpr** (non-degenerate, eligible=True): FPR=0.3% — strong benign control
- **Degenerate fixed_fpr tiers** (eligible=False, threshold ≥ 0.99): IoT RF/XGB/CNN1D/LR and UNSW RF/XGB/CNN1D/LSTM. These are marked degenerate because the threshold makes essentially all predictions benign on the source validation set — but **degenerate does not mean FPR=0 on external benign**. Flows with scores exceeding even a 0.99+ threshold can still occur:
  - IoT LR fixed_fpr (thr≈1.0, degenerate): FPR=**2.5%** (73/2,956 flows still alarmed)
  - UNSW LR fixed_fpr (thr≈1.0, degenerate): FPR=**1.4%** (42/2,956 flows still alarmed)
  - IoT RF/XGB/CNN1D and UNSW RF/XGB/CNN1D/LSTM: FPR=0.0% (no flows exceed threshold=1.0)

**Key finding on fixed_fpr:** The 1%-FPR constraint on source validation does NOT translate to controlled FPR on external benign. CIC RF fixed_fpr (source FPR ≤1%) achieves 55.3% FPR on external benign — a 55× overshoot. This is an extreme case of the threshold portability problem, now confirmed on external benign traffic.

---

## Q5. Does Fixed_FPR Control External Benign False Alarms?

**No.** Fixed_fpr thresholds tuned on source validation data do not reliably control false alarms on external benign traffic.

| CIC method | Source val FPR target | External benign FPR | Ratio |
|------------|---------------------|--------------------|----|
| LR | ≤1% | 5.2% | 5.2× |
| RF | ≤1% | 55.3% | 55.3× |
| XGB | ≤1% | 8.7% | 8.7× |
| CNN1D | ≤1% | 85.4% | 85.4× |
| LSTM | ≤1% | 0.2% | 0.2× (only model that improves) |

The fixed_fpr constraint is source-distribution-specific. The score distributions on external benign traffic are entirely different from source validation distributions, causing most thresholds to produce uncontrolled false alarm rates.

Note: degenerate thresholds (threshold ≥ 0.99) are marked `eligible=False` in the metrics CSV and excluded from the table above. Some degenerate rows still produce non-zero FPR on external benign (e.g., IoT LR fixed_fpr at FPR=2.5%, UNSW LR fixed_fpr at FPR=1.4%) — this is because even at threshold≈1.0, a small number of external benign flows produce scores that exceed the threshold.

**CIC-LSTM fixed_fpr (FPR=0.2%) and IoT-LSTM fixed_fpr (FPR=0.3%) are the only fixed_fpr results that provide genuine false alarm control** on external benign.

---

## Q6. Do Cross-Domain Successful Methods Show Better Benign Stability?

The most cross-domain portable methods were LR (best F1 in 4/6 directions) and LSTM (second most portable).

On external benign (default threshold):
- **LR**: CIC 6.2%, IoT 4.6%, UNSW 37.0% — mixed; UNSW-LR is the worst single result
- **LSTM**: CIC 0.0%, IoT 10.2%, UNSW 23.2% — CIC-LSTM is the best, but IoT/UNSW-LSTM fire often

**No consistent relationship between cross-domain success and benign stability.** The most cross-domain portable model (LR) is also the worst false alarm generator when trained on UNSW (37% FPR). CIC-LSTM is both cross-domain stable and benign-stable, but this appears specific to CIC's attack distribution matching well with NFS-exclusion.

---

## Q7. False Alarm Patterns: What Benign Traffic Triggers False Alarms?

Key patterns from `final_out_of_domain_benign_false_alarm_patterns.csv`:

### Dominant false alarm trigger: UDP NFS traffic (port 2049)

NFS over UDP is the dominant false alarm pattern across most models:
- NFS flows have high packet counts per flow (many small RPC requests)
- High packets_per_second (NFS batch operations)
- Low bytes_per_packet (small RPC headers)

Models trained on CIC (DoS attacks with high pps) and UNSW (Generic attacks with high flow volume) learn similar traffic signatures, creating false positives on NFS flows.

### Second pattern: Port 800 UDP traffic

Port 800 appears as the second-most alarmed traffic type for several methods. This unknown-service UDP traffic shares packet size/rate characteristics with some attack categories.

### Third pattern: High-bandwidth flows

Flows with bytes_total > 10KB are disproportionately falsely alarmed by UNSW-trained models. UNSW's Generic attack category (40k training flows) teaches models to fire on any high-volume flow.

### Quietest benign traffic: SSH (port 22) and HTTP (port 80)

TCP flows on ports 22 and 80 produce fewer false alarms than UDP NFS traffic for most models. CIC-LSTM (0 FPR at default) appears to be the only model that correctly ignores essentially all external benign traffic.

---

## Q8. Final Deployment Recommendations

### Methods safe to deploy on external benign networks (with caveats)

**CIC-trained LSTM (default or fixed_fpr):**
- Default FPR: 0.0% on this benign set
- Fixed_fpr FPR: 0.2%
- Low benign false alarm rate AND cross-domain portability on CIC→IoT direction
- Caveat: LSTM has catastrophic FPR at fixed_fpr in cross-domain settings; this benign evaluation is on a specific NFS-heavy traffic profile

**CIC-trained RF or XGB (default threshold only):**
- Default FPR: 0.3% and 0.2% respectively
- Very low false alarm rate, but also low attack detection recall (in-domain F1=0.07 and 0.13)
- val_tuned and fixed_fpr thresholds produce much higher FPR on external benign — use default threshold only

**IoT-trained CNN1D (val_tuned threshold):**
- 0.0% FPR at val_tuned threshold (which is 0.990 — very conservative)
- Low attack recall in IoT in-domain, but benign-safe
- Useful as a secondary layer with very low FPR budget

### Methods requiring caution

**UNSW-trained LR:** FPR=37% at default — would generate 6,563 false alerts per hour on this benign traffic. Cannot be deployed as-is without target-domain calibration.

**CIC-trained CNN1D:** FPR=28.5% at default (5,058 false alerts/hour). CNN1D learns features that fire broadly on UDP NFS traffic.

**UNSW-trained LSTM:** FPR=23.2% (4,122 alerts/hour). Not suitable for deployment without recalibration.

**Any val_tuned threshold (except IoT CNN1D):** Val_tuned thresholds reliably increase FPR on external benign. The val_tuned tier optimizes for attack recall, not benign specificity.

### Negative findings (mandatory)

1. **Fixed_fpr does NOT reliably control external benign FPR.** The source-side 1% FPR constraint is meaningless on external traffic. CIC RF fixed_fpr achieves 55.3% external benign FPR — 55× overshoot.

2. **UNSW-trained models are the least benign-stable across all method families.** UNSW's diverse attack training creates a broad decision boundary that misclassifies external benign NFS traffic as attacks.

3. **Cross-domain success does not predict benign stability.** LR is the most cross-domain portable method but also produces the worst UNSW-source false alarm rate (37%).

4. **DL models are not uniformly better or worse than ML models for benign stability.** CNN1D can have higher FPR than LR (28.5% vs 6.2% for CIC-trained), contradicting any assumption that DL models are more precise.

5. **The threshold portability problem extends to external benign environments:** thresholds calibrated on source benchmarks fail on real-world benign traffic, not just on attack detection in cross-domain settings.
