from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl, reresolve_cooldowns
from catalog.explog import enrich_from_logs
from tests._fixtures import make_corpus, make_native_corpus, make_bare_corpus, seed_test_cooldowns

def _db(tmp_path):
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn); seed_test_cooldowns(conn); return conn

def test_ingests_all(tmp_path):
    root = tmp_path / "data"; make_corpus(root)
    conn = _db(tmp_path); s = crawl(conn, [root])
    assert s["ingested"] == 5
    assert conn.execute("SELECT count(*) FROM raw_measurement").fetchone()[0] == 5

def test_integrity_recorded(tmp_path):
    root = tmp_path / "data"; p = make_corpus(root)
    conn = _db(tmp_path); crawl(conn, [root])
    rail = conn.execute("SELECT integrity_pass, integrity_reason FROM raw_measurement WHERE filename=?",
                        (p["sample_33mK_railed"].name,)).fetchone()
    assert rail["integrity_pass"] == 0 and rail["integrity_reason"] != "ok"
    clean = conn.execute("SELECT integrity_pass FROM raw_measurement WHERE filename=?",
                         (p["sample_33mK_clean"].name,)).fetchone()
    assert clean["integrity_pass"] == 1

def test_calibration_and_temp(tmp_path):
    root = tmp_path / "data"; make_corpus(root)
    conn = _db(tmp_path); crawl(conn, [root])
    row = conn.execute("""SELECT r.temp_mK, r.cooldown_resolved, c.f0_per_volt, c.label, r.temp_sidecar_path
                          FROM raw_measurement r JOIN cooldown c ON c.id=r.cooldown_id
                          WHERE r.filename='DAQ_4us_14mK_20000pts_1.txt'""").fetchone()
    assert row["temp_mK"] == 14.0 and row["f0_per_volt"] == 0.837
    assert row["label"] == "YbZn2GaO5_Dec2025" and row["cooldown_resolved"] == 1
    assert row["temp_sidecar_path"] is not None
    bkg = conn.execute("""SELECT c.f0_per_volt FROM raw_measurement r JOIN cooldown c ON c.id=r.cooldown_id
                          WHERE r.filename='DAQ_4us_300mK_20000pts_1.txt'""").fetchone()
    assert bkg["f0_per_volt"] == 0.834

def test_idempotent(tmp_path):
    root = tmp_path / "data"; make_corpus(root)
    conn = _db(tmp_path); crawl(conn, [root]); s2 = crawl(conn, [root])
    assert s2["ingested"] == 0 and s2["skipped"] == 5

def test_empty_root_graceful(tmp_path):
    (tmp_path / "data").mkdir()
    conn = _db(tmp_path); assert crawl(conn, [tmp_path / "data"])["ingested"] == 0

def test_native_filenames_ingest_with_outcome(tmp_path):
    """AutoSQUID-native names (date token + _OUTCOME suffix) must parse, not be flagged unparseable."""
    root = tmp_path / "data"; make_native_corpus(root)
    conn = _db(tmp_path); s = crawl(conn, [root])
    assert s["ingested"] == 2 and s["failed_parse"] == 0
    jump = conn.execute("SELECT outcome, integrity_pass FROM raw_measurement WHERE filename LIKE '%_JUMP.txt'").fetchone()
    assert jump["outcome"] == "JUMP" and jump["integrity_pass"] == 0
    clean = conn.execute("SELECT outcome, integrity_pass FROM raw_measurement WHERE filename='DAQ_Jun01_4us_33mK_20000pts_2.txt'").fetchone()
    assert clean["integrity_pass"] == 1   # outcome from filename is NULL until log enrichment

def test_bare_lab_format_no_temp_no_log(tmp_path):
    """The common lab-PC case: DAQ_100us_4K_... names, no TEMP.csv, no experiment_log."""
    root = tmp_path / "data"; make_bare_corpus(root, date="12-23-2025")
    conn = _db(tmp_path); s = crawl(conn, [root])
    assert s["ingested"] == 2 and s["failed_parse"] == 0
    r = conn.execute("""SELECT r.temp_mK, r.temp_sidecar_path, r.cooldown_resolved, c.f0_per_volt
                        FROM raw_measurement r JOIN cooldown c ON c.id=r.cooldown_id
                        WHERE r.filename='DAQ_4us_4K_20000pts_1.txt'""").fetchone()
    assert r["temp_mK"] == 4000.0 and r["temp_sidecar_path"] is None      # no temp.csv -> NULL
    assert r["cooldown_resolved"] == 1 and r["f0_per_volt"] == 0.837    # resolved by header date
    assert enrich_from_logs(conn, [root]) == 0                            # no logs -> harmless no-op

def test_recent_data_logged_but_flagged_unresolved(tmp_path):
    """Recently-acquired data whose date is in no registered cooldown is still LOGGED,
    but flagged unresolved (cooldown_id NULL) so calibration is never guessed."""
    root = tmp_path / "data"; make_bare_corpus(root, date="08-15-2026")
    conn = _db(tmp_path); s = crawl(conn, [root])
    assert s["ingested"] == 2 and s["unresolved"] == 2
    r = conn.execute("SELECT cooldown_id, cooldown_resolved, temp_mK FROM raw_measurement LIMIT 1").fetchone()
    assert r["cooldown_id"] is None and r["cooldown_resolved"] == 0 and r["temp_mK"] == 4000.0

def test_reresolve_after_registering_cooldown(tmp_path):
    """Log recent data, then register/extend its cooldown -> resolves WITHOUT re-crawling."""
    root = tmp_path / "data"; make_bare_corpus(root, date="08-15-2026")
    conn = _db(tmp_path); crawl(conn, [root])
    assert conn.execute("SELECT count(*) FROM raw_measurement WHERE cooldown_resolved=0").fetchone()[0] == 2
    conn.execute("UPDATE cooldown SET end_date='2026-08-31' WHERE label='Sapphire_May2026'")   # extend to cover it
    assert reresolve_cooldowns(conn) == 2
    r = conn.execute("""SELECT c.f0_per_volt FROM raw_measurement r JOIN cooldown c ON c.id=r.cooldown_id
                        LIMIT 1""").fetchone()
    assert r["f0_per_volt"] == 0.762
