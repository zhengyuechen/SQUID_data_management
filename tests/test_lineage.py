from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from catalog.dispatch import run_analysis
from catalog.lineage import products_of_raw, raws_of_product
from tests._fixtures import make_corpus

def _ready(tmp_path):
    make_corpus(tmp_path / "data")
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn)
    crawl(conn, [tmp_path / "data"]); return conn

def test_round_trips(tmp_path):
    conn = _ready(tmp_path)
    pid = run_analysis(conn, "psd", "temp_mK = 14", {"P": [10]}, results_root=tmp_path / "r", stamp="s1")[0]
    raws = raws_of_product(conn, pid)
    assert len(raws) == 1 and raws[0]["filename"] == "DAQ_4us_14mK_20000pts_1.txt"
    run_analysis(conn, "time_series", "temp_mK = 14", {}, results_root=tmp_path / "r", stamp="s2")
    kinds = {p["kind"] for p in products_of_raw(conn, raws[0]["id"])}
    assert {"psd", "time_series"} <= kinds
