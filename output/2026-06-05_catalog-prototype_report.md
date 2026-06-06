# Lab Data-Management Catalog — Prototype Built & Proven

**Date:** 2026-06-05
**Status:** **Implemented and passing** — 43/43 tests green; proven end-to-end on real 10 Mpts data.
**Plan:** [`2026-06-05_catalog-prototype-implementation_plan.md`](./2026-06-05_catalog-prototype-implementation_plan.md) · **Design:** [`2026-06-05_lab-data-management-catalog_plan.md`](./2026-06-05_lab-data-management-catalog_plan.md) · **Smoke:** [`2026-06-05_real-data-smoke_verdict.md`](./2026-06-05_real-data-smoke_verdict.md)

---

## What was built

A rebuildable SQLite **projection catalog** over the raw PCS102 SQUID traces. Disk owns the bytes; the DB owns queryable metadata + lineage. Package `catalog/` (14 modules, ~460 lines) + `tests/` (13 files, 43 tests).

| Module | Role |
|---|---|
| `squid.py` | single import point — `import AutoSQUID as sq` (published, editable-installed) + `_psd_welch` |
| `schema.sql` / `db.py` | 6-table schema (sample/instrument/cooldown/raw_measurement/derived_product/product_input) + connect/init |
| `pcs102_meta.py` | DAQ filename grammar (both simple **and** AutoSQUID-native: date token + `_OUTCOME` suffix) + temp→mK |
| `calibration.py` | per-cooldown Φ₀/V **as data**; cooldown resolved by header **DATE → date-range** |
| `seed.py` | bootstrap instrument/sample/cooldown lookups |
| `crawl.py` | read-only multi-root recursive ingest; integrity gate (`sq.is_surge_spec`) at ingest; idempotent on (size,mtime) |
| `explog.py` | **`experiment_log.txt` enrichment** — copies acquisition outcome / n_resets / T_start/T_end / jump_time onto rows |
| `analyzers.py` / `registry.py` | 3 analyzers wrapping `sq.plot_psd` / `sq.plot_run` / `sq.plot_overlay` (capture+save figures) |
| `dispatch.py` | query → run analyzer per clean trace → record `derived_product` + lineage; caches on (kind,raw,params) |
| `lineage.py` | bidirectional `raws_of_product` / `products_of_raw` |
| `playbook.py` + `analysis_playbook.md` | human-editable policy (fenced ```json core the dispatcher parses) |

## Two features added for AutoSQUID-native data (this session)

1. **Native filename grammar.** Real acquisition output is `DAQ_<DateTok>_<interval>_<temp>_<npts>_<idx>[_OUTCOME].txt` (e.g. `DAQ_Jun01_4us_4K_10Mpts_2.txt`, `DAQ_100us_15mK_1000000pts_1_JUMP.txt`). The parser now accepts the optional date token and `_OUTCOME` suffix and **captures the outcome**. (The simpler all-interval names still parse.)
2. **`experiment_log.txt` ingest.** The AutoSQUID ledger is joined on path to enrich each row with the acquisition's own **outcome** (CLEAN/JUMP/SURGE…), `n_resets`, `T_start_K`/`T_end_K`, `jump_time_s` — a *second, independent* integrity signal alongside `is_surge_spec`, queryable for disagreements (`WHERE outcome='CLEAN' AND integrity_pass=0`). `action_log.txt` is intentionally not ingested (actions, not measurements).

## Verification

- **Unit + integration:** `python -m pytest tests/ -q` → **43 passed in ~3.8 s**. Covers schema, parser (incl. native names), date-calibration, seeding, crawl (incl. native + idempotency + empty-root), log enrichment, the 3 analyzers, dispatch (per-trace + caching + failed-exclusion), lineage round-trip, playbook, and a full pipeline.
- **Real 10 Mpts data** (`real_e2e.py`, crawling the `bkg/` folder): 12 ingested, 0 unparseable, 0 unresolved; all resolved to `Sapphire_Dec2025` / **0.834** by the 12-14 header date; the gate excluded exactly the **3 × 500 µs** traces (stuck/frozen); a PSD dispatched via `sq.plot_psd` produced `results/2026-06-05_000000_real-e2e-bkg_psd/psd_DAQ_4us_10mK_10Mpts_1.png` with conversion 0.834 applied (white level 2.2e-11 Φ₀²/Hz) and intact figure→raw lineage.

## How to use it

```bash
pip install -e SQUID/automation/AutoSQUID      # once: AutoSQUID + pyserial + nidaqmx
cd data_management_plan && python -m pytest tests/ -q
```
```python
from catalog.db import connect, init_db; from catalog.seed import seed_lookups
from catalog.crawl import crawl; from catalog.explog import enrich_from_logs
from catalog.dispatch import run_analysis
from roots import DEFAULT_ROOTS                 # [<projects>/SQUID/data]
conn = connect("catalog.sqlite"); init_db(conn); seed_lookups(conn)
crawl(conn, DEFAULT_ROOTS)                      # auto-digests whatever is in SQUID/data
enrich_from_logs(conn, DEFAULT_ROOTS)           # pulls in experiment_log metadata if present
run_analysis(conn, "psd", "temp_mK BETWEEN 9 AND 15", {"P": [100, 1000]},
             results_root="results", stamp="2026-06-05_120000_psd-low-T")
```
Drop new acquisition folders (date-named, with logs + `DAQ_…`/`TEMP_…`) into `SQUID/data` and re-run `crawl` + `enrich_from_logs` — idempotent, incremental.

## Known / deferred

- 3 × 500 µs background traces fail `is_surge_spec` ("stuck/frozen") — matches the lab's prior exclusion; flagged for review only (could be a 2 kHz threshold artifact).
- ~~Many-raws→one-product overlay~~ **DONE** — `analyzers.psd_overlay` group analyzer + `dispatch.run_group_analysis` (one product, N `overlay_member` links, cached). Proven on the real `bkg/` set: 9 clean background PSDs overlaid across 4/20/100 µs (0.1 Hz–125 kHz) in `results/2026-06-05_000000_bkg_psd-overlay/psd_overlay.png`; 45/45 tests pass.
- Postgres / file-watcher daemon / LLM layer — Phase-1/2, out of scope.
- NumPy 1.x/2.x warnings from `numexpr`/`bottleneck` in the env are pre-existing and harmless.
