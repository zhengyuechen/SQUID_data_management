from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from catalog.explog import enrich_from_logs, parse_experiment_log
from tests._fixtures import make_native_corpus, seed_test_cooldowns, N, SCAN_INTERVAL_S

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
    jump = conn.execute("""SELECT outcome, usable_seconds, usable_points FROM raw_measurement WHERE filename LIKE '%_JUMP.txt'""").fetchone()
    assert jump["outcome"] == "JUMP" and jump["usable_seconds"] is not None and jump["usable_points"] is not None

def _write_legacy_log(folder, jump_name, clean_name):
    """A pre-2026-06 experiment_log.txt: jump_index/jump_time_s instead of usable_points/usable_seconds.
    This is the format of EVERY trace acquired so far (the real on-disk corpus), so enrich must read it.
    Clean rows carry the no-jump sentinels jump_index=-1, empty jump_time_s."""
    dur = N * SCAN_INTERVAL_S
    cols = ("timestamp\tscan_interval_us\tn_target\tn_acquired\tn_clean\tattempt\toutcome\t"
            "jump_index\tjump_time_s\tn_resets\tmean_V\tstd_V\tT_start_K\tT_end_K\tfilename")
    jump = f"2026-06-01T12:00:00\t4\t{N}\t{N//2}\t0\t1\tJUMP\t{N//2}\t{round(dur/2, 3)}\t1\t0.5\t0.2\t0.033\t0.034\t{jump_name}"
    clean = f"2026-06-01T12:01:00\t4\t{N}\t{N}\t1\t2\tCLEAN\t-1\t\t2\t0.012\t0.002\t0.0331\t0.0332\t{clean_name}"
    (folder / "experiment_log.txt").write_text("\n".join([cols, jump, clean]) + "\n")

def test_enrich_falls_back_to_legacy_jump_columns(tmp_path):
    """Legacy logs (jump_index/jump_time_s) must still populate usable_seconds/usable_points; the
    -1/empty no-jump sentinels on the clean row must map to NULL, not -1."""
    root = tmp_path / "data"; make_native_corpus(root)            # creates the DAQ files + folder
    folder = root / "Jun01-2026"
    _write_legacy_log(folder, "DAQ_Jun01_4us_33mK_20000pts_1_JUMP.txt",
                              "DAQ_Jun01_4us_33mK_20000pts_2.txt")  # overwrite the new-format log with a legacy one
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn); seed_test_cooldowns(conn)
    crawl(conn, [root]); enrich_from_logs(conn, [root])
    jump = conn.execute("SELECT usable_seconds, usable_points FROM raw_measurement WHERE filename LIKE '%_JUMP.txt'").fetchone()
    assert jump["usable_points"] == N // 2 and abs(jump["usable_seconds"] - N * SCAN_INTERVAL_S / 2) < 1e-6
    clean = conn.execute("SELECT usable_seconds, usable_points FROM raw_measurement WHERE filename='DAQ_Jun01_4us_33mK_20000pts_2.txt'").fetchone()
    assert clean["usable_seconds"] is None and clean["usable_points"] is None     # -1 / '' sentinels -> NULL

def test_disagreement_is_queryable(tmp_path):
    """The acquisition outcome (CLEAN) and our integrity gate (pass) agree here; the
    catalog can surface any disagreement via a query — confirm the columns coexist."""
    conn, root = _ready(tmp_path)
    enrich_from_logs(conn, [root])
    disagree = conn.execute(
        "SELECT count(*) FROM raw_measurement WHERE outcome='CLEAN' AND integrity_pass=0").fetchone()[0]
    assert disagree == 0
