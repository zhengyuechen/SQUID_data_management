"""Cooldown resolution LOGIC only. The cooldown/calibration DATA lives in the catalog's
`cooldown` table (catalog.sqlite), written via `seed.register_cooldown` / the `coollog
add-cooldown` CLI — nothing is hardcoded in this module. A trace is assigned to a cooldown
by matching its PCS102 header acquisition DATE against each cooldown's date range, which is
robust to folder layout (the real all-interval set mixes the YbZn sample and Sapphire
background cooldowns in one tree)."""


def _iso(mdy):
    "PCS102 header DATE 'MM-DD-YYYY' -> 'YYYY-MM-DD' (lexically comparable to the ISO ranges)."
    m, d, y = mdy.split("-")
    return f"{y}-{m}-{d}"


def resolve_cooldown(header_date, cooldowns):
    """(label, factor) for a PCS102 header DATE ('MM-DD-YYYY'); (None, None) if the date
    falls in no cooldown window. `cooldowns`: an iterable of dicts/rows with start_date,
    end_date (ISO), label, f0_per_volt — e.g. rows from the catalog's `cooldown` table."""
    try:
        d = _iso(header_date)
    except (ValueError, AttributeError, TypeError):
        return None, None
    for c in cooldowns:
        if c["start_date"] <= d <= c["end_date"]:
            return c["label"], c["f0_per_volt"]
    return None, None
