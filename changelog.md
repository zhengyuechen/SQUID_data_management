# Changelog

All notable changes to this project. Newest first. Dates are `YYYY-MM-DD`.

## Essentials

- A rebuildable **SQLite projection catalog** over raw PCS102 SQUID magnetometer traces: disk owns the bytes, the DB owns queryable metadata + calibration + lineage.
- This folder (`SQUID_data_management/`) is the SQUID-specific instance. A sibling `general_data_management/` holds the source-agnostic version.

---

## 2026-06-06

### Changed
- **Restructured** into `data_management_plan/SQUID_data_management/` (this repo, with full history) and a new sibling `general_data_management/`. The parent `data_management_plan/` is now a plain container holding both independent repos.
- **Calibration data moved out of Python into the database.** `catalog/calibration.py` is now resolve-logic only; the per-cooldown factors (`f0_per_volt`, `s_bias_ma`, date ranges) live in `catalog.sqlite`'s `cooldown` table, written via `register_cooldown` / the new `coollog add-cooldown` CLI. No calibration constants in any source file.
  - `seed_lookups` now only ensures the instrument row; cooldowns persist in the catalog across rebuilds and are back-filled onto already-crawled traces via `reresolve_cooldowns`.
  - Tests register their own cooldowns via a `seed_test_cooldowns` fixture (cooldowns are operational data, not baked into the app).
  - `roots.py` updated for the deeper folder location (`parents[1]` → `parents[2]`).

### Added
- `coollog add-cooldown` and `coollog registry` CLI commands (edit/list the calibration registry held in `catalog.sqlite`).
- This `changelog.md`.

## 2026-06-05

### Added
- Initial **SQLite projection catalog**: schema spine (`sample`, `instrument`, `cooldown`, `raw_measurement`, `derived_product`, `product_input`), idempotent + incremental crawl, AutoSQUID-backed reader and integrity gate, date-based cooldown/calibration resolution, the open/closed analyzer + dispatch + registry pattern, lineage (figure ↔ raw, both directions), and per-cooldown markdown logbooks.
- CLIs: `build_full_catalog.py`, the generic `catplot.py` dispatcher, and `coollog.py`.
- Test suite over synthetic PCS102 fixtures; conventions for figures/, narrative `output/`, weekly recaps, and Essentials-first markdown.
- First public GitHub publish.
