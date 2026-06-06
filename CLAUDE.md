# CLAUDE.md — Data-Management Catalog

A rebuildable **SQLite projection catalog** over the lab's raw PCS102 SQUID traces. **Disk owns the bytes; the DB (`catalog.sqlite`) owns queryable metadata + lineage.** Built 2026-06-05; see the broader SQUID/calibration context in the parent `projects/CLAUDE.md` (auto-loads with this file). Durable narrative: the dated `*_summary.md` / `*_report.md` / `*_verdict.md` / `*_plan.md` files in **`output/`**.

## Goal (where this is heading)

End state: a **central lab data-management system** — a server-rack machine wired to every instrument PC, holding one SQL database of all measurement metadata + lineage + calibration, that **runs analysis automatically** (one raw SQUID trace → PSD / time-series / overlay; eventually a refined XRD figure *while* a scan runs). Raw bytes always stay on disk; the DB owns metadata, lineage, and calibration. A deterministic engine makes the routine products; a local **LLM sits on top later** for English→query and novel analysis.

Four subsystems, in dependency order — **the catalog is the foundation everything else needs**:

1. **SQL metadata catalog** — *this project* (built, SQLite).
2. **Sync** instrument-PC → server.
3. **On-acquisition real-time analysis** (hardest; built last).
4. **LLM auto-plotting / natural-language query**.

Roadmap: **Phase 0** SQLite on a laptop (now — done) → **Phase 1** Postgres on the central server + a file-watcher daemon (same schema, engine swap) → **Phase 2** LLM layer → on-acquisition analysis. The schema is **instrument-agnostic**: adding XRD / fridge data is an `INSERT`, not a rewrite. Full design + success criteria: `output/2026-06-05_lab-data-management-catalog_plan.md`.

## Run it

```bash
pip install AutoSQUID     # once: AutoSQUID + nidaqmx + pyserial (import fine w/o hardware)
python -m pytest tests/ -q                        # 47 tests; run FROM this folder (conftest.py puts it on sys.path)
python scripts/build_full_catalog.py                      # build/refresh catalog.sqlite over all of SQUID/data (idempotent + incremental)
python scripts/catplot.py psd_overlay --temp 50 --cooldown YbZn2GaO5_Dec2025   # plot ANY selection -> figure + indexed
python scripts/coollog.py show YbZn2GaO5_Dec2025                                # per-cooldown setup (V-Phi, restore values) + notes
python scripts/coollog.py note YbZn2GaO5_Dec2025 --phase run "base temp 10 mK"  # append a lab note during calibration/run
python scripts/coollog.py add-cooldown <label> --sample S --start 2026-05-18 --end 2026-06-30 --f0 0.762 --s-bias 0.065  # register a cooldown's calibration (no Python edits)
python scripts/coollog.py registry                                             # list registered cooldowns (dates, f₀/V, S-bias)
```

`scripts/build_full_catalog.py` = seed (UPSERT cooldowns) → crawl (skips unchanged, reads new) → enrich from `experiment_log.txt` → `reresolve_cooldowns` → prints a full report. Rebuildable projection: `rm catalog.sqlite && python scripts/build_full_catalog.py` regenerates it identically (disk is truth).

## Operating rule — never `Read` a raw trace

Drive everything through the scripts above; **do NOT open a raw `DAQ_*.txt` with the `Read` tool.** Each trace is ~10 M points (~220 MB) — reading one floods context and tells you nothing the catalog doesn't already hold. The scripts read the bytes internally (via `AutoSQUID.read_daq_file`) and return only small summaries/figures. To inspect a trace, query `catalog.sqlite` or run `scripts/catplot.py`; to see raw values, plot `time_series`/`raw_overlay`. Reading the file directly is only ever justified to debug a parser bug, and then just the header (`Read` with a tiny `limit`), never the data block.

## Layout

- `catalog/` — the package. `squid.py` (the ONLY SQUID import: `import AutoSQUID as sq` + `_psd_welch`) · `schema.sql`/`db.py` (6 tables) · `pcs102_meta.py` (filename parser) · `calibration.py` (`resolve_cooldown` LOGIC only — no data) · `seed.py` (`seed_lookups` ensures the instrument; `register_cooldown` writes a cooldown row) · `crawl.py` (`crawl`, `reresolve_cooldowns`) · `explog.py` (log enrichment) · `analyzers.py`/`registry.py` · `dispatch.py` · `lineage.py` · `playbook.py`.
- `scripts/catplot.py` — generic plot/dispatch CLI (use this for every figure). `scripts/build_full_catalog.py` — build/refresh. `scripts/coollog.py` — per-cooldown logbook CLI. `demo_queries.py` — prompt→SQL cookbook. `make_*_pdf.py` — deliverable PDFs. `roots.py` — `DEFAULT_ROOTS = [SQUID/data]`.
- `cooldowns/<label>.md` — **human-readable lab logbooks** (one per cooldown): `## Essentials` + the `## Setup` block (restore values, Array/SQUID V-Phi, calibration factor) + a `## Notes` log of `- [phase] message` lines. Source of truth; `catalog/cooldown_log.py` indexes them onto `cooldown.setup_notes` + the `cooldown_note` table. `cooldowns/_calibration.md` is an **auto-generated** human-readable f₀/V + S-bias table (from the `cooldown` table, regenerated each build; `_`-prefixed files are skipped by the logbook loader).
- `tests/` (pytest, synthetic PCS102 fixtures via AutoSQUID writers) · **`figures/<YYYY-MM-DD>_<HHMMSS>_<desc>/`** (dispatch writes all figures here) · `catalog.sqlite` (the catalog).

