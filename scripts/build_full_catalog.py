"""Build the FULL persistent catalog.sqlite over all of SQUID/data, then report
exact contents. Idempotent + incremental: re-run after dropping in new folders."""
import sys; sys.path.insert(0, ".")
import time
from pathlib import Path
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl, reresolve_cooldowns, compute_usable_s
from catalog.explog import enrich_from_logs
from catalog.cooldown_log import load_logbooks, write_calibration_md
from roots import DEFAULT_ROOTS, PROJECTS_ROOT

DB = Path("catalog.sqlite")
conn = connect(DB); init_db(conn); seed_lookups(conn)   # seed UPSERTs cooldowns (picks up edited date ranges)

t0 = time.time()
stats = crawl(conn, DEFAULT_ROOTS)
enriched = enrich_from_logs(conn, DEFAULT_ROOTS)
reresolved = reresolve_cooldowns(conn)                   # resolve any now-registered cooldowns, no re-read
compute_usable_s(conn)                                   # usable (pre-jump) duration per trace
logbooks = load_logbooks(conn)                           # index cooldowns/*.md setup + notes
write_calibration_md()                                   # regenerate cooldowns/_calibration.md (human-readable)
dt = time.time() - t0

on_disk = sum(1 for _ in (PROJECTS_ROOT / "SQUID" / "data").rglob("DAQ_*.txt"))
print(f"=== built {DB.resolve()} ({DB.stat().st_size/1024:.0f} KB) in {dt:.0f}s ===")
print(f"crawl: {stats}   log-enriched: {enriched}   newly calibration-resolved: {reresolved}   logbooks indexed: {logbooks}")
print(f"DAQ_*.txt on disk under SQUID/data: {on_disk}   |   rows in catalog: "
      f"{conn.execute('SELECT count(*) FROM raw_measurement').fetchone()[0]}")

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
conn.close()
