# Public Release Publish Audit

> **Date:** 2026-04-06
> **Branch:** main
> **Remote:** https://github.com/XueyiZhang75/ids-cross-domain-evaluation.git

---

## Export Source

- Source: local full working repository (retained intact, not modified)
- This directory: clean public-release export (white-list copy only)

## Secrets Scan

Checked: GitHub tokens, OpenAI keys, passwords, api_key, session tokens.
**Result: CLEAN — no secrets found.**

Local data path `D:/ids_project_data/` was genericized to `<external_data_root>/` in README.

## Large File Scan

- Files >100 MB tracked: **0**
- Files 50–100 MB tracked: **0**
- Files 10–50 MB tracked: **0**
- `reports/predictions/` (large CSVs): **excluded**

## Excluded from Public Release

| Directory / Pattern | Reason |
|--------------------|--------|
| `docs/internal/` | Internal process history and audit docs |
| `archive/` | Internal archived artifacts |
| `data/` | Data directory (external data not in repo) |
| `reports/predictions/` | Large prediction sidecars (13–21 MB each); reproducible |
| `PROJECT_STATUS.md` / `EXPERIMENT_LOG.md` | Root stubs not needed in public release |
| `scripts/phase3-6/` | Internal analysis scripts |
| Phase audit / protocol / preflight / patch MDs | Internal process documents |

## Directory Summary

```
ids-cross-domain-evaluation-release/
├── README.md
├── requirements.txt
├── DECISIONS.md
├── .gitignore
├── publish_audit.md
├── publish_inventory.csv
├── reports/
│   ├── final/   (8 MDs + 17 CSVs)
│   └── figures/final/   (11 PNGs)
├── scripts/final/generate_final_figures.py
├── src/
├── configs/
└── docs/   (public protocol docs only — no internal/)
```

## Commit

- Message: `Publish cleaned public-release repository`
- Hash: `7be1c47`

## Push

- Target: `origin main --force`
- Result: **SUCCESS** — `+ 986d51f...7be1c47 main -> main (forced update)`
