# Cooldown calibration reference

## Essentials
- Per-cooldown SQUID calibration **f₀/V** and **S-bias**, for quick human reference.
- Generated from `catalog.sqlite`'s `cooldown` table (the source of truth) — edit it with `python scripts/coollog.py add-cooldown ...`; this file is regenerated every build. Full V-Phi setup per cooldown: `cooldowns/<label>.md`.

---

| Cooldown | Sample | Dates | f₀/V | S-bias (mA) |
|---|---|---|---|---|
| Sapphire_Dec2025 | Sapphire-background | 2025-12-08 → 2025-12-14 | 0.834 | 0.0752 |
| YbZn2GaO5_Dec2025 | YbZn2GaO5 | 2025-12-22 → 2026-01-04 | 0.837 | 0.0747 |
| Sapphire_May2026 | Sapphire-background | 2026-05-18 → 2026-06-30 | 0.762 | 0.0654 |
