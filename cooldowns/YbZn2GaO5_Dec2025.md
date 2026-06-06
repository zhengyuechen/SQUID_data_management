# Cooldown logbook — YbZn2GaO5_Dec2025

## Essentials
- **Sample:** YbZn2GaO5 (QSL candidate)   ·   **Dates:** 2025-12-22 → 2026-01-04 (runs extended to ~01-07)
- **Calibration factor: 0.837 f₀/V**   ·   **Flux jump: 1.195 V**
- **SQUID:** S-bias 0.0752 mA → drifted to **0.0747 mA** for the runs   ·   A-flux 5.861 µA
- **Array:** S-bias 0.3 mA · A-bias 20.879 µA · offset 0.5697 mV
- Source: `SQ180 w YbZn2GaO5 - Measurements Dec2025.pptx` (setup slides 6 & 102)

---

## Setup
Restore values from the prior background measurement, then tune & lock.

**Array V-Phi** (locked array):
- Test signal: 200 Hz, 0.4 V, Array Flux
- S-bias = 0.3 mA · S-flux = 0 µA · A-flux = 0 µA
- A-bias = 20.879 µA
- Offset = 0.5697 mV
- Image: 1 V/div, 1 ms/div · Output ~ 4.5 Vpp (4.921 Vpp at the 12/26 re-tune)

**SQUID V-Phi** (locked squid):
- Test signal: 200 Hz, 1 V, SQUID Flux
- S-bias = 0.0752 mA
- A-flux = 5.861 µA (6.398 µA at the 12/26 re-tune for 11 mK)
- Image: 0.2 V/div, 1 ms/div · Output ~ 0.7 V

Calibration factor: 0.837 f₀/V (flux jump 1.195 V)

## Notes
- [setup] (12/22/2025, 14 mK) Restored bias/flux from the prior background measurement before tuning.
- [calibration] Locked array (S-bias 0.3 mA, A-bias 20.879 µA, offset 0.5697 mV); locked SQUID (S-bias 0.0752 mA, A-flux 5.861 µA). Factor 0.837 f₀/V.
- [run] After the calibration sequence the S-bias drifted 0.0752 → 0.0747 mA (very small); continued all measurements at 0.0747 mA.
- [calibration] (12/26/2025, 11 mK) Re-tuned: A-flux 6.398 µA, output ~0.8 V; auto-calibration factor 0.837 f₀/V, flux jump 1.195 V. Restored these values for the later temperatures.
- [run] Temperature control via probe PID + MXC heater; the 11 mK (12/26) tuning was restored for all subsequent setpoints (10 mK → 5.5 K).
