# Weekly summary — week of 2026-06-06

## Essentials
- Built the **data-management catalog** and proved it on real data: **225 traces** from `SQUID/data` across **3 cooldowns** (YbZn 0.837 · Sapphire-Dec 0.834 · Sapphire-May→Jun 0.762). Crawl + integrity gate + date-based calibration + lineage all working; **55 tests pass**.
- **Generic plotting** via one `catplot` CLI (`psd`, `time_series`, `psd_overlay`, `raw_overlay`); jump/surge traces partly recoverable (`usable_s`), frozen ones identified.
- **Per-cooldown logbooks** (V-Phi setup + notes from the measurement PPTs) + a human-readable calibration table in `cooldowns/`.
- Conventions set: `figures/` (plots), `output/` (narrative), `cooldowns/` (logbooks), Essentials-first markdown.
- **Next:** Postgres + file-watcher (Phase 1), XRD ingest, the LLM query layer.
