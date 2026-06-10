# Changelog

All notable changes to this project. Newest first. Dates are `YYYY-MM-DD`.

## Essentials

- A rebuildable **SQLite projection catalog** over raw PCS102 SQUID magnetometer traces: disk owns the bytes, the DB owns queryable metadata + calibration + lineage.
- This folder (`SQUID_data_management/`) is the SQUID-specific instance. A sibling `general_data_management/` holds the source-agnostic version.

---

## 2026-06-09

### Added

- **PPT setup-parameter extractor (`catalog/ppt_extract.py`) + `deck`/`deck_setup` tables.** Reads the measurement decks (read-only via python-pptx), parses the dated setup slides, and pulls the **calibration factor (f₀/V)** — the field that feeds PSD — plus flux jump and section-namespaced Array/SQUID V-Phi context (the parser is section-aware: `S-bias` appears in both sections; `=`/`:`/`~` all separate). `coollog propose-from-ppt` (and a deck-indexing step in `build_full_catalog.py`) print a **human-confirmed** `coollog add-cooldown` proposal per factor-bearing slide — calibration is never auto-written. Decks live in their own tables, never `raw_measurement` rows. Validated against the real decks: recovers the registered factors exactly (Sapphire_Dec2025 0.834, Sapphire_May2026 0.762, YbZn2GaO5_Dec2025 0.837); `Summary_*` decks correctly yield zero setup slides. `config.ppt_roots` + `roots.DEFAULT_PPT_ROOTS` (→ `SQUID/data-analysis/ppt`). 9 new tests. Scope (decided with the user): setup/calibration only — no slide→trace linking, no mid-cooldown change tracking (future setup comes from `auto_s_tune` → `action_log`). See `output/2026-06-09_ppt-extractor-built_summary.md`.
- **AutoSQUID `plot_psd` y-label `Φ₀²/Hz` → `f₀²/Hz`** (user request) — removes the notation split between the per-trace PSD (was Φ₀, via AutoSQUID) and the catalog's overlay (f₀). The repo and the decks both write f₀/Fo; AutoSQUID was the outlier. (Edited in the editable-installed AutoSQUID dev tree.)
- **`figure_style_guide.md` + `catalog/style.py`** — house figure style in one place (DPI 130, figsize 8×6, rcParams, standard PSD/time-series labels, log-scale `temp_color` for temperature-comparison figures). `dispatch.run_analysis`/`run_group_analysis` call `style.apply()` before every analyzer, so all dispatched figures (including future LLM-written analyzers) inherit it; `analyzers.py`'s inline dpi/figsize/label literals replaced with the style constants. Guide covers the only-through-dispatch rule, axis/unit/calibration labelling, color policy, and a new-analyzer checklist.
- **Binding `## Vocabulary` section in `CLAUDE.md`** — surge/surged = `outcome='SURGE'` (the `_SURGE` filename suffix / experiment-log label), jump = `'JUMP'`, gate-failed = `integrity_pass=0` (catch-all, never "surged"). Promoted from a buried bullet after an LLM session misread "surge" as jump.
- **Decisions recorded** (`output/2026-06-09_ppt-scope-and-figure-style_summary.md`): ppt extraction scope narrowed to **setup parameters only** (f₀/V, flux jump, Array/SQUID V-Phi: A-bias, A-flux, S-bias, offset, output — the decks are the only source of these), proposal-only via pre-filled `coollog add-cooldown`; decks/slides get **their own tables** + a link table to `raw_measurement`, never `raw_measurement` rows.

### Changed

- **`raw_measurement` jump columns renamed to the usable-prefix vocabulary:** `jump_time_s` → `usable_seconds`, plus a new `usable_points` column — matching AutoSQUID's current experiment-log ledger (which replaced `jump_time_s`/`jump_index` with `usable_seconds`/`usable_points`). `enrich_from_logs` reads the new columns **and falls back to the legacy `jump_time_s`/`jump_index`** — the format every already-acquired trace carries — so a rebuild back-fills the usable prefix for the existing corpus instead of nulling it; the legacy `-1`/empty no-jump sentinels map to NULL. `compute_usable_s` now prefers the log's `usable_seconds` (then clean full-duration, then the gate's `at chunk N/nc` prefix). `db.py` migrates older catalogs (column rename + add).

### Fixed

- **`pcs102_meta` n_points off-by-one on decimal usable-count filenames.** AutoSQUID tags a truncated clean prefix like `8p2Mpts`; the parser computed `int(8.2 × 1e6)`, which floating-point-truncated to `8199999`. Now `round()`, so it parses to `8200000` (integer and `k`/`M` cases unchanged).
- **`catplot --outcome <surged|jumped|bad_baseline>` now also works for the per-trace analyzers** (`psd`, `time_series`), not just group overlays: `run_analysis` gained an `include_all` flag that `catplot` sets for a non-clean outcome, so selecting a gate-failed trace no longer raises "no clean traces match".

## 2026-06-06

### Added

- **Per-machine `config.json`** (git-ignored; `config.example.json` template + `build_full_catalog.py --init`) read by `catalog/config.py`: deployment paths `data_roots` (where raw `DAQ_*.txt` live, crawled), `ppt_roots` (parameter decks; declared for future tooling), and `db`. Falls back to the dev-tree default when unconfigured; `build_full_catalog.py` gains `--root` / `--db` overrides. Makes a fresh clone deployable on any machine without editing code — fixes the data root previously being hard-wired to the repo's position in the tree.
- **`catplot --outcome surged|jumped|clean|bad_baseline`** — selects by the `outcome` column (the acquisition's own label), normalizing the word to `SURGE`/`JUMP`/`CLEAN`/`BAD_BASELINE` via `dispatch.normalize_outcome` and auto-including gate-failed traces. So "surged" no longer accidentally returns jumps (which happens when filtering on `integrity_pass=0`, the catch-all anomaly gate).

### Fixed

- `build_full_catalog.py` no longer crashes on an empty catalog (0 rows): it prints a clear "no measurements indexed / point the data roots here" hint instead of a `NoneType` formatting error.

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
