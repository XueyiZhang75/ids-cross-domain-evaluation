# Pipeline Guardrails

Quick-reference checklist of rules that every script, notebook, and code
review in this project must respect. Violations of any item below invalidate
the affected experiment results.

---

## 1. Formal Input

- **The formal input is raw PCAP.** All flow-level features and packet-level
  sequences must be derived from `.pcap` / `.pcapng` files through the
  project's own extraction pipeline.
- Public CSV or precomputed flow files (e.g., those distributed with
  CIC-IDS2017) may be used **only** as:
  - label references (to assign ground-truth labels to extracted flows)
  - sanity checks (to verify extraction correctness)
- Public CSVs must **never** be loaded as `X_train` or `X_test`.

**How to check:** grep the codebase for `pd.read_csv` calls that touch
`data/raw/*/label_ref/` — they should only produce label columns, never
feature columns.

---

## 2. No Data Leakage via Splits

- **Do not randomly shuffle individual flows** before splitting into
  train / val / test. Flows from the same session, IP pair, or time window
  are correlated; random shuffling leaks information across splits.
- Splits must be based on capture-level units: capture day, scenario ID,
  time window, or source file.
- The split strategy and its parameters must be recorded in the experiment's
  config file and logged at runtime.

**How to check:** search for `train_test_split` or `shuffle=True` — each
occurrence must use a group-aware splitter (e.g., `GroupShuffleSplit`) or
an explicit capture-unit key.

---

## 3. Transfer Discipline

- In cross-domain experiments (E2–E4), **target-domain data must not be
  used for**:
  - model weight updates (training or fine-tuning)
  - decision-threshold selection
  - score calibration (Platt scaling, isotonic regression, etc.)
- Thresholds and calibrators must be fitted on **source-domain validation
  data only**, then applied as-is to the target domain.

**How to check:** any `fit()` or `calibrate()` call in transfer experiment
code must receive source-domain data. The target-domain data path should
appear only inside `predict()` / `transform()` / metric computation.

---

## 4. Scaler / Normalizer Fitting

- All scalers, normalizers, and encoders must be **fitted on the training
  split only**.
- The fitted object is then used to `transform()` validation, test, and
  any target-domain data — never `fit_transform()` on those splits.
- Save the fitted scaler alongside the model artifact so that inference
  on new data uses the same transform.

**How to check:** search for `.fit(` and `.fit_transform(` — every call
must receive `X_train` (or equivalent). Calls on `X_val`, `X_test`, or
target-domain data are bugs.

---

## 5. Exclusion Logging

- When flows, packets, or labels are dropped from the pipeline (e.g.,
  unsupported protocol, missing fields, excluded label category), the
  exclusion must be **logged with a reason and count**.
- Never use bare `dropna()` or `df = df[mask]` without logging how many
  rows were removed and why.
- Exclusion decisions (which labels to keep or exclude) are recorded in
  `data/external/label_mapping_master.csv` **before** any experiment runs.
  They must not be revised based on model performance.

**How to check:** every `drop`, `dropna`, or boolean-mask filter in
data-processing code should be preceded or followed by a `logger.info`
or `logger.warning` that reports the count and reason.

---

## 6. Data Path Policy

- **Large data files live outside the repository.** Raw PCAPs, label
  reference CSVs, extracted flow tables, and feature matrices are stored on
  a separate data drive (e.g., `D:\ids_project_data\`), not under the
  in-repo `data/` tree.
- The authoritative paths are in `configs/datasets.yaml`. All scripts must
  resolve data locations from that config — never hardcode absolute paths
  in source code.
- The in-repo `data/` directory stores only documentation, the inventory
  CSV, label mappings, and other lightweight metadata.

**How to check:** `git ls-files data/` should return only small metadata
files. No `.pcap`, `.pcapng`, or multi-MB CSVs should appear.

---

## 7. Artifact Caching and Traceability

- Every intermediate artifact (extracted flows, feature matrices, sequence
  arrays, split indices) must be:
  - written to a **deterministic path** derived from the dataset name and
    config hash or version tag
  - accompanied by a sidecar log or metadata file that records which config
    produced it
- Re-running the same config on the same raw data must produce
  byte-identical output (set random seeds; pin library versions).
- Do not overwrite artifacts silently. If an output file already exists,
  either skip with a log message or raise an error — never silently
  replace it.

**How to check:** list the external interim/processed directories — every
file should be traceable to a config in `configs/` and a script invocation
in `reports/logs/`.

---

## 8. No Fabrication

- Do not invent file paths, dataset sizes, experiment results, or metric
  values.
- If a pipeline stage is not yet implemented, raise `NotImplementedError`
  or write a `TODO` — never return synthetic placeholder data that could
  be mistaken for real output.