Analyzers registered: per-trace `psd`, `time_series`; group `psd_overlay` (many traces → one figure). (`volt_temp_overlay` was removed — it required `TEMP_*.csv` the lab data rarely has.)

## Non-obvious things (read before changing anything)

- **Calibration resolves by the PCS102 header `DATE` → cooldown date-range, NOT folder/filename.** One real folder mixes two cooldowns (only the date separates them). Per-cooldown f₀/V lives in the **`cooldown` table in `catalog.sqlite`** (registered via `coollog add-cooldown`) — NO calibration data in any Python file. Registered: `YbZn2GaO5_Dec2025` 0.837, `Sapphire_Dec2025` 0.834, `Sapphire_May2026` 0.762 (this one spans May–June 2026 — one continuous cooldown). Because the calibration is operational data in the (git-ignored, rebuildable) catalog, `rm catalog.sqlite` clears it — re-register the cooldowns with the CLI; the disk-derived rows rebuild from a crawl. Git never touches `catalog.sqlite`.
- **Adding/extending a cooldown = a metadata op, no 21 GB re-read.** Run `python scripts/coollog.py add-cooldown <label> --sample … --start … --end … --f0 … [--s-bias …]` — it UPSERTs the `cooldown` row and runs `reresolve_cooldowns` to back-fill already-crawled rows now in range. The crawl is **incremental** (skips files unchanged by size/mtime), so re-crawling alone will NOT recalibrate already-logged rows — `reresolve_cooldowns` does, from each row's stored `acquired_date`.
- **Data outside every registered window is LOGGED but flagged `cooldown_resolved=0` (NULL calibration) — never guessed.** That's correct; register the cooldown to resolve it.
- **Per-cooldown setup + lab notes are MANUAL data** (not derivable from a crawl), so they live in `cooldowns/<exact-label>.md` (human-edited, survives rebuild). `load_logbooks` indexes them and **cross-checks the logbook's stated calibration factor against `cooldown.f0_per_volt`**, warning on mismatch. Add one by creating `cooldowns/<cooldown-label>.md`; append notes with `scripts/coollog.py note`.
- **Path-keyed, not filename-keyed.** The same filename appears in multiple folders with *different* content; rows key on the absolute `path` and `content_hash` proves uniqueness. Never join on filename alone.
- **Integrity gate = AutoSQUID `is_surge_spec` at ingest** → `integrity_pass` + `integrity_reason`. Dispatch only analyzes `integrity_pass=1`. (Validated: the gate agrees 100% with the acquisition's own `_JUMP`/`_SURGE`/`_BADBASE` filename/log labels.)
- **Jump/surge traces are PARTIALLY usable.** `usable_s` = the good pre-jump duration (full for clean; the prefix located from the gate's `at chunk N/nc`, else the log's `jump_time_s`; NULL for stuck/dead). `catplot … --include-partial` adds these to a group overlay, truncated to `usable_s` and labelled `(pre-jump Xs)`; their prefixes overlay consistently with the clean traces. Stuck/frozen traces have `usable_s` NULL and stay excluded.
- **A figure only has catalog metadata if produced THROUGH the dispatcher** (`run_analysis`/`run_group_analysis` write `derived_product` + `product_input` atomically). A hand-made figure, or one from a `:memory:` run, is an orphan on disk. Always dispatch into the on-disk `catalog.sqlite`, not `:memory:`.
- **Lab-data tolerance:** missing `experiment_log.txt` → enrich is a no-op; missing `TEMP_*.csv` → `temp_sidecar_path` NULL; bare `DAQ_<int>_<temp>_<npts>_<run>.txt` and AutoSQUID-native `DAQ_<DateTok>_..._<idx>[_OUTCOME].txt` both parse. None of these are load-bearing.

## Conventions

- **Figures go in `figures/`** — every dispatched figure lands under `figures/<stamp>_<kind>/` (via `scripts/catplot.py`). Not `results/`.
- **Every markdown doc leads with a short `## Essentials` section** (the key facts at a glance, a few bullets), then `---`, then the complete description. Applies to cooldown logbooks, event summaries, and reports — short part first for fast human reading, full detail below.
- **Save a dated markdown summary on events** — new data incoming, a new/extended cooldown, a finding — as `output/<YYYY-MM-DD>_<slug>_summary.md`, in the Essentials-first structure above. **Weekly recaps go in `weekly_summary/`.** (`output/` holds all generated narrative; config and logbooks stay at root / `cooldowns/`.)
- **Plotting scripts must be generic** — drive `scripts/catplot.py` with flags; never write a new per-case `add_<temp>_overlay.py`. (Standing user preference.)
- Import **nothing** from `SQUID/denoising/**` (working/derived data, not raw). The only raw root is `SQUID/data`.
- `playbook.py` / `analysis_playbook.md` exist (policy-as-data design) but are **not yet wired into dispatch** — params are passed explicitly to `run_analysis`.
