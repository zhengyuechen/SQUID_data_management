from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from catalog.dispatch import run_analysis
from tests._fixtures import make_corpus

def _ready(tmp_path):
    make_corpus(tmp_path / "data")
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn)
    crawl(conn, [tmp_path / "data"]); return conn

def test_one_product_per_clean_trace(tmp_path):
    conn = _ready(tmp_path)
    pids = run_analysis(conn, "psd", "temp_mK = 33", {"P": [10]},
                        results_root=tmp_path / "r", stamp="2026-06-05_120000")
    assert len(pids) == 2          # two CLEAN 33 mK traces (railed one excluded)
    assert conn.execute("SELECT count(*) FROM product_input").fetchone()[0] == 2

def test_excludes_failed(tmp_path):
    conn = _ready(tmp_path)
    got = conn.execute("SELECT count(*) FROM raw_measurement WHERE temp_mK=33 AND integrity_pass=1").fetchone()[0]
    assert got == 2

def test_caches(tmp_path):
    conn = _ready(tmp_path)
    a = run_analysis(conn, "psd", "temp_mK = 14", {"P": [10]}, results_root=tmp_path / "r", stamp="2026-06-05_120100")
    b = run_analysis(conn, "psd", "temp_mK = 14", {"P": [10]}, results_root=tmp_path / "r", stamp="2026-06-05_120200")
    assert a == b
    assert conn.execute("SELECT count(*) FROM derived_product").fetchone()[0] == 1
