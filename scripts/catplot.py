#!/usr/bin/env python3
"""Dispatch ANY catalog analyzer over ANY selection and save the figure(s), recording
metadata + lineage in the catalog. Generic by design: the selection is given by flags,
so this one script covers every case — a temperature, an interval, a cooldown, all of
the background, a sub-band, etc. Nothing is hardcoded.

Examples:
  python catplot.py psd_overlay --temp 50 --cooldown YbZn2GaO5_Dec2025 --title "sample @ 50 mK, all intervals"
  python catplot.py psd_overlay --cooldown Sapphire_Dec2025 --name bkg --title "background overlay"
  python catplot.py psd_overlay --interval 4 --where "temp_mK <= 20" --name 4us-lowT
  python catplot.py psd --temp 14 --cooldown YbZn2GaO5_Dec2025      # per-trace analyzer also works
"""
import sys; sys.path.insert(0, ".")
import argparse
from datetime import datetime
from catalog.db import connect
from catalog.registry import REGISTRY, GROUP_REGISTRY
from catalog.dispatch import run_analysis, run_group_analysis, normalize_outcome
from catalog.lineage import raws_of_product

def build_where(a):
    """Compose a WHERE predicate from convenience flags + a raw --where (all ANDed).
    integrity_pass=1 is always added by the dispatcher itself (unless widened)."""
    clauses = []
    if a.cooldown:        clauses.append(f"cooldown_id=(SELECT id FROM cooldown WHERE label='{a.cooldown}')")
    if a.temp is not None:     clauses.append(f"temp_mK={a.temp}")
    if a.interval is not None: clauses.append(f"scan_interval_us={a.interval}")
    if a.outcome:         clauses.append(f"outcome='{normalize_outcome(a.outcome)}'")
    if a.where:           clauses.append(f"({a.where})")
    return " AND ".join(clauses)

def main():
    kinds = sorted(set(REGISTRY) | set(GROUP_REGISTRY))
    ap = argparse.ArgumentParser(description="Dispatch a catalog analyzer over a selection (generic).")
    ap.add_argument("kind", help="analyzer kind: " + ", ".join(kinds))
    ap.add_argument("--where", default="", help="raw SQL predicate on raw_measurement")
    ap.add_argument("--cooldown", help="cooldown label, e.g. YbZn2GaO5_Dec2025")
    ap.add_argument("--temp", type=float, help="temperature in mK")
    ap.add_argument("--interval", type=float, help="scan interval in us")
    ap.add_argument("--outcome", help="filter by the acquisition outcome: surged/jumped/clean/bad_baseline "
                                      "(=SURGE/JUMP/CLEAN/BAD_BASELINE). A non-clean outcome auto-includes "
                                      "gate-failed traces, so you don't also need --any.")
    ap.add_argument("--P", type=int, nargs="+", default=[100], help="Welch segment count(s)")
    ap.add_argument("--window", help="FFT window (analyzer default: hanning)")
    ap.add_argument("--title", help="figure title")
    ap.add_argument("--name", help="short slug for the results/ folder")
    ap.add_argument("--include-partial", action="store_true",
                    help="(group analyzers) also include jump/surge traces, truncated to their usable pre-jump prefix")
    ap.add_argument("--any", action="store_true",
                    help="(group analyzers) select ANY trace regardless of integrity — for diagnostic raw inspection (e.g. frozen traces)")
    ap.add_argument("--limit", type=int, help="cap the number of traces selected")
    ap.add_argument("--db", default="catalog.sqlite")
    a = ap.parse_args()

    params = {"P": a.P}
    if a.window: params["window"] = a.window
    if a.title:  params["title"] = a.title
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    stamp = f"{ts}_{a.name}" if a.name else ts
    where = build_where(a)
    # A non-clean outcome (SURGE/JUMP/BAD_BASELINE) is gate-failed, so widen selection to ANY trace.
    include_all = a.any or (a.outcome is not None and normalize_outcome(a.outcome) != "CLEAN")

    conn = connect(a.db)
    if a.kind in GROUP_REGISTRY:
        pids = [run_group_analysis(conn, a.kind, where, params, results_root="figures", stamp=stamp,
                                   include_partial=a.include_partial, include_all=include_all, limit=a.limit)]
    elif a.kind in REGISTRY:
        pids = run_analysis(conn, a.kind, where, params, results_root="figures", stamp=stamp,
                            include_all=include_all)
    else:
        conn.close(); sys.exit(f"unknown kind {a.kind!r}; choose from {kinds}")

    for pid in pids:
        r = conn.execute("SELECT artifact_path, scalars FROM derived_product WHERE id=?", (pid,)).fetchone()
        ins = raws_of_product(conn, pid)
        print(f"product {pid}  ->  {r['artifact_path']}")
        print(f"  scalars: {r['scalars']}")
        print(f"  inputs : {len(ins)} traces {[i['filename'] for i in ins][:6]}")
    conn.close()

if __name__ == "__main__":
    main()
