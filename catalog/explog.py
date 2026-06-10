"""Enrich raw_measurement rows from AutoSQUID experiment_log.txt ledgers.

Each date-folder's experiment_log.txt is a TSV, one row per acquisition attempt.
We match on the full path (folder/filename) and copy the acquisition's own metadata
onto the row: outcome, n_resets, T_start_K/T_end_K, usable_seconds/usable_points. This gives a second
independent integrity signal (the acquisition's outcome vs our is_surge_spec gate)
plus real start/end temperatures. action_log.txt is intentionally not ingested
(it logs actions, not measurements)."""
import pandas as pd
from pathlib import Path

def parse_experiment_log(path):
    """List of dict rows from an experiment_log.txt (TSV). Empty list if unreadable."""
    try:
        df = pd.read_csv(path, sep="\t")
    except Exception:                                  # noqa: BLE001
        return []
    return df.to_dict("records")

def _num(x):
    try:
        if x is None or x == "" or (isinstance(x, float) and pd.isna(x)):
            return None
        return float(x)
    except (ValueError, TypeError):
        return None

def _int(x):
    n = _num(x)
    return int(n) if n is not None else None

def _usable(r):
    """(usable_seconds, usable_points) from a log row. Prefers the current AutoSQUID columns
    (usable_seconds/usable_points); falls back to the pre-2026-06 ledger (jump_time_s/jump_index),
    which is what every trace acquired so far carries. Legacy no-jump sentinels (jump_index=-1,
    empty jump_time_s) map to NULL."""
    us = _num(r.get("usable_seconds"))
    if us is None:
        js = _num(r.get("jump_time_s"))
        us = js if (js is not None and js > 0) else None
    up = _int(r.get("usable_points"))
    if up is None:
        ji = _int(r.get("jump_index"))
        up = ji if (ji is not None and ji >= 0) else None
    return us, up

def enrich_from_logs(conn, roots):
    """Walk roots for experiment_log.txt; UPDATE matching raw_measurement rows.
    Returns the number of rows updated."""
    updated = 0
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for log in sorted(root.rglob("experiment_log.txt")):
            folder = log.parent
            for r in parse_experiment_log(log):
                fn = r.get("filename")
                if not fn or (isinstance(fn, float) and pd.isna(fn)):
                    continue
                target = str(folder / str(fn))
                usable_seconds, usable_points = _usable(r)
                cur = conn.execute(
                    """UPDATE raw_measurement
                       SET outcome=?, n_resets=?, t_start_K=?, t_end_K=?, usable_seconds=?, usable_points=?
                       WHERE path=?""",
                    (None if (isinstance(r.get("outcome"), float) and pd.isna(r.get("outcome")))
                     else r.get("outcome"),
                     _int(r.get("n_resets")), _num(r.get("T_start_K")),
                     _num(r.get("T_end_K")), usable_seconds, usable_points, target))
                updated += cur.rowcount
        conn.commit()
    return updated
