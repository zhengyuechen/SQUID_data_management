"""SQLite connection + schema application + small JSON helpers."""
import json
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

def connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(conn):
    conn.executescript(SCHEMA_PATH.read_text())
    # migrate older DBs that predate newer columns / names (no-op on fresh DBs)
    for table, col in [("cooldown", "logbook_path TEXT"), ("raw_measurement", "usable_s REAL")]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass   # column already exists
    try:
        conn.execute("ALTER TABLE cooldown RENAME COLUMN phi0_per_volt TO f0_per_volt")
    except sqlite3.OperationalError:
        pass   # already renamed (or fresh DB)
    conn.commit()

def dumps(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
