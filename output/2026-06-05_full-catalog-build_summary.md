# Full Catalog Build over SQUID/data

**Date:** 2026-06-05
**What:** Built the persistent `data_management_plan/catalog.sqlite` over **all of `SQUID/data`** (`build_full_catalog.py`).
**Result:** 94/94 traces indexed in 169 s; 0 unparseable, 0 unresolved. The catalog is a rebuildable projection — `rm catalog.sqlite && python build_full_catalog.py` regenerates it identically.

## Contents

| Cooldown | Φ₀/V | clean | failed | total |
|---|---|---|---|---|
| `YbZn2GaO5_Dec2025` (sample) | 0.837 | 78 | 4 | 82 |
| `Sapphire_Dec2025` (background) | 0.834 | 9 | 3 | 12 |
| **all** | | **87** | **7** | **94** |

| Scan interval | n | clean | failed |
|---|---|---|---|
| 4 µs | 22 | 22 | 0 |
| 20 µs | 23 | 23 | 0 |
| 100 µs | 26 | 26 | 0 |
| 500 µs | 23 | 16 | **7** |

- **Temperature coverage:** 10–5500 mK across 22 distinct setpoints (the YbZn series spans base→5.5 K; the Sapphire background is at 10/300/490 mK).
- **Cooldown split is by header acquisition date** (the all-interval folder mixes both cooldowns in one tree): 82 sample traces dated 12-22→01-04 → 0.837; 12 background dated 12-14 → 0.834.
- **`experiment_log.txt` enrichment: 0 rows** — this dataset has no ledgers (older/denoising layout). Native acquisition folders with logs will enrich automatically.

## Finding: every integrity failure is a 500 µs trace

All **7** gate failures are at the **500 µs** scan interval (2 kHz sample rate); the 4/20/100 µs intervals are **100 % clean**. Within 500 µs, 7 of 23 fail (not all), so the detector is selective — these look like genuinely frozen/stuck traces, not a blanket threshold artifact. Failures span **both** cooldowns (3 background + 4 sample), and the background ones match the lab's prior exclusion (the earlier all-interval analysis kept no 500 µs bkg). **Implication:** the 500 µs series is partly compromised (~30 % stuck); the faster intervals are fully usable. Worth a look at whether the FLL/acquisition struggles on the long 500 µs runs (10 Mpts = ~83 min each), or whether `is_surge_spec` wants a tuned threshold at 2 kHz.

The 7 failed (gate-excluded, still recorded with the reason):
`DAQ_500us_{10mK[×2: sample+bkg], 11mK, 2K, 4p5K}` (YbZn) and `DAQ_500us_{300mK, 490mK}` (bkg).

## Path-keyed, not filename-keyed (verified)

`DAQ_500us_10mK_10Mpts_1.txt` exists in **two** folders — `500us/` (YbZn, 0.837) and `bkg/` (Sapphire, 0.834). The catalog stored **two distinct rows** with the correct per-cooldown calibration each, because rows are keyed on the full path. A filename-only index would have collided them and mis-calibrated one.

## Querying it

```bash
sqlite3 catalog.sqlite \
  "SELECT filename, temp_mK, phi0_per_volt FROM raw_measurement r
   JOIN cooldown c ON c.id=r.cooldown_id
   WHERE c.label='YbZn2GaO5_Dec2025' AND scan_interval_us=4 AND integrity_pass=1
   ORDER BY temp_mK;"   # -> the 19-point clean YbZn 4 µs temperature series
```
