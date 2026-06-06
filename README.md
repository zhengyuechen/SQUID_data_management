# Data-Management Catalog

A rebuildable **SQLite catalog** over raw PCS102 SQUID magnetometer traces. The raw bytes stay on disk; the database holds the queryable **metadata, calibration, and lineage**. Built for a dilution-fridge quantum-spin-liquid noise-spectroscopy setup.

## Essentials

- **Crawl** raw `DAQ_*.txt` traces → one row per file (temperature, scan interval, integrity verdict, per-cooldown calibration, content hash, path).
- **Calibration** is resolved by the acquisition date in each file's header → the right cooldown's f₀/V factor, stored in the catalog's `cooldown` table and edited via a CLI, never hardcoded in code.
- **Plot** any selection (`psd`, `time_series`, `psd_overlay`, `raw_overlay`) through one generic CLI; every figure is recorded with lineage back to the exact raw traces.
- **Integrity gate** (AutoSQUID `is_surge_spec`) runs at ingest; jump/surge traces keep a usable pre-jump prefix, frozen ones are flagged.

## Requirements

- Python 3.10+ with `numpy`, `pandas`, `matplotlib` (a standard scientific stack).
- The **AutoSQUID** package (PCS102 reader, integrity gate, plot functions):
  `pip install AutoSQUID` *(or, in the lab tree, `pip install -e ../SQUID/automation/AutoSQUID`)* — it pulls `nidaqmx` + `pyserial`, which import fine without hardware.

## Quick start

Run from the repo root:

```bash
python -m pytest tests/ -q                 # the test suite (synthetic PCS102 fixtures)
python scripts/build_full_catalog.py       # crawl the data root -> catalog.sqlite (idempotent, incremental)
python scripts/catplot.py psd_overlay --temp 50 --cooldown YbZn2GaO5_Dec2025   # a calibrated PSD overlay
python scripts/coollog.py show YbZn2GaO5_Dec2025                                # a cooldown's setup + notes
python scripts/coollog.py add-cooldown YbZn2GaO5_Dec2025 --sample YbZn2GaO5 \
       --start 2025-12-22 --end 2026-01-04 --f0 0.837 --s-bias 0.0747          # register/edit a cooldown's calibration
```

`catplot.py` plots **any** selection via flags (`--temp`, `--interval`, `--cooldown`, `--where`, `--include-partial`, `--any`, `--limit`) — adding a new *kind* of plot is one analyzer; reusing a kind is just different flags.

## Layout

```
catalog/         the package: schema, crawl, calibration, analyzers, dispatch, lineage, cooldown logbooks
scripts/         run-from-root entry points: build_full_catalog.py, catplot.py, coollog.py
cooldowns/       per-cooldown markdown logbooks (V-Phi setup + notes); restated factor is cross-checked against the DB
tests/           pytest suite (no real data needed; fixtures use AutoSQUID's own writers)
output/          generated narrative: summaries, verdicts, reports, design/plan docs
figures/         dispatched figures (git-ignored — rebuildable)
roots.py         default data root;  conftest.py  pytest path shim
```

## How calibration works

Calibration lives in the catalog's **`cooldown` table** (in `catalog.sqlite`) — one row per cooldown with its label, sample, date range, `f0_per_volt`, and `s_bias_ma`. Because the same SQUID calibration on a given date is a physical fact, a trace is matched to its cooldown by **header date → cooldown date-range**, and the factor comes from that row. There is no calibration data in any Python file.

Register or extend a cooldown with the CLI — it writes the row and back-fills any already-crawled traces that now fall in range (no file re-reads):

```bash
python scripts/coollog.py add-cooldown <label> --sample <name> --start YYYY-MM-DD --end YYYY-MM-DD --f0 <factor> [--s-bias <mA>]
python scripts/coollog.py registry        # list all registered cooldowns (dates, f₀/V, S-bias)
```

Each cooldown also has a human `cooldowns/<label>.md` logbook (V-Phi setup + a phased notes log); if it restates the factor, the build **cross-checks** it against the `cooldown` row and warns on any mismatch.

Note: `catalog.sqlite` holds this calibration *and* the disk-derived index, and it is git-ignored (rebuildable, never pushed). Deleting it therefore also clears the registered cooldowns — re-register them with the CLI above (the disk-derived rows rebuild themselves from a crawl).

## Conventions

- Figures → `figures/`; generated narrative markdown → `output/` (weekly recaps → `weekly_summary/`).
- Every markdown doc leads with a short `## Essentials` section, then the full detail.
- Plotting is always driven through `scripts/catplot.py` flags — no per-case plotting scripts.

## Status

The catalog is built and proven on real data (~225 traces across 3 cooldowns). Roadmap: a per-user bench-PC deployment (calibration registry + one CLI), then Postgres + a file-watcher, then an LLM query layer. See `output/` for the design and plans.
