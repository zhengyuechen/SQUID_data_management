# Real-Data Smoke Test — Catalog Approach Validated

**Date:** 2026-06-05
**Question:** Before building the catalog, do the risky pieces (AutoSQUID read + integrity gate + filename parser + date-based calibration) actually work on the real raw traces?
**Data:** `SQUID/data/DAQ-all-interval-for-denoising/DAQ-all-interval-for-denoising/` — 31 of the 94 traces tested (all 19 `4us/` + all 12 `bkg/`), each **10 Mpts (~220 MB)**, December 2025.
**Script:** `data_management_plan/smoke_real_data.py` (standalone; mirrors the plan's parser + date-resolver inline, uses `import AutoSQUID as sq` for read + gate).
**Plan:** [`2026-06-05_catalog-prototype-implementation_plan.md`](./2026-06-05_catalog-prototype-implementation_plan.md).
**Verdict:** **PASS — the approach is validated end-to-end on real data.** One real finding (3 bad 500 µs background traces) corroborates the design.

---

## What was confirmed

| Risk | Result |
|---|---|
| `import AutoSQUID as sq` works in the analysis env | ✅ after `pip install -e SQUID/automation/AutoSQUID` (pulls pyserial + nidaqmx; both import without hardware). Anaconda base, Python 3.10. |
| AutoSQUID reads real 10 Mpts PCS102 traces | ✅ `sq.read_daq_file` → `~1.8 s/file`. Full 94-file crawl ≈ **3 min** — feasible. |
| Integrity gate runs on 10 M points | ✅ `sq.is_surge_spec` → (bad, reason) per trace. |
| Filename grammar parses real names | ✅ every temp: `1p35K`→1350, `4p75K`→4750, `5p5K`→5500, `1K/2K/3K`, `100…490mK`. Zero parse failures. |
| **Date-based calibration splits the two cooldowns** | ✅ all 19 `4us/` (dated 12-22-2025 → 01-04-2026) → **YbZn2GaO5_Dec2025, 0.837**; all 12 `bkg/` (all 12-14-2025) → **Sapphire_Dec2025, 0.834**. No misassignments across every date and temperature. |

## The real finding (integrity gate caught genuine bad traces)

3 of 31 traces **failed** the gate — all three **500 µs background** traces:

```
DAQ_500us_10mK_10Mpts_1.txt   (bkg, 12-14)  FAIL: stuck/frozen: ~100% of chunks
DAQ_500us_300mK_10Mpts_1.txt  (bkg, 12-14)  FAIL: stuck/frozen: ~100% of chunks
DAQ_500us_490mK_10Mpts_1.txt  (bkg, 12-14)  FAIL: stuck/frozen: ~100% of chunks
```

**This reproduces the lab's own prior curation.** The earlier all-interval analysis kept **9** background traces (4 µs/20 µs/100 µs × {10, 300, 490 mK}) — **no 500 µs bkg**. The gate, run blind at ingest, drops exactly the three traces a human had already excluded. Strong evidence that the mandatory gate + "exclude-failed-at-ingest" design is correct and that crawling raw data without manual curation is safe.

**Open (low-priority) question for the user:** are the 500 µs background traces genuinely defective, or is `is_surge_spec` over-eager at the 2 kHz sample rate (its stuck heuristic flags when one high-variance chunk inflates the reference)? Either way the catalog records `integrity_pass=0` + the reason and excludes them from analysis; this only matters if you later want those traces back.

## Consequences folded into the plan

- Calibration is resolved by the **PCS102 header `DATE` → cooldown date-range** (folder names can't separate the two cooldowns living in this one tree). Validated above.
- `import AutoSQUID as sq` adopted as the convention across the plan's modules (`catalog/squid.py` exposes `sq` + `_psd_welch`).
- Install step pinned: `pip install -e SQUID/automation/AutoSQUID`.
- `SQUID/data/` is no longer empty — this folder is the live auto-digest target (recursive `rglob` reaches the interval + `bkg/` subfolders).

## Caveat

`numexpr` / `bottleneck` in the env were compiled against NumPy 1.x while the env has NumPy 2.2.6 → noisy import warnings; pandas falls back and works. Pre-existing, not introduced here, not blocking — but worth a `conda`/`pip` refresh of those two if the warnings bother you.
