#!/usr/bin/env python3
"""Cooldown logbook CLI — record/read per-cooldown setup + notes (human-readable).

  python coollog.py show <label>                         # print setup + notes
  python coollog.py note <label> [--phase run] "msg"     # append a note, then re-index
  python coollog.py load                                 # (re)index all cooldowns/*.md into the catalog
  python coollog.py list                                 # cooldowns + note counts
"""
import sys; sys.path.insert(0, ".")
import argparse
from catalog.db import connect, init_db
from catalog.cooldown_log import load_logbooks, append_note, render

def main():
    ap = argparse.ArgumentParser(description="Cooldown logbook: setup + notes per cooldown.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show");  s.add_argument("label")
    n = sub.add_parser("note");  n.add_argument("label"); n.add_argument("text"); n.add_argument("--phase", default="run")
    sub.add_parser("load")
    sub.add_parser("list")
    ap.add_argument("--db", default="catalog.sqlite")
    a = ap.parse_args()

    conn = connect(a.db); init_db(conn)        # ensure schema is migrated (logbook columns/table)
    if a.cmd == "note":
        md = append_note(a.label, a.phase, a.text)
        load_logbooks(conn)
        print(f"appended [{a.phase}] to {md}")
        print(render(conn, a.label))
    elif a.cmd == "show":
        print(render(conn, a.label))
    elif a.cmd == "load":
        print("indexed logbooks:", load_logbooks(conn))
    elif a.cmd == "list":
        for r in conn.execute("""SELECT c.label, c.f0_per_volt,
                                        (SELECT count(*) FROM cooldown_note WHERE cooldown_id=c.id) AS notes,
                                        (c.logbook_path IS NOT NULL) AS has_logbook
                                 FROM cooldown c ORDER BY c.label"""):
            print(f"  {r['label']:<20} f₀/V={r['f0_per_volt']}  notes={r['notes']}  logbook={'yes' if r['has_logbook'] else 'no'}")
    conn.close()

if __name__ == "__main__":
    main()
