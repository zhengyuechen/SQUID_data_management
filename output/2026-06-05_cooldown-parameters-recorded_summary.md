# Cooldown Parameters Recorded from the Measurement PPTs

## Essentials
- Read the 3 measurement decks in `SQUID/data-analysis/ppt/` and recorded every cooldown's **setup + calibration** into `cooldowns/<label>.md` logbooks (now indexed in the catalog).
- **YbZn2GaO5_Dec2025 → 0.837 Φ₀/V** (flux jump 1.195 V); **Sapphire_Dec2025 → 0.834** (1.199 V); **Sapphire_May2026 → 0.762** (1.312 V) — all match the seeded calibration (cross-check passed, no warnings).
- Figures now save to `figures/` (was `results/`); markdown docs now lead with this short Essentials section, then full detail.

---

## What was done
Extracted slide text (stdlib zip/XML) from the setup slides of each deck and recorded the parameters into the per-cooldown logbooks. Source decks (`SQUID/data-analysis/ppt/`):
`SQ180 w YbZn2GaO5 - Measurements Dec2025.pptx`, `SQ180 w Sapphire - Measurements Dec2025.pptx`, `SQ180 w Sapphire - Measurements May2026.pptx`.

## Cooldown parameters (as recorded)

| Cooldown | Factor (Φ₀/V) | Flux jump | SQUID S-bias | A-flux | Array A-bias | Array offset | Array output |
|---|---|---|---|---|---|---|---|
| YbZn2GaO5_Dec2025 | 0.837 | 1.195 V | 0.0752 → 0.0747 mA (runs) | 5.861 µA | 20.879 µA | 0.5697 mV | ~4.5 Vpp |
| Sapphire_Dec2025 | 0.834 | 1.199 V | 0.0752 mA | 5.861 µA | 20.879 µA | 0.5697 mV | 4.961 Vpp |
| Sapphire_May2026 | 0.762 | 1.312 V | 0.0654 mA | 5.861 µA | 21.123 µA | 0.6607 mV | 5.517 Vpp |

Common to all: Array V-Phi test signal 200 Hz / 0.4 V / Array Flux at S-bias 0.3 mA; SQUID V-Phi test signal 200 Hz / 1 V / SQUID Flux; SQUID auto-calibration data points = 1000, flux step = 256, threshold = 0.5 V. Each logbook also carries phased notes (`[setup]`/`[calibration]`/`[run]`), including the YbZn S-bias drift (0.0752 → 0.0747 mA) and that the May cooldown continued into June 2026.

## New conventions (this session)
- **Figures → `figures/`** (`catplot.py` writes `figures/<stamp>_<kind>/`).
- **Markdown leads with `## Essentials`** (short) then `---` then full description — for logbooks, event summaries, and reports.
- **Event summaries**: save `<YYYY-MM-DD>_<slug>_summary.md` at the project root on new data / new cooldown / findings.

## Read it
`python coollog.py show YbZn2GaO5_Dec2025` (or `Sapphire_Dec2025` / `Sapphire_May2026`) — prints the setup + notes. Sources of truth: `cooldowns/*.md`.
