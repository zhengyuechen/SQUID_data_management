from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.cooldown_log import parse_logbook, load_logbooks, append_note, render
from tests._fixtures import seed_test_cooldowns

LOGBOOK = """# Cooldown logbook — YbZn2GaO5_Dec2025
## Setup
SQUID V-Phi: S-bias = 0.0752 mA
Calibration factor: 0.837
## Notes
- [setup] Restored bias/flux from background.
- [run] S-bias drifted 0.0752 -> 0.0747 mA; ran at 0.0747.
"""

def _write(tmp, text=LOGBOOK):
    d = tmp / "cooldowns"; d.mkdir()
    (d / "YbZn2GaO5_Dec2025.md").write_text(text)
    return d

def test_parse_logbook(tmp_path):
    d = _write(tmp_path)
    lb = parse_logbook(d / "YbZn2GaO5_Dec2025.md")
    assert lb["calibration_factor"] == 0.837
    assert "S-bias = 0.0752 mA" in lb["setup"]
    assert lb["notes"] == [("setup", "Restored bias/flux from background."),
                           ("run", "S-bias drifted 0.0752 -> 0.0747 mA; ran at 0.0747.")]

def test_load_logbooks_onto_cooldown(tmp_path):
    d = _write(tmp_path)
    conn = connect(tmp_path / "c.sqlite"); init_db(conn); seed_lookups(conn); seed_test_cooldowns(conn)
    assert load_logbooks(conn, d) == 1
    c = conn.execute("SELECT setup_notes, logbook_path FROM cooldown WHERE label='YbZn2GaO5_Dec2025'").fetchone()
    assert "0.0752 mA" in c["setup_notes"] and c["logbook_path"].endswith("YbZn2GaO5_Dec2025.md")
    notes = conn.execute("""SELECT phase, note FROM cooldown_note cn JOIN cooldown c ON c.id=cn.cooldown_id
                            WHERE c.label='YbZn2GaO5_Dec2025' ORDER BY ord""").fetchall()
    assert [n["phase"] for n in notes] == ["setup", "run"]
    assert "0.837 f₀/V" in render(conn, "YbZn2GaO5_Dec2025") or "0.837" in render(conn, "YbZn2GaO5_Dec2025")

def test_append_note_roundtrips(tmp_path):
    d = _write(tmp_path)
    conn = connect(tmp_path / "c.sqlite"); init_db(conn); seed_lookups(conn); seed_test_cooldowns(conn); load_logbooks(conn, d)
    append_note("YbZn2GaO5_Dec2025", "run", "Base temp reached 10 mK.", logbook_dir=d)
    load_logbooks(conn, d)
    last = conn.execute("""SELECT note FROM cooldown_note cn JOIN cooldown c ON c.id=cn.cooldown_id
                           WHERE c.label='YbZn2GaO5_Dec2025' ORDER BY ord DESC LIMIT 1""").fetchone()
    assert last["note"] == "Base temp reached 10 mK."

def test_load_idempotent_no_duplicate_notes(tmp_path):
    d = _write(tmp_path)
    conn = connect(tmp_path / "c.sqlite"); init_db(conn); seed_lookups(conn); seed_test_cooldowns(conn)
    load_logbooks(conn, d); load_logbooks(conn, d)
    n = conn.execute("SELECT count(*) FROM cooldown_note").fetchone()[0]
    assert n == 2          # re-load replaces, doesn't duplicate
