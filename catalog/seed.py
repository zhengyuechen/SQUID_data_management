"""Lookup-table writes for the catalog. The cooldown/calibration DATA is NOT hardcoded
here (or anywhere in Python) — it lives in `catalog.sqlite`'s `cooldown` table, written
by `register_cooldown` (via the `coollog add-cooldown` CLI) and persisting across builds
(init_db is CREATE-IF-NOT-EXISTS, so a re-build keeps existing cooldowns). `seed_lookups`
only ensures the instrument row exists."""

def seed_lookups(conn):
    conn.execute("INSERT OR IGNORE INTO instrument(name, kind) VALUES (?,?)", ("PCS102-SQUID", "squid"))
    conn.commit()

def register_cooldown(conn, label, sample, start_date, end_date, f0_per_volt,
                      formula=None, fridge="dilution", s_bias_ma=None):
    """Insert or update one cooldown (and its sample) in the catalog. UPSERT on label so
    editing a date range / factor re-registers in place. Commits. Returns the label.
    This is the ONLY way calibration enters the system — no Python-side seed list."""
    conn.execute("INSERT OR IGNORE INTO sample(name, formula) VALUES (?,?)", (sample, formula))
    sid = conn.execute("SELECT id FROM sample WHERE name=?", (sample,)).fetchone()["id"]
    conn.execute("""INSERT INTO cooldown
                    (sample_id,label,fridge,start_date,end_date,f0_per_volt,s_bias_ma)
                    VALUES (?,?,?,?,?,?,?)
                    ON CONFLICT(label) DO UPDATE SET
                      sample_id=excluded.sample_id, fridge=excluded.fridge,
                      start_date=excluded.start_date, end_date=excluded.end_date,
                      f0_per_volt=excluded.f0_per_volt, s_bias_ma=excluded.s_bias_ma""",
                 (sid, label, fridge, start_date, end_date, f0_per_volt, s_bias_ma))
    conn.commit()
    return label
