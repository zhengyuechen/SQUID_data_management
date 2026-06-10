"""PPT setup-parameter extractor: parse the dated setup slides of the measurement decks,
pull the calibration factor (f0/V — the load-bearing field for PSD) + V-Phi context, and
propose a human-confirmed `coollog add-cooldown`. Grammar fixtures are the REAL slide text."""
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog import ppt_extract as pe
from tests._fixtures import MAY2026_SETUP_BODY, DEC2025_SETUP_BODY, make_setup_deck


def test_sample_from_filename():
    assert pe.sample_from_filename("SQ180 w Sapphire - Measurements May2026.pptx") == "Sapphire"
    assert pe.sample_from_filename("SQ180 w YbZn2GaO5 - Measurements Dec2025.pptx") == "YbZn2GaO5"
    assert pe.sample_from_filename("unrelated.pptx") is None


def test_parse_may2026_setup_equals_separator():
    r = pe.parse_setup_slide("5/16/2026 Setup for 11 mK MXC", MAY2026_SETUP_BODY)
    assert r is not None
    assert r["f0_per_volt"] == 0.762            # 'Factor = 0.762 Fo/V'
    assert r["flux_jump_v"] == 1.312
    assert r["setup_date"] == "2026-05-16"
    assert "11" in r["mxc_label"]
    p = r["params"]
    assert p["array_s_bias_ma"] == 0.3          # section-aware: Array S-bias
    assert p["squid_s_bias_ma"] == 0.0654       # ... vs SQUID S-bias (same name, different value)
    assert p["array_a_bias_ua"] == 21.123
    assert p["array_offset_mv"] == 0.6607
    assert p["array_output_vpp"] == 5.517
    assert p["squid_a_flux_ua"] == 5.861


def test_parse_dec2025_setup_colon_and_tilde_separators():
    r = pe.parse_setup_slide("12/22/2025 Setup for 14 mK MXC", DEC2025_SETUP_BODY)
    assert r["f0_per_volt"] == 0.837            # 'Calibration Factor: 0.837 Fo/V'  (colon)
    assert r["flux_jump_v"] is None             # this slide records no flux jump
    assert r["setup_date"] == "2025-12-22"
    p = r["params"]
    assert p["array_s_bias_ma"] == 0.3
    assert p["squid_s_bias_ma"] == 0.0752
    assert p["array_output_vpp"] == 4.5         # 'Output ~ 4.5 Vpp'  (tilde)
    assert p["squid_output_v"] == 0.7


def test_measurement_slide_is_not_a_setup_slide():
    assert pe.parse_setup_slide("11mK Raw DAQ: 4us", "Saved 5/16 12:08pm") is None


def test_two_digit_year_in_title():
    r = pe.parse_setup_slide("12/26/25 Setup for 11 mK MXC",
                             "SQUID auto-calibration\nFactor: 0.837 Fo/V")
    assert r["setup_date"] == "2025-12-26"


def test_extract_deck(tmp_path):
    deck = make_setup_deck(tmp_path / "SQ180 w Sapphire - Measurements May2026.pptx")
    d = pe.extract_deck(deck)
    assert d["sample_guess"] == "Sapphire"
    assert d["slide_count"] == 3
    assert len(d["setups"]) == 1                # only the setup slide, not title/measurement
    assert d["setups"][0]["f0_per_volt"] == 0.762
    assert d["content_hash"]


def test_crawl_decks_populates_tables_and_is_idempotent(tmp_path):
    pptdir = tmp_path / "ppt"
    make_setup_deck(pptdir / "SQ180 w Sapphire - Measurements May2026.pptx")
    conn = connect(":memory:"); init_db(conn); seed_lookups(conn)

    s1 = pe.crawl_decks(conn, [pptdir])
    assert s1["decks"] == 1 and s1["setups"] == 1
    assert conn.execute("SELECT count(*) FROM deck").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM deck_setup WHERE f0_per_volt IS NOT NULL").fetchone()[0] == 1

    s2 = pe.crawl_decks(conn, [pptdir])         # unchanged file -> skipped, no duplicate rows
    assert s2["skipped"] == 1 and s2["decks"] == 0
    assert conn.execute("SELECT count(*) FROM deck").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM deck_setup").fetchone()[0] == 1


def test_crawl_decks_tolerates_an_unreadable_deck(tmp_path):
    pptdir = tmp_path / "ppt"
    make_setup_deck(pptdir / "SQ180 w Sapphire - Measurements May2026.pptx")
    (pptdir / "corrupt.pptx").write_bytes(b"this is not a zip / pptx")   # an unreadable deck
    conn = connect(":memory:"); init_db(conn); seed_lookups(conn)

    s = pe.crawl_decks(conn, [pptdir])             # must NOT raise; the good deck still indexes
    assert s["decks"] == 1 and s["failed"] == 1
    assert conn.execute("SELECT count(*) FROM deck").fetchone()[0] == 1


def test_propose_cooldowns_is_a_human_confirmable_command(tmp_path):
    pptdir = tmp_path / "ppt"
    make_setup_deck(pptdir / "SQ180 w Sapphire - Measurements May2026.pptx")
    conn = connect(":memory:"); init_db(conn); seed_lookups(conn)
    pe.crawl_decks(conn, [pptdir])

    props = pe.propose_cooldowns(conn)
    assert len(props) == 1
    p = props[0]
    assert p["f0_per_volt"] == 0.762
    assert p["sample_guess"] == "Sapphire"
    assert abs(p["squid_s_bias_ma"] - 0.0654) < 1e-9

    cmd = pe.format_proposal(p)
    assert "add-cooldown" in cmd                 # a ready-to-run command, NOT an auto-write
    assert "--f0 0.762" in cmd
    assert "Sapphire" in cmd
