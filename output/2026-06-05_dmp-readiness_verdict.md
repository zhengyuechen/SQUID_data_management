# Data-Management Catalog — Readiness Verdict & Next Step

**Date:** 2026-06-05
**Question answered:** "Read the plan under `data_management_plan/` and tell me what the next step should be."
**Analyzed:** `data_management_plan/2026-06-05_lab-data-management-catalog_plan.md` (the approved design), ground-truthed against the actual codebase by a 7-agent read-only verification workflow (run `wf_48fa73a9-3e2`).
**Verdict in one line:** The design is sound and *is* ready to become an implementation plan — but verification found **1 blocker only you can resolve (the data root) + 4 adapter gaps** the plan must encode. Do not start coding the schema until the data-root question is answered.

---

## What was verified (7 load-bearing claims)

| Claim | Status | What's actually true on disk |
|---|---|---|
| `load_pcs102_data()` exposes DATE/TIME/DATAPOINTS/SCANINTVAL | ✅ confirmed | Returns `(data, metadata_dict)`. Header fields present but as **strings**; provides `scan_interval_parsed` (float) + `n_points_parsed` (int). Crawler must build its own datetime from separate DATE+TIME. |
| `check_daq_jump()` returns `integrity_pass, jump_V, frozen_frac, fail_tag` | ⚠️ partial | Returns `(passed: bool, info: dict)`. Has `jump_V` ✅. **No `fail_tag` taxonomy** — only `fail_jump`/`fail_flat` booleans; JUMP/SURGE/RAIL/BADBASE is invented. `frozen_frac` is ambiguous: code has both `flat_fraction` and `longest_flat_run_frac`. |
| `squid_calibration.py` holds 0.837 / 0.834 / 0.762 per cooldown | ✅ confirmed | Two dicts: `CALIBRATION_FO_PER_V` (label→factor) + `COOLDOWN_BY_CONTEXT` (path-substring→label), resolved by `factor_for(path)`. Date-ranges & S-bias live in **comments only** — should become columns. |
| AutoSQUID has `plot_psd`/`plot_run`/`plot_overlay`, Config, `scan_indices()` | ✅ confirmed | All present at `SQUID/automation/AutoSQUID/src/AutoSQUID/`. Signatures captured below. They **read files from disk** (take a filename/Config, not arrays) and `plt.show()` (no file write) — wrappers must handle output paths. |
| `psd_cache_index.csv` = 84-row validation ground truth | ⚠️ partial | It's **82 rows, not 84**. Columns: `key, kind, interval, T_mK, n_seg_main, n_seg_low, jump_V, factor`. `jump_V`→raw_measurement, but `n_seg_main/n_seg_low`→PSD params (derived_product). Validation is a **join**, not a raw-table dump. |
| Crawler can resolve sample+cooldown **purely from folder path** | ⚠️ partial | Sample (SAMPLE-* vs BKG) resolves from folder ✅. **Cooldown does NOT** — `factor_for()` inspects the `Bkg-DAQ` *filename prefix*. And **folder temp ≠ file temp**: `BKG_44mK/` contains `DAQ_100us_253mKMXC_...` (253 mK). Temp must come from the **filename**. |
| `organize_project.py` enforces typed-subfolder layout; `experiment_log.txt` is per-folder operational truth | ⚠️ partial | `organize_project.py` only routes `build_*.py`→`builders/` and LaTeX→`latex/`. **`experiment_log.txt` exists in exactly ONE place** (`automation/scripts/test_output/`) — it is NOT a per-folder convention across the corpus. Drop it as an assumed ingest source. |

---

## The blocker (only you can resolve): where does the crawler crawl, and what validates it?

The design says *"the raw corpus the crawler ingests"* lives in `SQUID/data/` and is validated against `psd_cache_index.csv`. On disk **today**:

- **`SQUID/data/` is empty** — just a `.DS_Store`.
- The **293 real DAQ files** live under `SQUID/denoising/Trial-with-Spectral-Substraction/Dec-2025-VAE/{SAMPLE-YbZnGaO4, BKG}/<TEMP>/`.
- `psd_cache_index.csv` (the validation target) was built against a **third, now-deleted layout** (`4us/ 20us/ 100us/ 500us/` flat-by-interval; its `.npz` `rel` paths like `4us/DAQ_4us_100mK_10Mpts_1.txt` no longer resolve).

