"""Resolve a catalog query to clean traces, run an analyzer per trace, record the
derived products + lineage. Caches on (kind, raw_id, params)."""
from pathlib import Path
from catalog.db import dumps
from catalog.registry import REGISTRY, CODE_REF, GROUP_REGISTRY, GROUP_CODE_REF

def _select(conn, where, include_partial=False, include_all=False, limit=None):
    # include_all: ANY trace (for diagnostic raw inspection, incl. frozen/failed).
    # include_partial: clean (usable_s = full) PLUS jump/surge (usable_s = prefix).
    # default: clean only (integrity_pass=1).
    cond = "1" if include_all else ("usable_s IS NOT NULL" if include_partial else "integrity_pass=1")
    sql = f"SELECT * FROM raw_measurement WHERE {cond}"
    if where:
        sql += f" AND ({where})"
    sql += " ORDER BY temp_mK, run_index"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(sql)]

def _select_clean(conn, where):
    return _select(conn, where, include_partial=False)

def _factor(conn, cooldown_id):
    r = conn.execute("SELECT f0_per_volt FROM cooldown WHERE id=?", (cooldown_id,)).fetchone()
    return r["f0_per_volt"] if r else 1.0

def _cached(conn, kind, raw_id, params_json):
    r = conn.execute("""SELECT d.id FROM derived_product d JOIN product_input pi ON pi.derived_product_id=d.id
                        WHERE d.kind=? AND d.params=? AND pi.raw_measurement_id=?""",
                     (kind, params_json, raw_id)).fetchone()
    return r["id"] if r else None

def run_analysis(conn, kind, where, params, results_root, stamp):
    """Run `kind` over every clean trace matching `where`. Returns [product_id, ...]."""
    if kind not in REGISTRY:
        raise KeyError(f"unknown analyzer kind {kind!r}; registered: {sorted(REGISTRY)}")
    rows = _select_clean(conn, where)
    if not rows:
        raise ValueError(f"no clean traces match WHERE ({where})")
    params_json = dumps(params)
    outdir = Path(results_root) / f"{stamp}_{kind.replace('_', '-')}"
    outdir.mkdir(parents=True, exist_ok=True)
    pids = []
    for r in rows:
        hit = _cached(conn, kind, r["id"], params_json)
        if hit is not None:
            pids.append(hit); continue
        artifact, scalars = REGISTRY[kind](r, _factor(conn, r["cooldown_id"]), params, outdir)
        cur = conn.execute(
            """INSERT INTO derived_product (kind,params,scalars,artifact_path,result_folder,code_ref,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (kind, params_json, dumps(scalars), artifact, str(outdir), CODE_REF[kind], stamp))
        pid = cur.lastrowid
        conn.execute("INSERT INTO product_input (derived_product_id,raw_measurement_id,role) VALUES (?,?,?)",
                     (pid, r["id"], "primary"))
        pids.append(pid)
    conn.commit()
    return pids

def _group_cached(conn, kind, raw_ids, params_json):
    want = tuple(sorted(raw_ids))
    for d in conn.execute("SELECT id FROM derived_product WHERE kind=? AND params=?", (kind, params_json)):
        got = tuple(sorted(x["raw_measurement_id"] for x in conn.execute(
            "SELECT raw_measurement_id FROM product_input WHERE derived_product_id=?", (d["id"],))))
        if got == want:
            return d["id"]
    return None

def run_group_analysis(conn, kind, where, params, results_root, stamp,
                       include_partial=False, include_all=False, limit=None):
    """Run a GROUP analyzer ONCE over the traces matching `where` -> one product with many
    product_input links (role 'overlay_member'). Returns the product id. include_partial=True
    adds jump/surge traces (truncated to usable_s); include_all=True selects ANY trace
    (diagnostic, e.g. frozen ones); limit caps how many."""
    if kind not in GROUP_REGISTRY:
        raise KeyError(f"unknown group analyzer {kind!r}; registered: {sorted(GROUP_REGISTRY)}")
    rows = _select(conn, where, include_partial, include_all, limit)
    if not rows:
        raise ValueError(f"no clean traces match WHERE ({where})")
    raw_ids = [r["id"] for r in rows]
    params_json = dumps(params)
    hit = _group_cached(conn, kind, raw_ids, params_json)
    if hit is not None:
        return hit
    outdir = Path(results_root) / f"{stamp}_{kind.replace('_', '-')}"
    outdir.mkdir(parents=True, exist_ok=True)
    inputs = [(r, _factor(conn, r["cooldown_id"])) for r in rows]
    artifact, scalars = GROUP_REGISTRY[kind](inputs, params, outdir)
    cur = conn.execute(
        """INSERT INTO derived_product (kind,params,scalars,artifact_path,result_folder,code_ref,created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (kind, params_json, dumps(scalars), artifact, str(outdir), GROUP_CODE_REF[kind], stamp))
    pid = cur.lastrowid
    for rid in raw_ids:
        conn.execute("INSERT INTO product_input (derived_product_id,raw_measurement_id,role) VALUES (?,?,?)",
                     (pid, rid, "overlay_member"))
    conn.commit()
    return pid
