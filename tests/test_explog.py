from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from catalog.explog import enrich_from_logs, parse_experiment_log
from tests._fixtures import make_native_corpus, seed_test_cooldowns

def _ready(tmp_path):
    root = tmp_path / "data"; make_native_corpus(root)
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn); seed_test_cooldowns(conn)
    crawl(conn, [root])
    return conn, root

def test_parse_experiment_log_reads_rows(tmp_path):
    root = tmp_path / "data"; make_native_corpus(root)
    rows = parse_experiment_log(root / "Jun01-2026" / "experiment_log.txt")
    assert len(rows) == 2
    assert {r["outcome"] for r in rows} == {"JUMP", "CLEAN"}

def test_enrich_copies_log_metadata_onto_rows(tmp_path):
    conn, root = _ready(tmp_path)
    n = enrich_from_logs(conn, [root])
    assert n == 2
    clean = conn.execute("""SELECT outcome, n_resets, t_start_K, t_end_K
                            FROM raw_measurement WHERE filename='DAQ_Jun01_4us_33mK_20000pts_2.txt'""").fetchone()
    assert clean["outcome"] == "CLEAN" and clean["n_resets"] == 2
    assert abs(clean["t_start_K"] - 0.0331) < 1e-6 and abs(clean["t_end_K"] - 0.0332) < 1e-6
    jump = conn.execute("""SELECT outcome, jump_time_s FROM raw_measurement WHERE filename LIKE '%_JUMP.txt'""").fetchone()
    assert jump["outcome"] == "JUMP" and jump["jump_time_s"] is not None

def test_disagreement_is_queryable(tmp_path):
    """The acquisition outcome (CLEAN) and our integrity gate (pass) agree here; the
    catalog can surface any disagreement via a query — confirm the columns coexist."""
    conn, root = _ready(tmp_path)
    enrich_from_logs(conn, [root])
    disagree = conn.execute(
        "SELECT count(*) FROM raw_measurement WHERE outcome='CLEAN' AND integrity_pass=0").fetchone()[0]
    assert disagree == 0
