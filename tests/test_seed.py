from catalog.db import connect, init_db
from catalog.seed import seed_lookups

EXPECTED = {"sample", "instrument", "cooldown", "raw_measurement", "derived_product", "product_input"}

def test_init_db_creates_all_tables(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn)
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED <= names

def test_init_db_is_idempotent(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn); init_db(conn)
    assert conn.execute("SELECT count(*) FROM sample").fetchone()[0] == 0

def test_seed_populates_cooldowns(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn); seed_lookups(conn)
    rows = {r["label"]: r["f0_per_volt"] for r in conn.execute("SELECT label, f0_per_volt FROM cooldown")}
    assert rows == {"YbZn2GaO5_Dec2025": 0.837, "Sapphire_Dec2025": 0.834, "Sapphire_May2026": 0.762}
    r = conn.execute("""SELECT s.name FROM cooldown c JOIN sample s ON s.id=c.sample_id
                        WHERE c.label='YbZn2GaO5_Dec2025'""").fetchone()
    assert r["name"] == "YbZn2GaO5"

def test_seed_idempotent(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn); seed_lookups(conn); seed_lookups(conn)
    assert conn.execute("SELECT count(*) FROM cooldown").fetchone()[0] == 3
    assert conn.execute("SELECT count(*) FROM instrument WHERE name='PCS102-SQUID'").fetchone()[0] == 1
