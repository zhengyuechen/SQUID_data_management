# Partial (Jump) Traces Made Usable + Calibration in Markdown

## Essentials
- **Jump/surge traces are now recoverable.** Each trace carries `usable_s` = its good pre-jump duration; `catplot … --include-partial` overlays jump traces truncated to that prefix. **12** of the failed traces gained a usable prefix (the rest are genuinely frozen).
- **Verified:** on real June 100 µs @ 2 K data, the recovered pre-jump prefixes overlay onto the same PSD as the clean traces — the failed traces really are usable.
- **Calibration is now in a human-readable markdown:** `cooldowns/_calibration.md` (Φ₀/V + S-bias per cooldown), auto-generated from `calibration.py` every build.
- 54 tests pass.

---

## Jump traces → usable prefix
A new `usable_s` column = the good (pre-jump) duration per trace:
- **clean** → full duration;
- **baseline jump / surge** → the prefix, located from the gate's reason `… at chunk N/nc` (preferred) or the experiment_log's `jump_time_s` (fallback);
- **stuck / dead / already-surged** → NULL (no single jump point → not recovered).

`run_group_analysis(..., include_partial=True)` (CLI `catplot … --include-partial`) selects clean traces **plus** any with a `usable_s`, and `psd_overlay` truncates each to its prefix, labelling it `(pre-jump Xs)`.

Catalog state: **177 clean + 12 partial-usable + 36 unusable** (= 225). The 36 unusable are stuck/frozen (the FLL latched — no clean prefix; e.g. most 500 µs surges, abort-saved at 100 %).

Proof figure: `figures/2026-06-06_001300_jun-100us-2K-recovered_psd-overlay/psd_overlay.png` — 2 clean + 3 recovered (pre-jump 564 / 193 / 314 s) all collapse onto one spectrum above ~2 Hz.

## Calibration in human-readable markdown
`cooldowns/_calibration.md` is generated from `COOLDOWN_SEED` (the build-time source) and lists, per cooldown, sample · dates · Φ₀/V · S-bias. `calibration.py` stays the source; the markdown is the always-in-sync human view (full V-Phi setup remains in each `cooldowns/<label>.md`).

| Cooldown | Φ₀/V | S-bias (mA) |
|---|---|---|
| YbZn2GaO5_Dec2025 | 0.837 | 0.0747 |
| Sapphire_Dec2025 | 0.834 | 0.0752 |
| Sapphire_May2026 | 0.762 | 0.0654 |

## Conventions applied
- Figures now write to **`figures/`**.
- Markdown docs (this one, the logbooks) lead with a short **`## Essentials`** then `---` then full detail.
