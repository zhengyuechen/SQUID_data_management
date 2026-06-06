"""Per-cooldown Phi_0/V calibration, owned by the catalog as DATA (values from
CLAUDE.md). Cooldown is resolved by the PCS102 header acquisition DATE against
each cooldown's date range — robust to folder layout (the real all-interval set
mixes the YbZn sample and Sapphire background cooldowns in one tree)."""

CALIBRATION_FO_PER_V = {
    "YbZn2GaO5_Dec2025": 0.837,
    "Sapphire_Dec2025":  0.834,
    "Sapphire_May2026":  0.762,
}

# Cooldown lookup-table seed; date ranges (ISO) + S-bias documented in CLAUDE.md / the lab PPTs.
COOLDOWN_SEED = [
    {"label": "YbZn2GaO5_Dec2025", "sample": "YbZn2GaO5",           "formula": "YbZn2GaO5",
     "fridge": "dilution", "start_date": "2025-12-22", "end_date": "2026-01-04",
     "f0_per_volt": CALIBRATION_FO_PER_V["YbZn2GaO5_Dec2025"], "s_bias_ma": 0.0747},
    {"label": "Sapphire_Dec2025",  "sample": "Sapphire-background", "formula": "Al2O3",
     "fridge": "dilution", "start_date": "2025-12-08", "end_date": "2025-12-14",
     "f0_per_volt": CALIBRATION_FO_PER_V["Sapphire_Dec2025"], "s_bias_ma": 0.0752},
    {"label": "Sapphire_May2026",  "sample": "Sapphire-background", "formula": "Al2O3",
     "fridge": "dilution", "start_date": "2026-05-18", "end_date": "2026-06-30",  # same cooldown ran May into June
     "f0_per_volt": CALIBRATION_FO_PER_V["Sapphire_May2026"], "s_bias_ma": 0.0654},
]

def _iso(mdy):
    "PCS102 header DATE 'MM-DD-YYYY' -> 'YYYY-MM-DD' (lexically comparable to the ISO ranges)."
    m, d, y = mdy.split("-")
    return f"{y}-{m}-{d}"

def resolve_cooldown(header_date, cooldowns=COOLDOWN_SEED):
    """(label, factor) for a PCS102 header DATE ('MM-DD-YYYY'); (None, None) if the date
    falls in no cooldown window. `cooldowns`: dicts/rows with start_date, end_date (ISO),
    label, f0_per_volt."""
    try:
        d = _iso(header_date)
    except (ValueError, AttributeError, TypeError):
        return None, None
    for c in cooldowns:
        if c["start_date"] <= d <= c["end_date"]:
            return c["label"], c["f0_per_volt"]
    return None, None
