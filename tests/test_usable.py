from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl, compute_usable_s
from catalog.dispatch import run_group_analysis
from catalog.lineage import raws_of_product
from catalog.cooldown_log import write_calibration_md
from catalog.squid import sq
from tests._fixtures import make_corpus, _jumped, set_header_date, SCAN_INTERVAL_S, N

def _ready(tmp_path):
    """make_corpus (clean + a stuck/railed trace) + an added JUMP trace, crawled + usable computed."""
    root = tmp_path / "data"; make_corpus(root)
    jp = root / "sample" / "DAQ_4us_22mK_20000pts_1.txt"
    sq.save_pcs102(str(jp), _jumped(7), SCAN_INTERVAL_S); set_header_date(jp, "12-23-2025")
    conn = connect(tmp_path / "c.sqlite"); init_db(conn); seed_lookups(conn)
    crawl(conn, [root]); compute_usable_s(conn)
    return conn

def test_usable_s_clean_jump_stuck(tmp_path):
    conn = _ready(tmp_path)
    clean = conn.execute("SELECT usable_s, duration_s FROM raw_measurement WHERE filename='DAQ_4us_14mK_20000pts_1.txt'").fetchone()
    assert abs(clean["usable_s"] - clean["duration_s"]) < 1e-9          # CLEAN -> full duration
    jump = conn.execute("SELECT usable_s, duration_s, integrity_pass FROM raw_measurement WHERE filename='DAQ_4us_22mK_20000pts_1.txt'").fetchone()
    assert jump["integrity_pass"] == 0 and jump["usable_s"] is not None and 0 < jump["usable_s"] < jump["duration_s"]  # JUMP -> prefix
    stuck = conn.execute("SELECT usable_s FROM raw_measurement WHERE filename='DAQ_4us_33mK_20000pts_3.txt'").fetchone()
    assert stuck["usable_s"] is None                                   # stuck/frozen -> not usable

def test_include_partial_pulls_in_the_jump_trace(tmp_path):
    conn = _ready(tmp_path)
    clean_only = run_group_analysis(conn, "psd_overlay", "temp_mK IN (14,22)", {"P": [10]},
                                    results_root=tmp_path / "f", stamp="s1")
    with_partial = run_group_analysis(conn, "psd_overlay", "temp_mK IN (14,22)", {"P": [10]},
                                      results_root=tmp_path / "f", stamp="s2", include_partial=True)
    assert len(raws_of_product(conn, clean_only)) == 1                 # only the 14 mK clean trace
    assert len(raws_of_product(conn, with_partial)) == 2              # + the 22 mK jump trace (truncated)

def test_raw_overlay_plots_any_trace_including_frozen(tmp_path):
    from pathlib import Path
    conn = _ready(tmp_path)   # clean + jump + a stuck/railed (frozen) trace
    pid = run_group_analysis(conn, "raw_overlay", "scan_interval_us=4", {"downsample": 500},
                             results_root=tmp_path / "f", stamp="s", include_all=True, limit=3)
    raws = raws_of_product(conn, pid)
    assert 1 <= len(raws) <= 3                       # include_all selects failed traces too
    art = conn.execute("SELECT artifact_path FROM derived_product WHERE id=?", (pid,)).fetchone()[0]
    assert Path(art).exists()

def test_calibration_md_is_human_readable(tmp_path):
    p = write_calibration_md(tmp_path / "_calibration.md")
    text = p.read_text()
    assert "0.837" in text and "0.834" in text and "0.762" in text
    assert "S-bias" in text and "f₀/V" in text and "Essentials" in text
