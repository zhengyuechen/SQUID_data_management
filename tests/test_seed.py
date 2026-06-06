from catalog.db import connect, init_db
from catalog.seed import seed_lookups, register_cooldown
from tests._fixtures import seed_test_cooldowns

EXPECTED = {"sample", "instrument", "cooldown", "raw_measurement", "derived_product", "product_input"}

def test_init_db_creates_all_tables(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn)
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED <= names

def test_init_db_is_idempotent(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn); init_db(conn)
    assert conn.execute("SELECT count(*) FROM sample").fetchone()[0] == 0

def test_seed_lookups_creates_instrument_only(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn); seed_lookups(conn)
    assert conn.execute("SELECT count(*) FROM instrument WHERE name='PCS102-SQUID'").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM cooldown").fetchone()[0] == 0   # cooldowns are NOT baked in

def test_register_cooldown_writes_calibration(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn); seed_test_cooldowns(conn)
    rows = {r["label"]: r["f0_per_volt"] for r in conn.execute("SELECT label, f0_per_volt FROM cooldown")}
    assert rows == {"YbZn2GaO5_Dec2025": 0.837, "Sapphire_Dec2025": 0.834, "Sapphire_May2026": 0.762}
    r = conn.execute("""SELECT s.name FROM cooldown c JOIN sample s ON s.id=c.sample_id
                        WHERE c.label='YbZn2GaO5_Dec2025'""").fetchone()
    assert r["name"] == "YbZn2GaO5"

def test_register_cooldown_upserts_on_label(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn)
    register_cooldown(conn, "C", "S", "2026-01-01", "2026-01-10", 0.80)
    register_cooldown(conn, "C", "S", "2026-01-01", "2026-01-20", 0.81)   # extend + recalibrate, same label
    rows = conn.execute("SELECT end_date, f0_per_volt FROM cooldown WHERE label='C'").fetchall()
    assert len(rows) == 1 and rows[0]["end_date"] == "2026-01-20" and rows[0]["f0_per_volt"] == 0.81
