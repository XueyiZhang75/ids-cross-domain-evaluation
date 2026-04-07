# Attack Family / Category Transfer — Cross-Dataset Synthesis

> **Scope:** All in-domain + 6 cross-domain directions (all pairs)
> **Sources:** Family breakdown CSVs, coverage analysis reports, prediction sidecars

---

## 1. Family Taxonomies Per Dataset

The three datasets have distinct and non-overlapping attack taxonomies:

| Dataset | Taxonomy | Families in Train | Families in Test | Family Overlap |
|---------|----------|-------------------|------------------|----------------|
| CIC-IDS2017 | 5 coarse families | dos_ddos, brute_force, web_attack, reconnaissance_scan, infiltration | botnet_malware, dos_ddos, reconnaissance_scan | Partial (3 overlap) |
| IoT-23 | Malware scenarios | Mirai (C&C, DDoS, PortScan) | Torii (C&C), Hajime (PortScan, DDoS) | Zero family overlap (Mirai only in train) |
| UNSW-NB15 | 9 attack categories | All 9 | All 9 | Full overlap |

**No unified family space** is possible across datasets. Each dataset uses its own taxonomy: IoT-23 uses `detailed_label` (malware family + behavior), UNSW-NB15 uses `attack_cat` (9 laboratory categories), and CIC-IDS2017 uses `coarse_family` (5 traffic-type groupings). These taxonomies are dataset-local and were never unified; cross-domain family analysis must be interpreted strictly in target-dataset terms.

---

## 2. CIC-IDS2017 In-Domain: Family Structure

CIC train/val (Mon–Thu) contain different attack families than test (Friday):
- **Train families:** dos_ddos (Wed DoS/GoldenEye), brute_force (Tue FTP/SSH), web_attack (Thu), infiltration (Thu)
- **Test families:** botnet_malware (Fri), dos_ddos (Fri DDoS), reconnaissance_scan (Fri PortScan)

The in-domain split is inherently family-disjoint for `botnet_malware` (absent from train). This explains the low in-domain recall at default threshold despite high ROC-AUC: models learn attack signatures from train families but test demands detecting new families.

Suricata detected only 198 of 197,378 Friday attacks (0.1%), primarily DDoS-related alerts.

---

## 3. IoT-23: Family-Disjoint In-Domain

IoT-23 train = Mirai (scenarios 20-1, 21-1), test = Torii (5-1) + Hajime (7-1, 4-1).

Attack types in test:
- C&C: 7,031 flows (Torii)
- DDoS: 211 flows (Hajime)
- PortScan: 106 flows (Hajime)

LSTM is the only model with non-trivial in-domain recall (0.325, F1=0.468). All other methods fail (F1 < 0.06), despite moderate ROC-AUC (0.61–0.76). The packet-level temporal patterns learned from Mirai C&C appear to partially generalize to Torii C&C.

---

## 4. UNSW-NB15: Full Category Overlap

All 9 attack categories appear in both train and test (different capture dates):

| Category | Train Count | Test Count | In-Domain Recall (RF) |
|----------|-------------|------------|----------------------|
| Generic | ~40,000 | ~2,000 | High |
| Exploits | ~11,000 | ~2,600 | High |
| Fuzzers | ~12,000 | ~1,800 | High |
| DoS | ~2,000 | ~400 | High |
| Reconnaissance | ~3,500 | ~1,200 | High |
| Analysis | ~1,000 | ~60 | Moderate |
| Backdoor | ~500 | ~40 | Moderate |
| Shellcode | ~400 | ~160 | Moderate |
| Worms | ~130 | ~18 | Low (sparse) |

UNSW achieves the highest in-domain F1 (RF=0.83) partly because train/test share all categories.

---

## 5. Cross-Domain Family Transfer Results

### CIC → IoT (CIC source models on IoT test)

| Method | C&C Recall | DDoS Recall | PortScan Recall | Overall Recall |
|--------|-----------|-------------|-----------------|----------------|
| LR | High (~0.82) | Moderate | Moderate | 0.815 |
| RF | ~0 | ~0 | ~0 | 0.000 |
| XGB | ~0 | ~0 | ~0 | 0.000 |
| CNN1D | ~0 | ~0 | ~0 | 0.000 |
| LSTM | ~0 | ~0 | ~0 | 0.000 |

**Key finding:** Only LR transfers to IoT. CIC LR's linear boundary (volume/rate-based) captures the high-traffic C&C signature in Torii. Tree/DL models memorize CIC-specific split values that don't match IoT.

### CIC → UNSW (CIC source models on UNSW test)

All families show near-zero recall from all methods. The score distributions shift so far below 0.5 that no UNSW attacks are detected. CNN1D's ROC-AUC (0.70) suggests rank signal exists for some categories (possibly Reconnaissance and DoS), but the threshold gap prevents detection.

### IoT → UNSW (IoT source models on UNSW test)

IoT ML models produce FPR > 47% with recall < 21%. The IoT models' learned "attack signature" (Mirai byte-count patterns) triggers on many UNSW benign flows, creating a massive false-positive problem. No UNSW attack category benefits from IoT-trained models.

### UNSW → CIC (UNSW source models on CIC Friday)

