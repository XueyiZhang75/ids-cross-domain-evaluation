# Unified Label Schema

## Overview

This document defines the three-tier label schema used across all datasets in
the project. Every flow (or packet sequence) that enters the evaluation
pipeline must carry labels at all three tiers. The schema enables binary
detection as the primary task while preserving enough granularity for
per-family analysis and cross-domain degradation source decomposition.

---

## Tier 1 — Binary Label

The primary classification target.

| Value | Meaning |
|---|---|
| `benign` | Normal, non-malicious traffic |
| `attack` | Any malicious or anomalous traffic |

### Why binary first?

- Binary detection answers the most operationally relevant IDS question:
  "Is this flow malicious?"
- It provides a single, comparable evaluation axis across all three paradigms
  (rule-based, ML, DL) and across all datasets.
- Threshold analysis (E6) and cross-domain transfer experiments (E2–E4)
  are cleanest when defined over a single decision boundary.
- Multi-class evaluation can be layered on top later without changing the
  underlying data.

---

## Tier 2 — Coarse Family Label

A small, fixed vocabulary of attack families that is **shared across all
datasets**. This tier exists between the binary label and the raw
dataset-specific label.

| Family | Description | Example original labels |
|---|---|---|
| `dos_ddos` | Denial-of-service and distributed DoS | DoS Hulk, DDoS LOIC, DoS Slowloris, … |
| `brute_force` | Credential brute-forcing | FTP-Patator, SSH-Patator, Brute Force -Web, … |
| `web_attack` | Application-layer web attacks | Web Attack – XSS, Web Attack – SQL Injection, … |
| `botnet_malware` | Botnet C2 and malware traffic | Botnet ARES, Backdoor, Worms, … |
| `infiltration_exploit` | Host infiltration and exploit delivery | Infiltration, Exploits, Shellcode, … |
| `reconnaissance_scan` | Scanning and reconnaissance | PortScan, Reconnaissance, Analysis, … |
| `other_attack` | Attacks that do not fit the above | Generic, Fuzzers, or dataset-specific types |

### Purpose of coarse families

1. **Common-subset analysis.** Not every dataset contains every attack type.
   Coarse families let us identify the *shared attack families* across datasets
   and restrict cross-domain comparisons to the common subset when needed
   (e.g., degradation source decomposition in E3).

2. **Per-family detection breakdown.** Even under binary classification, we can
   stratify results by coarse family to reveal which attack types degrade most
   under domain shift.

3. **Stable vocabulary.** Original labels differ wildly across datasets (naming
   conventions, granularity, taxonomy). Coarse families provide a stable,
   human-readable intermediate layer that does not change when a new dataset
   is added.

### Mapping rules

- Each original attack label maps to **exactly one** coarse family.
- `benign` rows do not receive a coarse family (the field is left empty or
  set to `N/A`).
- If an original label is ambiguous, the mapping decision and rationale must
  be documented in `label_mapping_master.csv` (see the `notes` column).
- The `other_attack` family is a catch-all. Use it sparingly — prefer
  assigning to a specific family when the attack intent is clear.

---

## Tier 3 — Original Label

The exact label string as it appears in the dataset's public label reference
file, **preserved verbatim** without renaming.

### Why keep original labels?

- **Traceability.** Any evaluation result can be traced back to the exact
  source label, making it possible to audit the mapping.
- **Fine-grained post-hoc analysis.** After the main experiments, we may want
  to inspect specific original categories (e.g., "DoS Slowloris" vs.
  "DoS GoldenEye") without re-running the pipeline.
- **Reproducibility.** Other researchers can verify or revise the coarse-family
  mapping independently if the original label is preserved.

---

## Exclusion Policy

Some original labels may need to be **excluded** from the evaluation pipeline.
An excluded flow is removed from all splits and does not count toward any
metric.

### When to exclude

| Reason | Example |
|---|---|
| **Ambiguous ground truth** | Label is known to be noisy or contradictory in the dataset documentation |
| **Insufficient samples** | Fewer than a minimum threshold of flows (e.g., < 50), making stratified splitting unreliable |
| **Not applicable** | Label represents background noise or infrastructure artifacts, not a meaningful traffic class |
| **Duplicate / alias** | Two labels in the same dataset refer to the same activity; keep one, exclude the other |

### How to record exclusions

In `data/external/label_mapping_master.csv`, set:
- `keep_or_exclude` = `exclude`
- `exclude_reason` = one of: `ambiguous`, `insufficient_samples`,
  `not_applicable`, `duplicate`, or a free-text explanation
- `notes` = any additional context

Exclusion decisions must be made **before** training and must not be revised
based on model performance.

---

## File Locations

| Artifact | Path | Git-tracked |
|---|---|---|
| This schema document | `docs/label_schema.md` | Yes |
| Master mapping table | `data/external/label_mapping_master.csv` | Yes |

---

## How to Use This Schema

1. **Before any modeling**, fill in `label_mapping_master.csv` for every
   original label in every dataset. Use this document as the reference for
   valid `binary_label`, `coarse_family`, and `keep_or_exclude` values.

2. **During flow labeling**, join extracted flows with the master mapping to
   assign all three tiers. Flows whose original label is not found in the
   mapping table must be flagged (not silently dropped).

3. **During evaluation**, use `binary_label` as the primary target. Use
   `coarse_family` for per-family breakdowns and cross-domain common-subset
   analysis. Use `original_label` for traceability and fine-grained post-hoc
   inspection.
