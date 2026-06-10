# Figure Style Guide

How every figure in this project gets made and what it must look like. Written for both humans and LLM sessions: **read this before writing any plotting code.**

## Essentials

- **Figures are made ONLY through the dispatcher** (`scripts/catplot.py` → `dispatch.run_analysis`/`run_group_analysis`). Never a per-case plotting script, never a hand-made figure — those are lineage orphans.
- **Style comes from `catalog/style.py`**, applied automatically by dispatch before every analyzer runs. A new analyzer imports `style` and uses its constants; it never calls `rcParams`, never hardcodes dpi/figsize/labels.
- **Selection is never baked into an analyzer.** What to plot comes from the catalog query (`--temp`, `--cooldown`, `--outcome`, `--where`); the analyzer only knows *how* to draw. (Standing rule: plotting scripts must be generic.)
- **PSD figures:** log-log, x = `Frequency (Hz)`, y = `PSD ($f_0^2$/Hz)` — calibrated via the trace's own cooldown `f0_per_volt`. An uncalibrated PSD must be labelled `(V$^2$/Hz)`, never silently mislabelled.
- **Time-series figures:** x = `Time (s)`, y = `Voltage (V)` (raw, uncalibrated).
- **Save at `style.DPI` (130), default figsize `style.FIGSIZE` (8×6)**, into the dispatch-created `figures/<stamp>_<kind>/` folder — never loose files.
- **Legend entries for traces:** `<interval>us <temp>mK`, with ` (pre-jump Xs)` appended for partial jump/surge traces. **Titles:** what the figure is + `(n=…, key params)`.

---

## How a figure gets made (the only path)

```
catplot.py <kind> --flags  →  dispatch resolves the WHERE against catalog.sqlite
                           →  style.apply()                (house rcParams)
                           →  analyzer(kind) draws + saves  (figures/<stamp>_<kind>/, underscores in kind become dashes: psd_overlay → psd-overlay)
                           →  derived_product + product_input rows written atomically
```

A figure produced any other way has no catalog metadata and no lineage back to its raw traces. If you find yourself writing `plt.savefig` outside an analyzer, stop and write an analyzer instead (one function + one registry line — see `catalog/registry.py`).

## House style (`catalog/style.py`)

| Setting | Value | Note |
|---|---|---|
| `DPI` | 130 | all saved figures |
| `FIGSIZE` | (8, 6) | single-panel default; multi-panel stacks size per-row |
| font / title / label size | 11 | via rcParams |
| tick label size | 9 | |
| legend size | 8 | overlays use `ncol=2` when entries are many |
| grid | on, alpha 0.3 | |
| default linewidth | 0.8 | overlays may go thinner (0.4–0.7) for dense stacks |

These are the **taste knobs** — edit them in `catalog/style.py` only (one place, every figure follows). Do not override them inside an analyzer.

## Axes, units, calibration

- **PSD:** always `plt.loglog`. y is calibrated flux PSD: multiply volts by the trace's cooldown `f0_per_volt` **before** Welch (the dispatcher hands each analyzer the right per-trace factor — never a global one, never hardcoded). Label `style.PSD_YLABEL` = `PSD ($f_0^2$/Hz)`. `f0` is the flux quantum, per this repo's f₀/V notation.
- **Raw time series:** uncalibrated volts, labels `style.TS_XLABEL`/`style.TS_YLABEL`. Decimate for display (`raw_overlay` uses ~20k points/panel); never plot 10M points raw.
- **Partial traces** (jump/surge with a usable prefix): plot only the prefix (truncate to `usable_s`) and say so in the legend — ` (pre-jump Xs)`. Stuck/frozen traces are excluded from analysis figures (diagnostic `raw_overlay --include-all` is the exception).

## Color

- **Comparing intervals/runs at one temperature** (the common `psd_overlay --temp 50` case): use the default matplotlib color cycle — every curve must be distinguishable.
- **When temperature IS the comparison axis** (overlay across temperatures, T-dependence figures — the physics fingerprint for the QSL search): use `style.temp_color(temp_mK)` so the same temperature is the same color in **every** figure. It log-maps 10 mK–10 K onto viridis; out-of-range clamps, unknown → gray. Add a sorted legend (coldest first).
- Never encode anything in red/green alone as the only distinction.

## Labels & titles

- Legend per trace: `f"{interval:.0f}us {temp:.0f}mK"` (+ pre-jump suffix). Keep it terse — provenance lives in the catalog, not the legend.
- Title: what + count + load-bearing params, e.g. `PSD overlay  (n=12, P=100)`. The dispatch folder name (`<stamp>_<kind>`) and the `derived_product.params` JSON carry the rest.
- No timestamps, file paths, or absolute disk locations rendered inside figures — the catalog's lineage answers "which files made this".

## Writing a new analyzer (checklist)

1. One function in `catalog/analyzers.py`: per-trace `(row, factor, params, outdir)` or group `(inputs, params, outdir)` → `(artifact_path, scalars_dict)`.
2. `from catalog import style` — use `style.DPI`, `style.FIGSIZE`, the label constants, `style.temp_color` where temperature is the axis. No `rcParams` edits, no new dpi numbers.
3. Honor `usable_s` for partial traces; skip or annotate, never silently plot a post-jump tail.
4. Register it: one line in `catalog/registry.py`. Dispatch handles selection, calibration factors, output folder, lineage, caching.
5. Scalars returned must be spreadsheet-cell values (numbers/short strings) — curves and images stay on disk.
6. Run `python -m pytest tests/ -q` from the repo root.

## What NOT to do

- ❌ A new `add_<temp>_overlay.py`-style script (standing user rule: drive `catplot.py` with flags).
- ❌ `plt.show()` — analyzers run headless (Agg); save and close.
- ❌ Dispatch into a `:memory:` DB for a figure you keep — it becomes an orphan.
- ❌ Restyle inline (`fontsize=`, `dpi=` literals) — change `catalog/style.py` if the house style is wrong.
- ❌ Mislabel calibration: a PSD in V²/Hz labelled `$f_0^2$/Hz` (or vice versa) is a physics error, not a style error.
