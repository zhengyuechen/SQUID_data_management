"""Read-only multi-root ingest. Projects each DAQ_*.txt into a raw_measurement row
via AutoSQUID read_daq_file + is_surge_spec. Idempotent on path; incremental via (size, mtime)."""
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from catalog.squid import sq
from catalog.pcs102_meta import parse_daq_filename
from catalog.calibration import resolve_cooldown

_CHUNK = re.compile(r"at chunk (\d+)/(\d+)")

def compute_usable_s(conn):
    """Set usable_s per trace: full duration for CLEAN; the pre-jump prefix for a
    baseline-jump/surge (parsed from the integrity reason's 'at chunk N/nc'); NULL for
    stuck/dead/already-surged. Pure metadata (no file reads). Returns rows updated."""
    n = 0
    for r in conn.execute("SELECT id, integrity_pass, integrity_reason, duration_s, jump_time_s FROM raw_measurement").fetchall():
        dur = r["duration_s"]
        if r["integrity_pass"]:
            usable = dur
        else:
            usable = None
            m = _CHUNK.search(r["integrity_reason"] or "")
            if m and dur:                                   # is_surge_spec located the jump (preferred)
                usable = (int(m.group(1)) / int(m.group(2))) * dur
            elif r["jump_time_s"] is not None and dur and 0 < r["jump_time_s"] < dur:
                usable = r["jump_time_s"]                    # fallback: the acquisition's own jump location
        conn.execute("UPDATE raw_measurement SET usable_s=? WHERE id=?", (usable, r["id"]))
        n += 1
    conn.commit()
    return n

def reresolve_cooldowns(conn):
    """Re-resolve cooldown/calibration for every still-unresolved row from its stored
    acquired_date against the CURRENT cooldown table. Pure metadata (no file reads) — run
    after registering or extending a cooldown. Returns the number newly resolved."""
    cds = [dict(r) for r in conn.execute(
        "SELECT id, label, sample_id, start_date, end_date, f0_per_volt FROM cooldown")]
    by_label = {c["label"]: c for c in cds}
    changed = 0
    for row in conn.execute("SELECT id, acquired_date FROM raw_measurement WHERE cooldown_resolved=0").fetchall():
        label, _ = resolve_cooldown(row["acquired_date"], cds)
        if label is None:
            continue
        c = by_label[label]
        conn.execute("UPDATE raw_measurement SET cooldown_id=?, sample_id=?, cooldown_resolved=1 WHERE id=?",
                     (c["id"], c["sample_id"], row["id"]))
        changed += 1
    conn.commit()
    return changed

def _ids(conn):
    inst = conn.execute("SELECT id FROM instrument WHERE name='PCS102-SQUID'").fetchone()["id"]
    cmap = {r["label"]: r["id"] for r in conn.execute("SELECT id, label FROM cooldown")}
    cool_sample = {r["label"]: r["sample_id"] for r in conn.execute("SELECT label, sample_id FROM cooldown")}
    return inst, cmap, cool_sample

def crawl(conn, roots):
    """Ingest DAQ_*.txt under each root. Returns {'ingested','skipped','failed_parse','unresolved'}."""
    inst_id, cmap, cool_sample = _ids(conn)
    cds = [dict(r) for r in conn.execute(   # cooldowns seeded from the registry; resolve by acquisition date
        "SELECT label, start_date, end_date, f0_per_volt FROM cooldown")]
    stats = {"ingested": 0, "skipped": 0, "failed_parse": 0, "unresolved": 0}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in sorted(root.rglob("DAQ_*.txt")):
            st = path.stat()
            prior = conn.execute("SELECT size_bytes, mtime_ns FROM raw_measurement WHERE path=?",
                                 (str(path),)).fetchone()
            if prior and prior["size_bytes"] == st.st_size and prior["mtime_ns"] == st.st_mtime_ns:
                stats["skipped"] += 1
                continue

            meta = parse_daq_filename(path.name)
            if meta is None:
                stats["failed_parse"] += 1
                print(f"[crawl] UNPARSEABLE FILENAME, skipped: {path}")
                continue

            header, df = sq.read_daq_file(str(path.parent), path.name)
            v = df["CHAN_01(V)"].to_numpy()
            bad, reason = sq.is_surge_spec(v)
            label, _factor = resolve_cooldown(header.get("DATE"), cds)   # cooldown by acquisition date
            if label is None:
                stats["unresolved"] += 1
                print(f"[crawl] UNRESOLVED COOLDOWN (calibration unknown), flagged: {path}")

            dt = float(header["SCANINTVAL"]); n = len(v)
            sidecar = path.parent / path.name.replace("DAQ", "TEMP", 1).replace(".txt", ".csv")
            row = dict(
                instrument_id=inst_id, sample_id=cool_sample.get(label), cooldown_id=cmap.get(label),
                path=str(path), filename=path.name,
                acquired_date=header.get("DATE"), acquired_time=header.get("TIME"),
                temp_mK=meta["temp_mK"], scan_interval_us=meta["scan_interval_us"],
                n_points=n, run_index=meta["run_index"],
                duration_s=n * dt, fs_hz=(1.0 / dt) if dt else None,
                integrity_pass=int(not bad), integrity_reason=reason,
                outcome=meta["outcome"],                            # from filename suffix (enriched later from log)
                n_resets=None, t_start_K=None, t_end_K=None, jump_time_s=None,
                mean_V=float(v.mean()), std_V=float(v.std()),
                temp_sidecar_path=(str(sidecar) if sidecar.exists() else None),
                cooldown_resolved=int(label is not None),
                size_bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                content_hash=hashlib.sha1(v.tobytes()).hexdigest(),
                crawled_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            cols = ", ".join(row); ph = ", ".join("?" for _ in row)
            # On re-ingest, preserve log-enriched fields (don't clobber with NULL from a re-crawl).
            upd = ", ".join(f"{c}=excluded.{c}" for c in row
                            if c not in ("path", "outcome", "n_resets", "t_start_K", "t_end_K", "jump_time_s"))
            upd += (", outcome=COALESCE(excluded.outcome, raw_measurement.outcome)")
            conn.execute(f"INSERT INTO raw_measurement ({cols}) VALUES ({ph}) "
                         f"ON CONFLICT(path) DO UPDATE SET {upd}", list(row.values()))
            stats["ingested"] += 1
        conn.commit()
    return stats
