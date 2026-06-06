# June 2026 Data Indexed + Calibrated

**Date:** 2026-06-05
**What:** Indexed 5 newly-imported AutoSQUID folders (`Jun-01` … `Jun-05-2026`, 131 traces) into `catalog.sqlite` and registered their cooldown.

## Indexing
- 225 traces total now (94 prior + 131 June); 0 unparseable. **127 of 131 June traces enriched from `experiment_log.txt`** (June folders ship logs).
- The June filenames are AutoSQUID-native (`DAQ_Jun01_100us_2K_10Mpts_1.txt`, with `_JUMP`/`_SURGE`/`_BADBASE` outcome suffixes) — the extended parser handles them.

## Calibration: June = the May cooldown (user)
The May 2026 cooldown ran continuously into June, so `Sapphire_May2026` (Φ₀/V = **0.762**) was **extended** (`end_date` 2026-05-19 → 2026-06-30) and the 131 June rows re-resolved to it. This used a new capability — `reresolve_cooldowns()` — that re-resolves already-logged rows from their stored acquisition date **without re-reading** the 21 GB (registering/extending a cooldown is now a metadata-only operation; also wired into `build_full_catalog.py` and `seed_lookups` now UPSERTs cooldowns). Result: **0 unresolved rows.**
- *Caveat:* end_date set to 2026-06-30 to cover the current import — extend if the cooldown continued past June. Sample label inherited as `Sapphire-background` (same physical cooldown); correct factor regardless.

## Why 41 of the 131 June traces failed integrity
All 41 are genuine flux-lock events during acquisition, and **the gate agrees 100% with the acquisition's own labels**:

| acquisition outcome | gate pass | gate fail |
|---|---|---|
| CLEAN (89) | 89 | 0 |
| JUMP (30) | 0 | 30 |
| SURGE (7) | 0 | 7 |
| BAD_BASELINE (1) | 0 | 1 |
| (no log, 4) | 1 | 3 |

Failure reasons: **28 stuck/frozen** (FLL latched — mostly the slow 500 µs runs), **12 baseline jumps** (surge mid-run), **1 started already-surged**. The high-temperature June runs (2–5.5 K) plus the long 500 µs acquisitions were surge-prone; the acquisition flagged them in the filenames, and `is_surge_spec` independently confirms every one. Nothing is wrong with the catalog — it is correctly excluding the bad traces.

The 90 clean June traces (Sapphire_May2026, 0.762) are now ready to plot/analyze, e.g. `python catplot.py psd_overlay --temp 4000 --cooldown Sapphire_May2026 --name jun-4K`.