So "crawl `SQUID/data/`, diff against `psd_cache_index.csv`" cannot run as written — the source is empty and the ground truth points at files that moved. **Decision needed:** (a) which directory is the canonical crawl root, and (b) is `psd_cache_index.csv` still a valid ground truth, or do we re-baseline it from whatever root we pick?

> **RESOLVED (2026-06-05, user):** The `SQUID/denoising/**` tree is *working/derived data, not raw* — never crawl it, and the `psd_cache_index.csv` in it is **not** a validation target. The one canonical raw root is **`SQUID/data/`** (currently empty; will be populated). The crawler must accept **multiple input roots** with `SQUID/data/` as one, and **auto-digest** new files on the next (idempotent, incremental) re-crawl. Real-data validation (incl. the lab's own `PSD_*Seg.txt` cross-check) is deferred until raw data lands in `SQUID/data/`; the prototype is proven on **synthetic PCS102 fixtures** + self-consistent success criteria. Full build steps: [`2026-06-05_catalog-prototype-implementation_plan.md`](./2026-06-05_catalog-prototype-implementation_plan.md).

---

## The 4 adapter gaps to bake into the implementation plan

1. **`fail_tag` doesn't exist.** `check_daq_jump` returns `(passed, info)` with `fail_jump`/`fail_flat` booleans. Either store those two flags directly (simplest), or write a thin categorizer if the JUMP/SURGE/RAIL/BADBASE taxonomy is wanted. Pin `frozen_frac` = `longest_flat_run_frac` (the field the gate actually fails on), not `flat_fraction`.
2. **Calibration is path + filename, not folder-only.** Reuse the existing `factor_for()` / `COOLDOWN_BY_CONTEXT` rather than inventing a folder rule; keep its KeyError-on-unmapped behavior (surface, don't guess). Migrate the comment-only date-range + S-bias into the `cooldown` table columns.
3. **Folder temperature is decorative — trust the filename.** `temp_mK` comes from parsing the filename (`§5 step 4`); folder names like `BKG_44mK/` are unreliable labels. Make this explicit so no one wires the ingest to the folder.
4. **Validation is a raw⨝derived join, 82 rows.** `jump_V` lives on `raw_measurement`; `n_seg_main`/`n_seg_low` are PSD analysis params on `derived_product.scalars`. Restate the success criterion as a join that reproduces 82 rows (fix the "84"). Drop `experiment_log.txt` as an ingest input — rows come from the DAQ files themselves, which the design already does.

None of these touch the architecture. The projection-catalog model, the open/closed `derived_product` table, and the human-editable playbook all survive verification intact — these are field-name/wiring reconciliations, not redesigns.

---

## Recommended next step

1. **You decide (now):** canonical crawl root + validation baseline (the blocker above).
2. **Then write the implementation plan** for the provable-now slice (schema → crawl → registry+3 analyzers → dispatch → playbook → demo notebook), with the 4 adapter gaps written in as explicit reconciliation tasks and the validation restated as the 82-row join.
3. **Then build** artifacts 1→6 in dependency order and run the demo notebook's success checks.

Building the schema before step 1 risks coding `raw_measurement.path` against an empty directory and a `fail_tag` column that has no source.

---

### Reference signatures captured during verification

- `load_pcs102_data(filepath) -> (data: np.ndarray, metadata: dict[DATE,TIME,CHANNELS,DATAPOINTS,SCANINTVAL,scan_interval_parsed,n_points_parsed])`
- `check_daq_jump(v, n_chunks=2000, jump_thresh_V=0.05, flat_std_frac=0.05, flat_run_frac=0.02) -> (passed: bool, info: dict{jump_V, jump_at_frac, flat_fraction, longest_flat_run_frac, fail_jump, fail_flat, ...})`
- `factor_for(path_or_name: str) -> float` (over `CALIBRATION_FO_PER_V` + `COOLDOWN_BY_CONTEXT`)
- `plot_psd(path, filename, conversion=1, P=(10,100,1000,10000), window="hanning", clean_only=True)` — reads DAQ file, Welch PSD, `plt.show()`
- `plot_run(cfg, filename_list=None)` — reads clean traces + TEMP_*.csv, `plt.show()`
- `plot_overlay(t, v, temp_t, temp_T, title="")` — raw arrays in, twin-axis figure
- `scan_indices(outdir, core) -> (n_clean, next_idx)` — resume primitive
