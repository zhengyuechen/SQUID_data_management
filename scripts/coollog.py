#!/usr/bin/env python3
"""Cooldown logbook CLI — record/read per-cooldown setup + notes, and edit the
calibration registry (the `cooldown` table in catalog.sqlite — the source of truth).

  python coollog.py show <label>                         # print setup + notes
  python coollog.py note <label> [--phase run] "msg"     # append a note, then re-index
  python coollog.py load                                 # (re)index all cooldowns/*.md into the catalog
  python coollog.py list                                 # cooldowns + note counts
  python coollog.py registry                              # dump the calibration registry (dates, f0/V, S-bias)
  python coollog.py add-cooldown <label> --sample S --start 2026-05-18 --end 2026-06-30 \
                                 --f0 0.762 [--formula Al2O3] [--fridge dilution] [--s-bias 0.0654]
"""
import sys; sys.path.insert(0, ".")
import argparse
from catalog.db import connect, init_db
from catalog.seed import register_cooldown
from catalog.cooldown_log import load_logbooks, append_note, render
from catalog.crawl import reresolve_cooldowns

def main():
    ap = argparse.ArgumentParser(description="Cooldown logbook + calibration registry (in catalog.sqlite).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show");  s.add_argument("label")
    n = sub.add_parser("note");  n.add_argument("label"); n.add_argument("text"); n.add_argument("--phase", default="run")
    sub.add_parser("load")
    sub.add_parser("list")
    sub.add_parser("registry")
    ac = sub.add_parser("add-cooldown", help="register/update a cooldown in catalog.sqlite's cooldown table")
    ac.add_argument("label")
    ac.add_argument("--sample", required=True)
    ac.add_argument("--start", required=True, help="ISO start date YYYY-MM-DD (inclusive)")
    ac.add_argument("--end", required=True, help="ISO end date YYYY-MM-DD (inclusive)")
    ac.add_argument("--f0", type=float, required=True, help="calibration factor f0 per volt")
    ac.add_argument("--formula", default=None)
    ac.add_argument("--fridge", default="dilution")
    ac.add_argument("--s-bias", dest="s_bias", type=float, default=None)
    ap.add_argument("--db", default="catalog.sqlite")
    a = ap.parse_args()

    conn = connect(a.db); init_db(conn)        # ensure schema is migrated (logbook columns/table)
    if a.cmd == "add-cooldown":
        register_cooldown(conn, a.label, a.sample, a.start, a.end, a.f0,
                          formula=a.formula, fridge=a.fridge, s_bias_ma=a.s_bias)
        resolved = reresolve_cooldowns(conn)   # back-fill any already-crawled rows now in range (no file reads)
        print(f"registered {a.label}: {a.sample}  {a.start}→{a.end}  f0/V={a.f0}"
              + (f"  (resolved {resolved} previously-unresolved traces)" if resolved else ""))
    elif a.cmd == "registry":
        for r in conn.execute("""SELECT c.label, s.name sample, c.start_date, c.end_date,
                                        c.f0_per_volt, c.s_bias_ma
                                 FROM cooldown c LEFT JOIN sample s ON s.id=c.sample_id
                                 ORDER BY c.start_date"""):
            print(f"  {r['label']:<20} {(r['sample'] or ''):<20} {r['start_date']}→{r['end_date']}  "
                  f"f0/V={r['f0_per_volt']}  S-bias={r['s_bias_ma']}")
    elif a.cmd == "note":
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
