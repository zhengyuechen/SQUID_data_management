"""Bootstrap the lookup tables once (instrument, samples, cooldowns-with-calibration).
Idempotent via INSERT OR IGNORE on the UNIQUE name/label columns."""
from catalog.calibration import COOLDOWN_SEED

def seed_lookups(conn):
    conn.execute("INSERT OR IGNORE INTO instrument(name, kind) VALUES (?,?)", ("PCS102-SQUID", "squid"))
    for row in COOLDOWN_SEED:
        conn.execute("INSERT OR IGNORE INTO sample(name, formula) VALUES (?,?)", (row["sample"], row["formula"]))
    for row in COOLDOWN_SEED:
        sid = conn.execute("SELECT id FROM sample WHERE name=?", (row["sample"],)).fetchone()["id"]
        # UPSERT so editing COOLDOWN_SEED (e.g. extending a date range) updates the row on re-seed.
        conn.execute("""INSERT INTO cooldown
                        (sample_id,label,fridge,start_date,end_date,f0_per_volt,s_bias_ma)
                        VALUES (?,?,?,?,?,?,?)
                        ON CONFLICT(label) DO UPDATE SET
                          sample_id=excluded.sample_id, fridge=excluded.fridge,
                          start_date=excluded.start_date, end_date=excluded.end_date,
                          f0_per_volt=excluded.f0_per_volt, s_bias_ma=excluded.s_bias_ma""",
                     (sid, row["label"], row["fridge"], row["start_date"],
                      row["end_date"], row["f0_per_volt"], row["s_bias_ma"]))
    conn.commit()
