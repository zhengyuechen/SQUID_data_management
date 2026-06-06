# Cooldown logbook — Sapphire_May2026

## Essentials
- **Sample:** Sapphire (non-magnetic background)   ·   **Dates:** 2026-05-18 → 2026-06-30 (one cooldown, ran May into June)
- **Calibration factor: 0.762 f₀/V**   ·   **Flux jump: 1.312 V**
- **SQUID:** S-bias 0.0654 mA · A-flux 5.861 µA
- **Array:** S-bias 0.3 mA · A-bias 21.123 µA · offset 0.6607 mV
- Source: `SQ180 w Sapphire - Measurements May2026.pptx` (setup slide 9, tuned 5/16/2026)

---

## Setup

**Array V-Phi** (auto-tuning, locked array):
- Test signal: 200 Hz, 0.4 V, Array Flux
- S-bias = 0.3 mA
- A-bias = 21.123 µA
- Offset = 0.6607 mV
- Output = 5.517 Vpp

**SQUID V-Phi** (manual tuning with DAQ, locked squid):
- Test signal: 200 Hz, 1 V, SQUID Flux
- S-bias = 0.0654 mA
- A-flux = 5.861 µA
- Image: 0.2 V/div, 1 ms/div

SQUID auto-calibration: data points = 1000, flux step = 256, threshold = 0.5 V.
Calibration factor: 0.762 f₀/V (flux jump 1.312 V)

## Notes
- [setup] (5/16/2026, 11 mK) Array auto-tuned (output 5.517 Vpp); SQUID manually tuned with the DAQ.
- [calibration] Auto-calibration factor 0.762 f₀/V, flux jump 1.312 V.
- [run] The same cooldown continued into June 2026 — the `Jun-01` … `Jun-05-2026` acquisition folders (400 mK – 5.5 K) belong to this cooldown. Many high-T / 500 µs runs surged (see catalog integrity flags).