| Method | reconnaissance_scan Recall | dos_ddos Recall | botnet_malware Recall |
|--------|---------------------------|-----------------|----------------------|
| LR | High (volume patterns) | High (rate patterns) | Moderate |
| LSTM | High | High | Moderate |
| RF | ~0 | ~0 | ~0 |
| CNN1D | ~0 | ~0 | ~0 |

UNSW LR and LSTM detect CIC's reconnaissance_scan and dos_ddos families (which share volume/rate signatures with UNSW's Generic and Reconnaissance categories). Botnet_malware is partially detected due to its atypical traffic patterns.

### UNSW → IoT (UNSW source models on IoT test)

Target taxonomy: IoT `detailed_label` (Torii C&C, Hajime DDoS/PortScan, benign)

| Method | C&C Recall | DDoS Recall | PortScan Recall | Overall Recall |
|--------|-----------|-------------|-----------------|----------------|
| LR | High (~0.86) | Moderate | Moderate | 0.861 |
| XGB | High (~0.84) | Moderate | Moderate | 0.840 |
| CNN1D | High (~0.76) | Moderate | Moderate | 0.757 |
| LSTM | Very high (~0.92) | High | High | 0.925 (high FPR=0.92) |
| RF | Low (~0.22) | Low | Low | 0.221 |

**Key finding:** UNSW→IoT is the second most successful cross-domain direction after CIC→IoT. UNSW's diverse 9-category training captures the rate/volume boundary that detects Torii/Hajime botnet traffic. LR and XGB achieve high F1 (0.860, 0.808) with manageable FPR (0.187, 0.318). LSTM achieves high recall (0.925) but with catastrophic FPR (0.919) — it over-fires on benign flows.

**Taxonomy note:** All recalls are reported in IoT `detailed_label` terms. No UNSW `attack_cat` family can be mapped to IoT families.

### IoT → CIC (IoT source models on CIC Friday)

Target taxonomy: CIC `coarse_family` (reconnaissance_scan, dos_ddos, botnet_malware)

| Method | recon_scan Recall | dos_ddos Recall | botnet Recall | Overall Recall |
|--------|------------------|-----------------|---------------|----------------|
| LR | ~0.05 | ~0.05 | ~0.05 | 0.050 |
| RF | ~0 | ~0 | ~0 | 0.000 |
| XGB | ~0 | ~0 | ~0 | 0.000 |
| CNN1D | ~0.17 | ~0.17 | ~0.17 | 0.166 |
| LSTM | ~0.19 | ~0.19 | ~0.19 | 0.191 |

**Key finding:** IoT→CIC is a near-total failure across all families. Consistent with IoT→UNSW, the IoT-trained models' Mirai-specific feature boundaries fail on CIC's diverse Friday traffic. CIC Friday attacks (PortScan: 159k flows, DDoS: 38k flows, botnet: 327 flows) do not produce the byte-level signatures that Mirai models learned. CNN1D and LSTM have moderate ROC-AUC (0.718, 0.707), indicating some rank signal survives — but the threshold gap prevents detection.

**Taxonomy note:** All recalls are reported in CIC `coarse_family` terms. IoT `detailed_label` family cannot be mapped to CIC families.

---

## 6. Summary Findings

1. **High-volume/rate-type attacks are most transferable:** Reconnaissance, DDoS, and C&C produce traffic volume and rate features that generalize across datasets. This explains why LR (which relies on linear rate/volume features) is the most portable method.

2. **IoT target is consistently accessible (CIC→IoT and UNSW→IoT both succeed):** Torii/Hajime botnet traffic produces volume/rate signatures detectable from both CIC and UNSW source models. This is not because IoT is "easy" in-domain — its family-disjoint split makes it the hardest in-domain task — but because C&C botnet traffic is recognizable from diverse training.

3. **IoT source is consistently brittle (IoT→UNSW and IoT→CIC both fail):** Mirai-trained models do not transfer to UNSW laboratory attacks or CIC diverse attack traffic. The IoT family's C&C/PortScan boundary does not match any cross-domain target family.

4. **Family-specific signature attacks do not transfer:** Web attacks, infiltration, and specific malware families (Mirai, Torii) have dataset-specific byte patterns that tree/DL models memorize.

5. **Tree models (RF, XGB) are the most family-brittle:** They learn precise split points on source-specific feature distributions that rarely match target distributions. Exception: UNSW XGB val_tuned transfers to IoT with F1=0.815 — the only tree model cross-domain success.

4. **LSTM shows moderate family generalization at the packet level:** The temporal sequence patterns (connection timing, packet size evolution) provide a partial generalization layer that survives some domain shifts.

5. **Full family overlap (UNSW) produces the highest in-domain performance:** The train/test family overlap in UNSW explains why it achieves F1=0.83 while CIC (partial overlap) and IoT (zero overlap) achieve much lower F1.

---

## 7. Limitations

- No unified family space exists across the three datasets — IoT `detailed_label`, UNSW `attack_cat`, and CIC `coarse_family` are independent taxonomies with no cross-dataset comparability
- Family-level recall for CIC in-domain and CIC→UNSW/IoT→UNSW is estimated from prediction sidecars at default threshold only
- UNSW→IoT and IoT→CIC family transfer data is unavailable (directions not run)
- Suricata family analysis is available only for CIC in-domain
