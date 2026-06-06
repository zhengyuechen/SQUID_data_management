from catalog.calibration import resolve_cooldown

# A small explicit registry-shaped list — resolve_cooldown is pure logic over rows like these.
COOLDOWNS = [
    {"label": "YbZn2GaO5_Dec2025", "start_date": "2025-12-22", "end_date": "2026-01-04", "f0_per_volt": 0.837},
    {"label": "Sapphire_Dec2025",  "start_date": "2025-12-08", "end_date": "2025-12-14", "f0_per_volt": 0.834},
    {"label": "Sapphire_May2026",  "start_date": "2026-05-18", "end_date": "2026-06-30", "f0_per_volt": 0.762},
]

def test_resolves_by_acquisition_date():
    assert resolve_cooldown("12-23-2025", COOLDOWNS) == ("YbZn2GaO5_Dec2025", 0.837)
    assert resolve_cooldown("01-04-2026", COOLDOWNS) == ("YbZn2GaO5_Dec2025", 0.837)
    assert resolve_cooldown("12-14-2025", COOLDOWNS) == ("Sapphire_Dec2025", 0.834)

def test_date_outside_all_windows_is_flagged():
    assert resolve_cooldown("08-15-2026", COOLDOWNS) == (None, None)   # after the extended May window
    assert resolve_cooldown(None, COOLDOWNS) == (None, None)
