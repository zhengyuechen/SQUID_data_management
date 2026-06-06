# Cooldown logbook — Sapphire_Dec2025

## Essentials
- **Sample:** Sapphire (non-magnetic background)   ·   **Dates:** 2025-12-08 → 2025-12-14
- **Calibration factor: 0.834 f₀/V**   ·   **Flux jump: 1.199 V**
- **SQUID:** S-bias 0.0752 mA · A-flux 5.861 µA
- **Array:** S-bias 0.3 mA · A-bias 20.879 µA · offset 0.5697 mV
- Source: `SQ180 w Sapphire - Measurements Dec2025.pptx` (setup slide 9, tuned 12/8/2025)

---

## Setup

**Array V-Phi** (auto-tuning, locked array):
- Test signal: 200 Hz, 0.4 V, Array Flux
- S-bias = 0.3 mA
- A-bias = 20.879 µA
- Offset = 0.5697 mV
- Output = 4.961 Vpp

**SQUID V-Phi** (manual tuning with DAQ, locked squid):
- Test signal: 200 Hz, 1 V, SQUID Flux
- S-bias = 0.0752 mA
- A-flux = 5.861 µA
- Image: 0.2 V/div, 1 ms/div

SQUID auto-calibration: data points = 1000, flux step = 256, threshold = 0.5 V.
Calibration factor: 0.834 f₀/V (flux jump 1.199 V)

## Notes
- [setup] (12/8/2025, 10.3 mK) Array auto-tuned; SQUID manually tuned with the DAQ.
- [calibration] Auto-calibration factor 0.834 f₀/V, flux jump 1.199 V.
- [run] Restored bias/offset/flux from the 10 mK tuning for higher temperatures (e.g. 200 mK: probe heater 1.25 mW, probe 435 mK, MXC 200 mK). Background temperature-dependence series at 10 / 300 / 490 mK.
