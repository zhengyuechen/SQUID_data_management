from catalog.calibration import resolve_cooldown, COOLDOWN_SEED, CALIBRATION_FO_PER_V

def test_resolves_by_acquisition_date():
    assert resolve_cooldown("12-23-2025") == ("YbZn2GaO5_Dec2025", 0.837)
    assert resolve_cooldown("01-04-2026") == ("YbZn2GaO5_Dec2025", 0.837)
    assert resolve_cooldown("12-14-2025") == ("Sapphire_Dec2025", 0.834)

def test_date_outside_all_windows_is_flagged():
    assert resolve_cooldown("08-15-2026") == (None, None)   # after the extended May window
    assert resolve_cooldown(None) == (None, None)

def test_seed_factor_matches_map():
    for row in COOLDOWN_SEED:
        assert row["f0_per_volt"] == CALIBRATION_FO_PER_V[row["label"]]
