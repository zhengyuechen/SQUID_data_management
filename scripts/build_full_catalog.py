"""Build/refresh the persistent catalog.sqlite over the configured data roots, then
report contents. Idempotent + incremental: re-run after dropping in new folders.

Data roots + DB path come from config.json (see catalog/config.py); falls back to the
dev-tree default when unconfigured. Override per run with --root / --db. First time on a
new machine: `python scripts/build_full_catalog.py --init`, edit config.json, run again."""
import sys; sys.path.insert(0, ".")
import argparse
import time
from pathlib import Path
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl, reresolve_cooldowns, compute_usable_s
from catalog.explog import enrich_from_logs
from catalog.cooldown_log import load_logbooks, write_calibration_md
from catalog.config import load_config, data_roots, ppt_roots, write_default_config

ap = argparse.ArgumentParser(description="Build/refresh the catalog over the configured data roots.")
ap.add_argument("--root", action="append", default=None,
                help="data root to crawl (repeatable); overrides config.json data_roots")
ap.add_argument("--db", default=None, help="catalog DB path (overrides config.json)")
ap.add_argument("--init", action="store_true", help="write a starter config.json and exit")
a = ap.parse_args()

if a.init:
    p, created = write_default_config()
    print(f"{'wrote' if created else 'kept existing'} {p}")
    print("edit its data_roots (and ppt_roots) to point at this machine's data, then run build again")
    sys.exit(0)

cfg = load_config()
roots = [Path(r) for r in a.root] if a.root else data_roots(cfg)
DB = Path(a.db or cfg["db"])

conn = connect(DB); init_db(conn); seed_lookups(conn)   # ensures instrument; cooldowns persist in catalog.sqlite (register via coollog add-cooldown)

t0 = time.time()
stats = crawl(conn, roots)
enriched = enrich_from_logs(conn, roots)
reresolved = reresolve_cooldowns(conn)                   # resolve any now-registered cooldowns, no re-read
compute_usable_s(conn)                                   # usable (pre-jump) duration per trace
logbooks = load_logbooks(conn)                           # index cooldowns/*.md setup + notes
write_calibration_md(conn)                               # regenerate cooldowns/_calibration.md (human-readable)
deck_stats = None
try:                                                     # index parameter decks (factual; calibration stays human-confirmed)
    from catalog.ppt_extract import crawl_decks          # crawl_decks itself tolerates a corrupt deck (per-deck);
    droots = ppt_roots(cfg)                              # only a MISSING python-pptx is swallowed here, so real bugs surface
    if droots:
        deck_stats = crawl_decks(conn, droots)
except ImportError as e:                                  # python-pptx not installed -> non-fatal, decks just aren't indexed
    print(f"[decks] python-pptx unavailable, skipped ppt indexing: {e}")
dt = time.time() - t0

on_disk = sum(1 for root in roots for _ in Path(root).rglob("DAQ_*.txt"))
n_rows = conn.execute("SELECT count(*) FROM raw_measurement").fetchone()[0]
print(f"=== built {DB.resolve()} ({DB.stat().st_size/1024:.0f} KB) in {dt:.0f}s ===")
print(f"data roots: {[str(r) for r in roots]}")
print(f"crawl: {stats}   log-enriched: {enriched}   newly calibration-resolved: {reresolved}   logbooks indexed: {logbooks}")
print(f"DAQ_*.txt on disk: {on_disk}   |   rows in catalog: {n_rows}")
if deck_stats:
    n_prop = conn.execute("SELECT count(*) FROM deck_setup WHERE f0_per_volt IS NOT NULL").fetchone()[0]
    print(f"decks indexed: {deck_stats}   ({n_prop} factor-bearing setup slides)  "
          f"->  `python scripts/coollog.py propose-from-ppt` for human-confirmed calibration proposals")

if n_rows == 0:
    print("\n(no measurements indexed yet)")
    if on_disk == 0:
        print("  -> no DAQ_*.txt found under the data roots above. Point them at this machine's data:")
        print("     python scripts/build_full_catalog.py --init   # writes config.json, then edit data_roots")
        print("     or pass one explicitly:  python scripts/build_full_catalog.py --root <path-to-data>")
    conn.close()
    sys.exit(0)

print("\n-- by cooldown (calibration applied) x integrity --")
for r in conn.execute("""SELECT COALESCE(c.label,'<unresolved>') label, c.f0_per_volt f0,
                                SUM(r.integrity_pass) clean, SUM(1-r.integrity_pass) failed, count(*) n
                         FROM raw_measurement r LEFT JOIN cooldown c ON c.id=r.cooldown_id
                         GROUP BY c.label ORDER BY c.label"""):
    print(f"   {r['label']:<20} f0={r['f0']}  clean={r['clean']}  failed={r['failed']}  total={r['n']}")

print("\n-- by scan interval --")
for r in conn.execute("""SELECT scan_interval_us iv, count(*) n, SUM(integrity_pass) clean
                         FROM raw_measurement GROUP BY scan_interval_us ORDER BY scan_interval_us"""):
    print(f"   {r['iv']:>6.0f} us   n={r['n']:<3} clean={r['clean']}")

tr = conn.execute("SELECT min(temp_mK) lo, max(temp_mK) hi, count(DISTINCT temp_mK) d FROM raw_measurement").fetchone()
print(f"\ntemperature coverage: {tr['lo']:.0f}-{tr['hi']:.0f} mK across {tr['d']} distinct setpoints")

print("\n-- integrity failures (gate-excluded) --")
for r in conn.execute("SELECT filename, integrity_reason FROM raw_measurement WHERE integrity_pass=0 ORDER BY filename"):
    print(f"   {r['filename']:<34} {r['integrity_reason'][:46]}")

unresolved = conn.execute("SELECT count(*) FROM raw_measurement WHERE cooldown_resolved=0").fetchone()[0]
print(f"\nunresolved-calibration rows: {unresolved}   unparseable filenames: {stats['failed_parse']}")
if unresolved:
    print("  -> register the cooldown(s) so calibration resolves (no re-read):")
    print("     python scripts/coollog.py add-cooldown <label> --sample S --start YYYY-MM-DD --end YYYY-MM-DD --f0 <factor>")
conn.close()
