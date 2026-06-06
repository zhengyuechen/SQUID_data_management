from pathlib import Path
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from catalog.explog import enrich_from_logs
from catalog.dispatch import run_analysis
from catalog.lineage import raws_of_product, products_of_raw
from catalog.playbook import parse_playbook
from tests._fixtures import (make_corpus, make_native_corpus, _healthy,
                             SCAN_INTERVAL_S, set_header_date)
from catalog.squid import sq

PB = Path(__file__).resolve().parents[1] / "analysis_playbook.md"

def test_full_pipeline(tmp_path):
    data_root = tmp_path / "data"; make_corpus(data_root); make_native_corpus(data_root)
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn)

    # (1) idempotent crawl over both layouts (5 simple + 2 native = 7)
    assert crawl(conn, [data_root])["ingested"] == 7
    assert crawl(conn, [data_root])["ingested"] == 0

    # (2) experiment_log enrichment copies the acquisition's outcome + temperatures
    assert enrich_from_logs(conn, [data_root]) == 2
    assert conn.execute("SELECT outcome FROM raw_measurement WHERE filename='DAQ_Jun01_4us_33mK_20000pts_2.txt'"
                        ).fetchone()["outcome"] == "CLEAN"

    # (3) temperature query returns exactly the expected clean traces
    assert conn.execute("SELECT count(*) FROM raw_measurement WHERE temp_mK=14 AND integrity_pass=1").fetchone()[0] == 1

    # (4) dispatch honors the playbook policy (welch_P from the file), via AutoSQUID plot_psd
    pol = parse_playbook(PB)
    pid = run_analysis(conn, "psd", "temp_mK = 14", {"P": [pol["welch_P"][0]], "window": pol["window"]},
                       results_root=tmp_path / "r", stamp="2026-06-05_140000")[0]
    assert Path(conn.execute("SELECT artifact_path FROM derived_product WHERE id=?", (pid,)).fetchone()[0]).exists()

    # (5) lineage round-trips both directions
    raws = raws_of_product(conn, pid); assert len(raws) == 1
    assert pid in [p["id"] for p in products_of_raw(conn, raws[0]["id"])]

    # (6) playbook edit (bump P) -> new product, zero code change
    pid2 = run_analysis(conn, "psd", "temp_mK = 14", {"P": [100], "window": pol["window"]},
                        results_root=tmp_path / "r", stamp="2026-06-05_140100")[0]
    assert pid2 != pid and conn.execute("SELECT count(*) FROM derived_product").fetchone()[0] == 2

    # (7) auto-digest: drop a new file (dated into a cooldown window), re-crawl, it appears + resolves
    newp = data_root / "sample" / "DAQ_4us_50mK_20000pts_1.txt"
    sq.save_pcs102(str(newp), _healthy(99), SCAN_INTERVAL_S); set_header_date(newp, "12-26-2025")
    assert crawl(conn, [data_root])["ingested"] == 1
    row = conn.execute("""SELECT c.f0_per_volt FROM raw_measurement r JOIN cooldown c ON c.id=r.cooldown_id
                          WHERE r.temp_mK=50""").fetchone()
    assert row is not None and row["f0_per_volt"] == 0.837
