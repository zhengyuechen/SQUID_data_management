# Data-Management Catalog

A rebuildable **SQLite catalog** over raw PCS102 SQUID magnetometer traces. The raw bytes stay on disk; the database holds the queryable **metadata, calibration, and lineage**. Built for a dilution-fridge quantum-spin-liquid noise-spectroscopy setup.

## Essentials

- **Crawl** raw `DAQ_*.txt` traces → one row per file (temperature, scan interval, integrity verdict, per-cooldown calibration, content hash, path).
- **Calibration** is resolved by the acquisition date in each file's header → the right cooldown's f₀/V factor, defined in human-editable markdown (`cooldowns/`), not in code.
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
```

`catplot.py` plots **any** selection via flags (`--temp`, `--interval`, `--cooldown`, `--where`, `--include-partial`, `--any`, `--limit`) — adding a new *kind* of plot is one analyzer; reusing a kind is just different flags.

## Layout

```
catalog/         the package: schema, crawl, calibration, analyzers, dispatch, lineage, cooldown logbooks
scripts/         run-from-root entry points: build_full_catalog.py, catplot.py, coollog.py
cooldowns/       per-cooldown markdown logbooks (calibration + V-Phi setup + notes) — the calibration SOURCE
tests/           pytest suite (no real data needed; fixtures use AutoSQUID's own writers)
output/          generated narrative: summaries, verdicts, reports, design/plan docs
figures/         dispatched figures (git-ignored — rebuildable)
roots.py         default data root;  conftest.py  pytest path shim
```

## How calibration works

Each cooldown is one `cooldowns/<label>.md` file: a small machine-readable header (label / sample / dates / `f0_per_volt` / `s_bias_ma`) plus the human V-Phi setup and a phased notes log. Because the same SQUID calibration on a given date is a physical fact, calibration is resolved by the trace's **header date → cooldown date-range**. Register or extend a cooldown by editing a markdown file and rebuilding — no Python.

## Conventions

- Figures → `figures/`; generated narrative markdown → `output/` (weekly recaps → `weekly_summary/`).
- Every markdown doc leads with a short `## Essentials` section, then the full detail.
- Plotting is always driven through `scripts/catplot.py` flags — no per-case plotting scripts.

## Status

The catalog is built and proven on real data (~225 traces across 3 cooldowns). Roadmap: a per-user bench-PC deployment (calibration registry + one CLI), then Postgres + a file-watcher, then an LLM query layer. See `output/` for the design and plans.
