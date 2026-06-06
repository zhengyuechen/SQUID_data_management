from pathlib import Path
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from catalog.dispatch import run_group_analysis
from catalog.lineage import raws_of_product
from tests._fixtures import make_corpus

def _ready(tmp_path):
    make_corpus(tmp_path / "data")
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn)
    crawl(conn, [tmp_path / "data"]); return conn

def test_psd_overlay_is_one_product_with_many_inputs(tmp_path):
    conn = _ready(tmp_path)
    pid = run_group_analysis(conn, "psd_overlay", "scan_interval_us=4", {"P": [100]},
                             results_root=tmp_path / "r", stamp="2026-06-05_000000_overlay")
    # all clean 4us traces overlaid: sample 33mK x2 + 14mK x1 + bkg 300mK x1 = 4 (railed excluded)
    links = conn.execute("SELECT count(*) FROM product_input WHERE derived_product_id=?", (pid,)).fetchone()[0]
    assert links == 4
    roles = {r["role"] for r in raws_of_product(conn, pid)}
    assert roles == {"overlay_member"}
    art = conn.execute("SELECT artifact_path, scalars FROM derived_product WHERE id=?", (pid,)).fetchone()
    assert Path(art["artifact_path"]).exists() and '"n_traces":4' in art["scalars"]

def test_group_overlay_caches(tmp_path):
    conn = _ready(tmp_path)
    a = run_group_analysis(conn, "psd_overlay", "scan_interval_us=4", {"P": [100]},
                           results_root=tmp_path / "r", stamp="s1")
    b = run_group_analysis(conn, "psd_overlay", "scan_interval_us=4", {"P": [100]},
                           results_root=tmp_path / "r", stamp="s2")
    assert a == b
    assert conn.execute("SELECT count(*) FROM derived_product WHERE kind='psd_overlay'").fetchone()[0] == 1
