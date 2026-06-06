# Lab Data-Management Catalog (Provable-Now Slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a rebuildable SQLite *projection catalog* that crawls raw PCS102 SQUID traces from one or more root folders, records their metadata + integrity verdict + per-cooldown calibration, runs analyzers that wrap **AutoSQUID's published plot functions** and emit lineage-tracked derived products, and is driven by a human-editable playbook — proven end-to-end on synthetic fixtures with `SQUID/data/` as the live (initially empty, auto-digesting) root.

**Architecture:** Disk owns the bytes; the DB owns queryable metadata + lineage. A read-only multi-root `crawl()` upserts one `raw_measurement` row per file (idempotent on path + size/mtime), running the integrity gate at ingest. An open/closed `derived_product` table makes a new analysis a new `kind` string, never a schema change. A dispatcher resolves a catalog query, calls the analyzer per clean trace, and records `product_input` lineage both directions. **All SQUID processing goes through the published `AutoSQUID` package** (`read_daq_file`, `is_surge_spec`, `plot_psd`/`plot_run`/`plot_overlay`, `Config`, `save_pcs102`/`save_temp_csv`); the catalog itself owns the per-cooldown calibration map as data.

**Tech Stack:** Python 3, stdlib `sqlite3` + `json` + `hashlib`, `numpy`, `pandas`, `matplotlib` (Agg backend to save figures headlessly), the **`AutoSQUID`** package, `pytest`. No SQUID code is imported from `SQUID/denoising/**`.

---

## Scope & boundaries (read first)

- **In scope:** SQUID-only catalog + crawler + 3 analyzers (wrapping AutoSQUID's plot functions) + dispatcher + playbook + demo, on synthetic fixtures and whatever the user later drops into `SQUID/data/`.
- **Out of scope (YAGNI):** Postgres, a live file-watcher daemon, the LLM layer, XRD/fridge ingest, any change to acquisition. "Auto-digest" here means *idempotent incremental re-crawl* picks up new files — not an always-on watcher.
- **Data boundary (user rule):** `SQUID/denoising/**` is working/derived data, **NOT** a raw-data source — never crawl it, and import **nothing** from it (not the old loader, integrity, or calibration modules). The one canonical raw root is `SQUID/data/`; extra roots may be passed to `crawl()`. As of 2026-06-05 it contains the real **`DAQ-all-interval-for-denoising/`** set (94 × 10 Mpts, ~21 GB): the `4us/20us/100us/500us/` series are the **YbZn sample** (dated 12-22-2025 → 01-04-2026, factor 0.837) and the `bkg/` subfolder is the **Sapphire background** (dated 12-14-2025, factor 0.834). The crawler's recursive `rglob("DAQ_*.txt")` walks all subfolders; this folder is the live proof of auto-digest.
- **Library rule (user, 2026-06-05):** `AutoSQUID` is **published/pip-installed** — import it normally (`from AutoSQUID.* import ...`), do **not** add its source tree to `sys.path`. Use its plot functions (`plot_psd`/`plot_run`/`plot_overlay`) directly as the analyzer artifacts.
- **Environment prerequisite (verified 2026-06-05):** install AutoSQUID once — `pip install -e SQUID/automation/AutoSQUID` — which pulls `pyserial` + `nidaqmx` (both import without hardware). Confirmed working in the anaconda base env (Python 3.10): `import AutoSQUID as sq` succeeds; `sq.read_daq_file` + `sq.is_surge_spec` run on real 10 Mpts traces at ~1.8 s/file. (NumPy 1.x/2.x warnings from `numexpr`/`bottleneck` are a pre-existing env quirk and harmless.)
- **Reconciliations baked in (from the 2026-06-05 readiness verdict):**
  1. The integrity gate is AutoSQUID's **`is_surge_spec(v) -> (bad, reason)`** (the same detector `plot_psd(clean_only=True)` uses). The catalog records `integrity_pass` (1/0) + `integrity_reason` (the string). There is no `JUMP/SURGE/RAIL/BADBASE` taxonomy and no `check_daq_jump` import.
  2. Calibration lives in the catalog **as data**, resolved by the PCS102 header **acquisition `DATE` → cooldown date-range** (not folder name). The real `DAQ-all-interval-for-denoising/` set proves folder-name resolution is insufficient: it mixes the YbZn sample cooldown (12-22→01-04, 0.837) and the Sapphire background cooldown (12-14, 0.834) in one tree, separable only by date. Dates outside every cooldown window are **flagged**, not crashed on.
  3. `temp_mK` comes from the **filename**, never the folder name.
  4. No reliance on `experiment_log.txt` or the denoising `psd_cache_index.csv`; rows are derived from the DAQ files themselves, and validation is by self-consistent success criteria (real-data validation deferred until `SQUID/data/` is populated).

## File Structure

All prototype code lives under `data_management_plan/`. `organize_project.py` only relocates `build_*.py` → `builders/` and LaTeX → `latex/`, so every file below stays where written except the demo builder.

```
data_management_plan/
  conftest.py            # empty — puts data_management_plan/ on sys.path for pytest
  roots.py               # PROJECTS_ROOT + DEFAULT_ROOTS = [<projects>/SQUID/data]
  analysis_playbook.md   # human-editable policy + a fenced ```json core
  catalog/
    __init__.py
    squid.py             # single import point for the PUBLISHED AutoSQUID API
    schema.sql           # the 6 tables + indexes
    db.py                # connect(), init_db(), json helpers
    pcs102_meta.py       # parse_daq_filename(), normalize_temp_mK()
    calibration.py       # resolve_cooldown(path) -> (label, factor); COOLDOWN_SEED (calibration as data)
    seed.py              # seed_lookups(conn): instrument/sample/cooldown rows
    crawl.py             # crawl(conn, roots): read-only multi-root ingest
    analyzers.py         # wrappers over AutoSQUID plot_psd / plot_run / plot_overlay
    registry.py          # REGISTRY: kind -> analyzer
    dispatch.py          # run_analysis(conn, kind, where, params): per-trace map + lineage + caching
    lineage.py           # products_of_raw(), raws_of_product()
    playbook.py          # parse_playbook(md_path) -> dict
  builders/
    build_catalog_demo.py  # generates catalog_demo.ipynb
  tests/
    __init__.py
    _fixtures.py         # synthetic PCS102 corpus (+ temp sidecars) via AutoSQUID writers
    test_squid_smoke.py
    test_pcs102_meta.py
    test_calibration.py
    test_seed.py
    test_crawl.py
    test_analyzers.py
    test_dispatch.py
    test_lineage.py
    test_playbook.py
    test_end_to_end.py
  results/               # derived-product run folders <YYYY-MM-DD>_<HHMMSS>_<desc>/ (created at runtime)
```

Run all tests from `data_management_plan/`: `python -m pytest tests/ -v`.

**Git note:** this workspace has no git (`CLAUDE.md` confirms). The `git commit` steps below are optional checkpoints — either `git init` in `data_management_plan/` first, or skip them.

---

### Task 0: Scaffold + AutoSQUID import point + fixtures

**Files:**
- Create: `data_management_plan/conftest.py`, `data_management_plan/roots.py`
- Create: `data_management_plan/catalog/__init__.py`, `data_management_plan/catalog/squid.py`
- Create: `data_management_plan/tests/__init__.py`, `data_management_plan/tests/_fixtures.py`
- Create: `data_management_plan/tests/test_squid_smoke.py`

- [ ] **Step 1: pytest path shim + package markers**

`conftest.py` (empty file — its presence makes pytest add `data_management_plan/` to `sys.path`):

```python
# Makes `catalog`, `roots`, and `tests` importable when running pytest from data_management_plan/.
```

`catalog/__init__.py`:

```python
"""Lab data-management catalog (provable-now slice)."""
```

`tests/__init__.py`:

```python
```

- [ ] **Step 2: AutoSQUID import point**

`catalog/squid.py` — the single place the catalog imports the **published** AutoSQUID API. Normal package imports, no `sys.path` manipulation.

```python
"""Single import point for the published AutoSQUID package the catalog depends on.

AutoSQUID is pip-installed (do NOT add its source tree to sys.path) and imported
as `sq` per lab convention; use `sq.read_daq_file`, `sq.is_surge_spec`,
`sq.plot_psd`, `sq.Config`, etc. Its package __init__ pulls nidaqmx + pyserial,
which import without hardware. `_psd_welch` is not re-exported at package level,
so it comes from the submodule.

Install once:  pip install -e SQUID/automation/AutoSQUID   (pulls pyserial + nidaqmx)
"""
import AutoSQUID as sq
from AutoSQUID.plotting import _psd_welch

__all__ = ["sq", "_psd_welch"]
```

- [ ] **Step 3: roots**

`roots.py`:

```python
"""Default crawl roots. SQUID/data is the canonical raw root (may be empty; the
crawler auto-digests whatever appears there on the next crawl)."""
from pathlib import Path

PROJECTS_ROOT = Path(__file__).resolve().parents[1]        # .../projects
DEFAULT_ROOTS = [PROJECTS_ROOT / "SQUID" / "data"]
```

- [ ] **Step 4: synthetic-fixture corpus (AutoSQUID writers, with temp sidecars)**

`tests/_fixtures.py`:

```python
"""Synthetic PCS102 corpus for tests, written with AutoSQUID's own writers.

Mirrors the real DAQ-all-interval-for-denoising layout: a `bkg/` subfolder
(background, Sapphire window) and a `sample/` subfolder (YbZn window). Calibration
is resolved by the PCS102 header DATE, so each file's DATE is patched into the
right cooldown window (save_pcs102 stamps 'today', which is in no window).
Each DAQ_*.txt gets a sibling TEMP_*.csv so plot_run / plot_overlay have temperature.
"""
import numpy as np
from pathlib import Path
from catalog.squid import sq

SCAN_INTERVAL_S = 4.0e-6
N = 20_000

def _healthy(seed):
    rng = np.random.default_rng(seed)
    return rng.normal(0.012, 0.002, N).astype(np.float64)

def _railed(seed):
    v = _healthy(seed); v[N // 2:] = 1.0; return v

def set_header_date(daq_path, mdy):
    """Rewrite the PCS102 'DATE=' line to mdy ('MM-DD-YYYY') so date-based calibration resolves."""
    p = Path(daq_path); lines = p.read_text().splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("DATE="):
            lines[i] = f"DATE={mdy}"; break
    p.write_text("\n".join(lines) + "\n")

def _write(folder, name, v, T_K, mdy):
    folder.mkdir(parents=True, exist_ok=True)
    daq = folder / name
    sq.save_pcs102(str(daq), v, SCAN_INTERVAL_S)
    set_header_date(daq, mdy)
    dur = N * SCAN_INTERVAL_S
    temp = folder / name.replace("DAQ", "TEMP", 1).replace(".txt", ".csv")
    sq.save_temp_csv(str(temp), [(0.0, T_K), (dur / 2, T_K), (dur, T_K + 0.001)])
    return daq

def make_corpus(root):
    """Fixture tree: bkg/ = background (Sapphire window 12-14), else = YbZn sample
    (12-22→01-04). Returns {key: daq_path}."""
    spec = [
        ("sample_33mK_clean", "sample", "DAQ_4us_33mK_20000pts_1.txt", _healthy(1), 0.033, "12-23-2025"),
        ("sample_14mK_clean", "sample", "DAQ_4us_14mK_20000pts_1.txt", _healthy(2), 0.014, "12-24-2025"),
        ("sample_33mK_run2",  "sample", "DAQ_4us_33mK_20000pts_2.txt", _healthy(3), 0.033, "12-23-2025"),
        ("sample_33mK_railed","sample", "DAQ_4us_33mK_20000pts_3.txt", _railed(4),  0.033, "12-23-2025"),
        ("bkg_300mK_clean",   "bkg",    "DAQ_4us_300mK_20000pts_1.txt", _healthy(5), 0.300, "12-14-2025"),
    ]
    return {k: _write(root / folder, name, v, T, mdy) for k, folder, name, v, T, mdy in spec}
```

- [ ] **Step 5: smoke test**

`tests/test_squid_smoke.py`:

```python
import numpy as np
from catalog.squid import sq
from tests._fixtures import make_corpus

def test_autosquid_reads_fixture(tmp_path):
    paths = make_corpus(tmp_path / "data")
    daq = paths["sample_33mK_clean"]
    header, df = sq.read_daq_file(str(daq.parent), daq.name)
    assert header["SCANINTVAL"] == 4.0e-6
    assert len(df["CHAN_01(V)"]) == 20_000

def test_integrity_gate_flags_railed(tmp_path):
    paths = make_corpus(tmp_path / "data")
    rail = paths["sample_33mK_railed"]
    header, df = sq.read_daq_file(str(rail.parent), rail.name)
    bad, reason = sq.is_surge_spec(df["CHAN_01(V)"].to_numpy())
    assert bad is True and isinstance(reason, str)
    good = paths["sample_33mK_clean"]
    _, gdf = sq.read_daq_file(str(good.parent), good.name)
    assert sq.is_surge_spec(gdf["CHAN_01(V)"].to_numpy())[0] is False
```

- [ ] **Step 6: run**

Run: `cd "data_management_plan" && python -m pytest tests/test_squid_smoke.py -v`
Expected: PASS (2). If `import AutoSQUID` fails, install `AutoSQUID nidaqmx pyserial` before continuing.

- [ ] **Step 7: commit**

```bash
git add data_management_plan/conftest.py data_management_plan/roots.py \
        data_management_plan/catalog/__init__.py data_management_plan/catalog/squid.py \
        data_management_plan/tests/__init__.py data_management_plan/tests/_fixtures.py \
        data_management_plan/tests/test_squid_smoke.py
git commit -m "feat(catalog): scaffold + published-AutoSQUID import point + PCS102 fixtures"
```

---

### Task 1: Schema + DB init

**Files:**
- Create: `data_management_plan/catalog/schema.sql`, `data_management_plan/catalog/db.py`
- Test: `data_management_plan/tests/test_seed.py` (init portion)

- [ ] **Step 1: schema**

`catalog/schema.sql`:

```sql
-- Projection catalog: disk owns the bytes; these tables own queryable metadata + lineage.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sample (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, formula TEXT, notes TEXT);

CREATE TABLE IF NOT EXISTS instrument (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, kind TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS cooldown (
  id INTEGER PRIMARY KEY,
  sample_id INTEGER REFERENCES sample(id),
  label TEXT UNIQUE NOT NULL,
  fridge TEXT, start_date TEXT, end_date TEXT,
  phi0_per_volt REAL NOT NULL,           -- per-cooldown calibration factor, AS DATA
  s_bias_ma REAL, setup_notes TEXT);

CREATE TABLE IF NOT EXISTS raw_measurement (
  id INTEGER PRIMARY KEY,
  instrument_id INTEGER REFERENCES instrument(id),
  sample_id INTEGER REFERENCES sample(id),
  cooldown_id INTEGER REFERENCES cooldown(id),
  path TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
  acquired_date TEXT, acquired_time TEXT,
  temp_mK REAL,                          -- normalized from the FILENAME (not the folder)
  scan_interval_us REAL, n_points INTEGER, run_index INTEGER,
  duration_s REAL, fs_hz REAL,
  integrity_pass INTEGER NOT NULL,       -- 1/0 from AutoSQUID is_surge_spec
  integrity_reason TEXT,                 -- is_surge_spec's reason string ('ok' or the failure)
  mean_V REAL, std_V REAL,
  temp_sidecar_path TEXT,
  cooldown_resolved INTEGER NOT NULL,    -- 1 if cooldown/calibration resolved from path, else 0
  size_bytes INTEGER, mtime_ns INTEGER, content_hash TEXT, crawled_at TEXT);

CREATE TABLE IF NOT EXISTS derived_product (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,                    -- a NEW analysis is a new value here; no schema change
  params TEXT, scalars TEXT,             -- JSON
  artifact_path TEXT, result_folder TEXT, code_ref TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS product_input (
  derived_product_id INTEGER NOT NULL REFERENCES derived_product(id),
  raw_measurement_id INTEGER NOT NULL REFERENCES raw_measurement(id),
  role TEXT,
  PRIMARY KEY (derived_product_id, raw_measurement_id));

CREATE INDEX IF NOT EXISTS ix_raw_temp      ON raw_measurement(temp_mK);
CREATE INDEX IF NOT EXISTS ix_raw_cooldown  ON raw_measurement(cooldown_id);
CREATE INDEX IF NOT EXISTS ix_raw_integrity ON raw_measurement(integrity_pass);
CREATE INDEX IF NOT EXISTS ix_prod_kind     ON derived_product(kind);
CREATE INDEX IF NOT EXISTS ix_pi_raw        ON product_input(raw_measurement_id);
```

- [ ] **Step 2: db.py**

`catalog/db.py`:

```python
"""SQLite connection + schema application + small JSON helpers."""
import json, sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

def connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(conn):
    conn.executescript(SCHEMA_PATH.read_text()); conn.commit()

def dumps(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

def loads(s):
    return json.loads(s) if s else None
```

- [ ] **Step 3: init tests**

`tests/test_seed.py` (init portion):

```python
from catalog.db import connect, init_db

EXPECTED = {"sample", "instrument", "cooldown", "raw_measurement", "derived_product", "product_input"}

def test_init_db_creates_all_tables(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn)
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert EXPECTED <= names

def test_init_db_is_idempotent(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn); init_db(conn)
    assert conn.execute("SELECT count(*) FROM sample").fetchone()[0] == 0
```

- [ ] **Step 4: run + commit**

Run: `python -m pytest tests/test_seed.py -v` → PASS (2).
```bash
git add data_management_plan/catalog/schema.sql data_management_plan/catalog/db.py data_management_plan/tests/test_seed.py
git commit -m "feat(catalog): 6-table projection schema (integrity_pass + reason) + DB init"
```

---

### Task 2: Filename grammar + temperature normalization

**Files:**
- Create: `data_management_plan/catalog/pcs102_meta.py`
- Test: `data_management_plan/tests/test_pcs102_meta.py`

Grammar (CLAUDE.md): `DAQ_<interval>_<temperature>_<npts>_<run>.txt`. Interval `us`|`ms`; npts may carry `k`/`M`; run index optional; temperature uses `p` for the decimal. Unparseable names return `None` (surfaced, never guessed).

- [ ] **Step 1: failing tests**

`tests/test_pcs102_meta.py`:

```python
import pytest
from catalog.pcs102_meta import parse_daq_filename, normalize_temp_mK

@pytest.mark.parametrize("name,iv,tmK,npts,run", [
    ("DAQ_4us_33mK_2Mpts_1.txt",      4.0,    33.0,   2_000_000, 1),
    ("DAQ_100us_38mK_50000pts_2.txt", 100.0,  38.0,   50_000,    2),
    ("DAQ_500us_1p2K_10Mpts_1.txt",   500.0,  1200.0, 10_000_000,1),
    ("DAQ_10ms_14mK_1000pts.txt",     10_000.0, 14.0, 1000,      None),
    ("DAQ_20us_5p5K_100kpts_3.txt",   20.0,   5500.0, 100_000,   3),
])
def test_parse(name, iv, tmK, npts, run):
    m = parse_daq_filename(name)
    assert (m["scan_interval_us"], m["temp_mK"], m["n_points"], m["run_index"]) == (iv, tmK, npts, run)

def test_parse_rejects_garbage():
    assert parse_daq_filename("notes.txt") is None
    assert parse_daq_filename("DAQ_weird.txt") is None

@pytest.mark.parametrize("tok,mK", [("33mK",33.0),("300mK",300.0),("1p2K",1200.0),("5p5K",5500.0),("1K",1000.0)])
def test_normalize_temp(tok, mK):
    assert normalize_temp_mK(tok) == mK
```

- [ ] **Step 2: run → FAIL (module not found).**

- [ ] **Step 3: implement**

`catalog/pcs102_meta.py`:

```python
"""Parse the DAQ filename grammar and normalize temperature to milli-kelvin.
Returns None on anything that does not match (the crawler surfaces these)."""
import re

_INTERVAL_US = {"us": 1.0, "ms": 1000.0}
_NPTS_MULT = {"": 1, "k": 1_000, "M": 1_000_000}

_FN = re.compile(
    r"^DAQ_(?P<ival>\d+(?:\.\d+)?)(?P<iunit>us|ms)"
    r"_(?P<temp>\d+(?:p\d+)?(?:mK|K)[A-Za-z]*)"
    r"_(?P<npts>\d+)(?P<nmult>[kM]?)pts"
    r"(?:_(?P<run>\d+))?\.txt$")

def normalize_temp_mK(tok):
    m = re.match(r"^(?P<num>\d+(?:p\d+)?)(?P<unit>mK|K)", tok)
    if not m:
        return None
    val = float(m["num"].replace("p", "."))
    return val if m["unit"] == "mK" else val * 1000.0

def parse_daq_filename(name):
    m = _FN.match(name)
    if not m:
        return None
    temp_mK = normalize_temp_mK(m["temp"])
    if temp_mK is None:
        return None
    return {"scan_interval_us": float(m["ival"]) * _INTERVAL_US[m["iunit"]],
            "temp_mK": temp_mK,
            "n_points": int(m["npts"]) * _NPTS_MULT[m["nmult"]],
            "run_index": int(m["run"]) if m["run"] else None}
```

- [ ] **Step 4: run → PASS; commit**

```bash
git add data_management_plan/catalog/pcs102_meta.py data_management_plan/tests/test_pcs102_meta.py
git commit -m "feat(catalog): DAQ filename grammar + filename-derived temperature"
```

---

### Task 3: Cooldown/calibration resolution (owned by the catalog, as data)

**Files:**
- Create: `data_management_plan/catalog/calibration.py`
- Test: `data_management_plan/tests/test_calibration.py`

The calibration map is the catalog's own data (values documented in CLAUDE.md), not imported from `denoising/`. Cooldown is resolved by the PCS102 header **acquisition `DATE` → cooldown date-range**, because the real `DAQ-all-interval-for-denoising/` set mixes two cooldowns in one tree (only the date separates the YbZn sample from the Sapphire background). Dates in no window return `(None, None)` so the crawler can flag them. The two December windows do not overlap, so date resolution is unambiguous.

- [ ] **Step 1: failing tests**

`tests/test_calibration.py`:

```python
from catalog.calibration import resolve_cooldown, COOLDOWN_SEED, CALIBRATION_FO_PER_V

def test_resolves_by_acquisition_date():
    # sample series (12-22 -> 01-04) -> YbZn; bkg (12-14) -> Sapphire
    assert resolve_cooldown("12-23-2025") == ("YbZn2GaO5_Dec2025", 0.837)
    assert resolve_cooldown("01-04-2026") == ("YbZn2GaO5_Dec2025", 0.837)
    assert resolve_cooldown("12-14-2025") == ("Sapphire_Dec2025", 0.834)

def test_date_outside_all_windows_is_flagged():
    assert resolve_cooldown("06-05-2026") == (None, None)
    assert resolve_cooldown(None) == (None, None)

def test_seed_factor_matches_map():
    for row in COOLDOWN_SEED:
        assert row["phi0_per_volt"] == CALIBRATION_FO_PER_V[row["label"]]
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement**

`catalog/calibration.py`:

```python
"""Per-cooldown Phi_0/V calibration, owned by the catalog as DATA (values from
CLAUDE.md). Cooldown is resolved by the PCS102 header acquisition DATE against
each cooldown's date range — robust to folder layout (the real all-interval set
mixes the YbZn sample and Sapphire background cooldowns in one tree)."""

CALIBRATION_FO_PER_V = {
    "YbZn2GaO5_Dec2025": 0.837,
    "Sapphire_Dec2025":  0.834,
    "Sapphire_May2026":  0.762,
}

# Cooldown lookup-table seed; date ranges (ISO) + S-bias documented in CLAUDE.md / the lab PPTs.
COOLDOWN_SEED = [
    {"label": "YbZn2GaO5_Dec2025", "sample": "YbZn2GaO5",           "formula": "YbZn2GaO5",
     "fridge": "dilution", "start_date": "2025-12-22", "end_date": "2026-01-04",
     "phi0_per_volt": CALIBRATION_FO_PER_V["YbZn2GaO5_Dec2025"], "s_bias_ma": 0.0747},
    {"label": "Sapphire_Dec2025",  "sample": "Sapphire-background", "formula": "Al2O3",
     "fridge": "dilution", "start_date": "2025-12-08", "end_date": "2025-12-14",
     "phi0_per_volt": CALIBRATION_FO_PER_V["Sapphire_Dec2025"], "s_bias_ma": 0.0752},
    {"label": "Sapphire_May2026",  "sample": "Sapphire-background", "formula": "Al2O3",
     "fridge": "dilution", "start_date": "2026-05-18", "end_date": "2026-05-19",
     "phi0_per_volt": CALIBRATION_FO_PER_V["Sapphire_May2026"], "s_bias_ma": 0.0654},
]

def _iso(mdy):
    "PCS102 header DATE 'MM-DD-YYYY' -> 'YYYY-MM-DD' (lexically comparable to the ISO ranges)."
    m, d, y = mdy.split("-")
    return f"{y}-{m}-{d}"

def resolve_cooldown(header_date, cooldowns=COOLDOWN_SEED):
    """(label, factor) for a PCS102 header DATE ('MM-DD-YYYY'); (None, None) if the date
    falls in no cooldown window. `cooldowns`: dicts/rows with start_date, end_date (ISO),
    label, phi0_per_volt — pass DB rows to stay in sync with the seeded table."""
    try:
        d = _iso(header_date)
    except (ValueError, AttributeError, TypeError):
        return None, None
    for c in cooldowns:
        if c["start_date"] <= d <= c["end_date"]:
            return c["label"], c["phi0_per_volt"]
    return None, None
```

- [ ] **Step 4: run → PASS; commit**

```bash
git add data_management_plan/catalog/calibration.py data_management_plan/tests/test_calibration.py
git commit -m "feat(catalog): catalog-owned calibration resolved by header DATE -> cooldown window"
```

---

### Task 4: Seed the lookup tables

**Files:**
- Create: `data_management_plan/catalog/seed.py`
- Modify: `data_management_plan/tests/test_seed.py` (append seed-row tests)

- [ ] **Step 1: failing tests** (append to `tests/test_seed.py`)

```python
from catalog.seed import seed_lookups
from catalog.db import connect, init_db

def test_seed_populates_cooldowns(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn); seed_lookups(conn)
    rows = {r["label"]: r["phi0_per_volt"] for r in conn.execute("SELECT label, phi0_per_volt FROM cooldown")}
    assert rows == {"YbZn2GaO5_Dec2025": 0.837, "Sapphire_Dec2025": 0.834, "Sapphire_May2026": 0.762}
    r = conn.execute("""SELECT s.name FROM cooldown c JOIN sample s ON s.id=c.sample_id
                        WHERE c.label='YbZn2GaO5_Dec2025'""").fetchone()
    assert r["name"] == "YbZn2GaO5"

def test_seed_idempotent(tmp_path):
    conn = connect(tmp_path / "t.sqlite"); init_db(conn); seed_lookups(conn); seed_lookups(conn)
    assert conn.execute("SELECT count(*) FROM cooldown").fetchone()[0] == 3
    assert conn.execute("SELECT count(*) FROM instrument WHERE name='PCS102-SQUID'").fetchone()[0] == 1
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement**

`catalog/seed.py`:

```python
"""Bootstrap the lookup tables once (instrument, samples, cooldowns-with-calibration).
Idempotent via INSERT OR IGNORE on the UNIQUE name/label columns."""
from catalog.calibration import COOLDOWN_SEED

def seed_lookups(conn):
    conn.execute("INSERT OR IGNORE INTO instrument(name, kind) VALUES (?,?)", ("PCS102-SQUID", "squid"))
    for row in COOLDOWN_SEED:
        conn.execute("INSERT OR IGNORE INTO sample(name, formula) VALUES (?,?)", (row["sample"], row["formula"]))
    for row in COOLDOWN_SEED:
        sid = conn.execute("SELECT id FROM sample WHERE name=?", (row["sample"],)).fetchone()["id"]
        conn.execute("""INSERT OR IGNORE INTO cooldown
                        (sample_id,label,fridge,start_date,end_date,phi0_per_volt,s_bias_ma)
                        VALUES (?,?,?,?,?,?,?)""",
                     (sid, row["label"], row["fridge"], row["start_date"],
                      row["end_date"], row["phi0_per_volt"], row["s_bias_ma"]))
    conn.commit()
```

- [ ] **Step 4: run → PASS; commit**

```bash
git add data_management_plan/catalog/seed.py data_management_plan/tests/test_seed.py
git commit -m "feat(catalog): seed instrument/sample/cooldown (calibration as data)"
```

---

### Task 5: Read-only multi-root crawler (AutoSQUID reader + integrity gate)

**Files:**
- Create: `data_management_plan/catalog/crawl.py`
- Test: `data_management_plan/tests/test_crawl.py`

Walks every root for `DAQ_*.txt`, reads each once via AutoSQUID `read_daq_file`, runs `is_surge_spec`, computes cheap scalars, resolves the cooldown, and UPSERTs one row keyed on `path`. Incremental: unchanged `(size, mtime_ns)` is skipped without re-reading. Read-only on raw data.

- [ ] **Step 1: failing tests**

`tests/test_crawl.py`:

```python
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from tests._fixtures import make_corpus

def _db(tmp_path):
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn); return conn

def test_ingests_all(tmp_path):
    root = tmp_path / "data"; make_corpus(root)
    conn = _db(tmp_path); s = crawl(conn, [root])
    assert s["ingested"] == 5
    assert conn.execute("SELECT count(*) FROM raw_measurement").fetchone()[0] == 5

def test_integrity_recorded(tmp_path):
    root = tmp_path / "data"; p = make_corpus(root)
    conn = _db(tmp_path); crawl(conn, [root])
    rail = conn.execute("SELECT integrity_pass, integrity_reason FROM raw_measurement WHERE filename=?",
                        (p["sample_33mK_railed"].name,)).fetchone()
    assert rail["integrity_pass"] == 0 and rail["integrity_reason"] != "ok"
    clean = conn.execute("SELECT integrity_pass FROM raw_measurement WHERE filename=?",
                         (p["sample_33mK_clean"].name,)).fetchone()
    assert clean["integrity_pass"] == 1

def test_calibration_and_temp(tmp_path):
    root = tmp_path / "data"; make_corpus(root)
    conn = _db(tmp_path); crawl(conn, [root])
    row = conn.execute("""SELECT r.temp_mK, r.cooldown_resolved, c.phi0_per_volt, c.label, r.temp_sidecar_path
                          FROM raw_measurement r JOIN cooldown c ON c.id=r.cooldown_id
                          WHERE r.filename='DAQ_4us_14mK_20000pts_1.txt'""").fetchone()
    assert row["temp_mK"] == 14.0 and row["phi0_per_volt"] == 0.837
    assert row["label"] == "YbZn2GaO5_Dec2025" and row["cooldown_resolved"] == 1
    assert row["temp_sidecar_path"] is not None
    bkg = conn.execute("""SELECT c.phi0_per_volt FROM raw_measurement r JOIN cooldown c ON c.id=r.cooldown_id
                          WHERE r.filename='DAQ_4us_300mK_20000pts_1.txt'""").fetchone()
    assert bkg["phi0_per_volt"] == 0.834

def test_idempotent(tmp_path):
    root = tmp_path / "data"; make_corpus(root)
    conn = _db(tmp_path); crawl(conn, [root]); s2 = crawl(conn, [root])
    assert s2["ingested"] == 0 and s2["skipped"] == 5

def test_empty_root_graceful(tmp_path):
    (tmp_path / "data").mkdir()
    conn = _db(tmp_path); assert crawl(conn, [tmp_path / "data"])["ingested"] == 0
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement**

`catalog/crawl.py`:

```python
"""Read-only multi-root ingest. Projects each DAQ_*.txt into a raw_measurement row
via AutoSQUID read_daq_file + is_surge_spec. Idempotent on path; incremental via (size, mtime)."""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from catalog.squid import sq
from catalog.pcs102_meta import parse_daq_filename
from catalog.calibration import resolve_cooldown

def _ids(conn):
    inst = conn.execute("SELECT id FROM instrument WHERE name='PCS102-SQUID'").fetchone()["id"]
    cmap = {r["label"]: r["id"] for r in conn.execute("SELECT id, label FROM cooldown")}
    cool_sample = {r["label"]: r["sample_id"] for r in conn.execute("SELECT label, sample_id FROM cooldown")}
    return inst, cmap, cool_sample

def crawl(conn, roots):
    """Ingest DAQ_*.txt under each root. Returns {'ingested','skipped','failed_parse','unresolved'}."""
    inst_id, cmap, cool_sample = _ids(conn)
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
            label, _factor = resolve_cooldown(header.get("DATE"))   # cooldown by acquisition date
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
                mean_V=float(v.mean()), std_V=float(v.std()),
                temp_sidecar_path=(str(sidecar) if sidecar.exists() else None),
                cooldown_resolved=int(label is not None),
                size_bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                content_hash=hashlib.sha1(v.tobytes()).hexdigest(),
                crawled_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            cols = ", ".join(row); ph = ", ".join("?" for _ in row)
            upd = ", ".join(f"{c}=excluded.{c}" for c in row if c != "path")
            conn.execute(f"INSERT INTO raw_measurement ({cols}) VALUES ({ph}) "
                         f"ON CONFLICT(path) DO UPDATE SET {upd}", list(row.values()))
            stats["ingested"] += 1
        conn.commit()
    return stats
```

- [ ] **Step 4: run → PASS (6); commit**

```bash
git add data_management_plan/catalog/crawl.py data_management_plan/tests/test_crawl.py
git commit -m "feat(catalog): read-only multi-root crawler (AutoSQUID reader + is_surge_spec gate)"
```

---

### Task 6: Analyzers wrapping AutoSQUID's plot functions

**Files:**
- Create: `data_management_plan/catalog/analyzers.py`, `data_management_plan/catalog/registry.py`
- Test: `data_management_plan/tests/test_analyzers.py`

Each analyzer is per-trace: `run(row, factor, params, outdir) -> (artifact_path, scalars)`. The figure is produced by AutoSQUID's plot function (`plot_psd`/`plot_run`/`plot_overlay`) under the Agg backend (where `plt.show()` is a no-op that leaves the figure open), then captured and saved. Scalars are computed from the same data via AutoSQUID helpers.

- [ ] **Step 1: failing tests**

`tests/test_analyzers.py`:

```python
from pathlib import Path
from catalog.registry import REGISTRY
from tests._fixtures import make_corpus

def _row(daq, sidecar=None):
    return {"path": str(daq), "filename": daq.name,
            "temp_sidecar_path": (str(sidecar) if sidecar else
                                  str(daq.parent / daq.name.replace("DAQ","TEMP",1).replace(".txt",".csv")))}

def test_psd_wraps_plot_psd(tmp_path):
    p = make_corpus(tmp_path / "data"); out = tmp_path / "out"; out.mkdir()
    art, sc = REGISTRY["psd"](_row(p["sample_33mK_clean"]), 0.837, {"P": [10, 100]}, out)
    assert Path(art).exists() and art.endswith(".png")
    assert sc["conversion"] == 0.837 and sc["white_level"] > 0

def test_time_series_wraps_plot_run(tmp_path):
    p = make_corpus(tmp_path / "data"); out = tmp_path / "out"; out.mkdir()
    art, sc = REGISTRY["time_series"](_row(p["sample_33mK_clean"]), 0.837, {}, out)
    assert Path(art).exists() and art.endswith(".png")
    assert abs(sc["mean_V"] - 0.012) < 0.003 and sc["duration_s"] > 0

def test_volt_temp_overlay_wraps_plot_overlay(tmp_path):
    p = make_corpus(tmp_path / "data"); out = tmp_path / "out"; out.mkdir()
    art, sc = REGISTRY["volt_temp_overlay"](_row(p["sample_33mK_clean"]), 0.837, {}, out)
    assert Path(art).exists() and art.endswith(".png")
    assert sc["n_temp_samples"] == 3
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement analyzers**

`catalog/analyzers.py`:

```python
"""Analyzers: per-trace wrappers over AutoSQUID's plot functions. Under the Agg
backend plt.show() is a no-op and leaves the figure open, so we call the plot
function then capture + save the current figure(s)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

from catalog.squid import sq, _psd_welch

def _save_current(stem):
    fig = plt.gcf(); path = f"{stem}.png"; fig.savefig(path, dpi=110); plt.close("all"); return path

def psd(row, factor, params, outdir):
    """Welch PSD figure via sq.plot_psd; scalars via _psd_welch (largest P)."""
    folder, fn = str(Path(row["path"]).parent), row["filename"]
    P = tuple(params.get("P", [10, 100, 1000])); window = params.get("window", "hanning")
    plt.close("all")
    sq.plot_psd(folder, fn, conversion=factor, P=P, window=window, clean_only=True)
    art = _save_current(str(outdir / f"psd_{fn[:-4]}"))
    header, df = sq.read_daq_file(folder, fn)
    f, S = _psd_welch(df["CHAN_01(V)"].to_numpy() * factor, float(header["SCANINTVAL"]), P[-1], window)
    band = (f > 1) & (f < 10)
    white = float(np.median(S[band])) if band.any() else float(np.median(S[1:]))
    return art, {"P": list(P), "window": window, "conversion": factor, "white_level": white}

def time_series(row, factor, params, outdir):
    """Voltage-vs-time (+ temperature) figure via sq.plot_run on a minimal sq.Config."""
    folder = Path(row["path"]).parent; fn = row["filename"]
    cfg = sq.Config(data_root=str(folder.parent), user=folder.name, date="")
    plt.close("all")
    sq.plot_run(cfg, filename_list=[fn])
    arts = []
    for i, num in enumerate(plt.get_fignums()):
        p = str(outdir / f"run_{fn[:-4]}_{i}.png"); plt.figure(num).savefig(p, dpi=110); arts.append(p)
    plt.close("all")
    header, df = sq.read_daq_file(str(folder), fn); v = df["CHAN_01(V)"].to_numpy(); dt = float(header["SCANINTVAL"])
    return arts[0], {"mean_V": float(v.mean()), "std_V": float(v.std()),
                     "duration_s": float(len(v) * dt), "n_figs": len(arts)}

def volt_temp_overlay(row, factor, params, outdir):
    """Voltage + interpolated temperature on a shared time axis via sq.plot_overlay."""
    sidecar = row.get("temp_sidecar_path")
    if not sidecar or not Path(sidecar).exists():
        raise ValueError(f"no temp sidecar for {row['filename']}")
    folder, fn = str(Path(row["path"]).parent), row["filename"]
    header, df = sq.read_daq_file(folder, fn); dt = float(header["SCANINTVAL"])
    v = df["CHAN_01(V)"].to_numpy(); t = (df.index.to_numpy() - 1) * dt
    tdf = pd.read_csv(sidecar)
    plt.close("all")
    sq.plot_overlay(t, v, tdf["time_s"].to_numpy(), tdf["T_K"].to_numpy(), title=fn)
    art = _save_current(str(outdir / f"overlay_{fn[:-4]}"))
    return art, {"n_temp_samples": int(len(tdf)), "T_mean_K": float(tdf["T_K"].mean())}
```

- [ ] **Step 4: implement registry**

`catalog/registry.py`:

```python
"""kind -> analyzer. Each analyzer: run(row, factor, params, outdir) -> (artifact_path, scalars)."""
from catalog import analyzers

REGISTRY, CODE_REF = {}, {}

def register(kind, fn, code_ref):
    REGISTRY[kind] = fn; CODE_REF[kind] = code_ref

register("psd",              analyzers.psd,              "plot_psd@AutoSQUID")
register("time_series",      analyzers.time_series,      "plot_run@AutoSQUID")
register("volt_temp_overlay",analyzers.volt_temp_overlay,"plot_overlay@AutoSQUID")
```

- [ ] **Step 5: run → PASS (3); commit**

```bash
git add data_management_plan/catalog/analyzers.py data_management_plan/catalog/registry.py data_management_plan/tests/test_analyzers.py
git commit -m "feat(catalog): analyzers wrapping AutoSQUID plot_psd/plot_run/plot_overlay"
```

---

### Task 7: Dispatcher (per-trace map → run → lineage, with caching)

**Files:**
- Create: `data_management_plan/catalog/dispatch.py`
- Test: `data_management_plan/tests/test_dispatch.py`

`run_analysis` resolves a query (always filtered to `integrity_pass=1`), and for **each** clean trace pulls its calibration factor, runs the analyzer once, and records one `derived_product` + one `product_input` (role `primary`). Returns the list of product ids. Caching: a product with the same `(kind, raw_id, params)` is reused, not recomputed.

- [ ] **Step 1: failing tests**

`tests/test_dispatch.py`:

```python
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from catalog.dispatch import run_analysis
from tests._fixtures import make_corpus

def _ready(tmp_path):
    make_corpus(tmp_path / "data")
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn)
    crawl(conn, [tmp_path / "data"]); return conn

def test_one_product_per_clean_trace(tmp_path):
    conn = _ready(tmp_path)
    pids = run_analysis(conn, "psd", "temp_mK = 33", {"P": [10]},
                        results_root=tmp_path / "r", stamp="2026-06-05_120000")
    assert len(pids) == 2          # two CLEAN 33 mK traces (railed one excluded)
    links = conn.execute("SELECT count(*) FROM product_input").fetchone()[0]
    assert links == 2

def test_excludes_failed(tmp_path):
    conn = _ready(tmp_path)
    got = conn.execute("SELECT count(*) FROM raw_measurement WHERE temp_mK=33 AND integrity_pass=1").fetchone()[0]
    assert got == 2                # confirms the railed trace is not eligible

def test_caches(tmp_path):
    conn = _ready(tmp_path)
    a = run_analysis(conn, "psd", "temp_mK = 14", {"P": [10]}, results_root=tmp_path / "r", stamp="2026-06-05_120100")
    b = run_analysis(conn, "psd", "temp_mK = 14", {"P": [10]}, results_root=tmp_path / "r", stamp="2026-06-05_120200")
    assert a == b
    assert conn.execute("SELECT count(*) FROM derived_product").fetchone()[0] == 1
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement**

`catalog/dispatch.py`:

```python
"""Resolve a catalog query to clean traces, run an analyzer per trace, record the
derived products + lineage. Caches on (kind, raw_id, params)."""
from pathlib import Path
from catalog.db import dumps
from catalog.registry import REGISTRY, CODE_REF

def _select_clean(conn, where):
    sql = "SELECT * FROM raw_measurement WHERE integrity_pass=1"
    if where:
        sql += f" AND ({where})"
    return [dict(r) for r in conn.execute(sql + " ORDER BY temp_mK, run_index")]

def _factor(conn, cooldown_id):
    r = conn.execute("SELECT phi0_per_volt FROM cooldown WHERE id=?", (cooldown_id,)).fetchone()
    return r["phi0_per_volt"] if r else 1.0

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
```

- [ ] **Step 4: run → PASS (3); commit**

```bash
git add data_management_plan/catalog/dispatch.py data_management_plan/tests/test_dispatch.py
git commit -m "feat(catalog): per-trace dispatcher with lineage recording + caching"
```

---

### Task 8: Lineage round-trip helpers

**Files:**
- Create: `data_management_plan/catalog/lineage.py`
- Test: `data_management_plan/tests/test_lineage.py`

- [ ] **Step 1: failing tests**

`tests/test_lineage.py`:

```python
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from catalog.dispatch import run_analysis
from catalog.lineage import products_of_raw, raws_of_product
from tests._fixtures import make_corpus

def _ready(tmp_path):
    make_corpus(tmp_path / "data")
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn)
    crawl(conn, [tmp_path / "data"]); return conn

def test_round_trips(tmp_path):
    conn = _ready(tmp_path)
    pid = run_analysis(conn, "psd", "temp_mK = 14", {"P": [10]}, results_root=tmp_path / "r", stamp="s1")[0]
    raws = raws_of_product(conn, pid)
    assert len(raws) == 1 and raws[0]["filename"] == "DAQ_4us_14mK_20000pts_1.txt"
    # same raw, a second analysis -> raw -> {psd, time_series}
    run_analysis(conn, "time_series", "temp_mK = 14", {}, results_root=tmp_path / "r", stamp="s2")
    kinds = {p["kind"] for p in products_of_raw(conn, raws[0]["id"])}
    assert {"psd", "time_series"} <= kinds
```

- [ ] **Step 2: run → FAIL.**

- [ ] **Step 3: implement**

`catalog/lineage.py`:

```python
"""Lineage queries — the product_input link is traversable both directions."""

def raws_of_product(conn, product_id):
    return [dict(r) for r in conn.execute(
        """SELECT r.*, pi.role FROM raw_measurement r JOIN product_input pi ON pi.raw_measurement_id=r.id
           WHERE pi.derived_product_id=? ORDER BY r.temp_mK, r.run_index""", (product_id,))]

def products_of_raw(conn, raw_id):
    return [dict(r) for r in conn.execute(
        """SELECT d.*, pi.role FROM derived_product d JOIN product_input pi ON pi.derived_product_id=d.id
           WHERE pi.raw_measurement_id=? ORDER BY d.created_at""", (raw_id,))]
```

- [ ] **Step 4: run → PASS; commit**

```bash
git add data_management_plan/catalog/lineage.py data_management_plan/tests/test_lineage.py
git commit -m "feat(catalog): bidirectional lineage helpers"
```

---

### Task 9: The analysis playbook

**Files:**
- Create: `data_management_plan/analysis_playbook.md`, `data_management_plan/catalog/playbook.py`
- Test: `data_management_plan/tests/test_playbook.py`

Human prose wrapping a machine-readable core — a fenced ```json block the dispatcher parses deterministically.

- [ ] **Step 1: playbook**

`analysis_playbook.md`:

````markdown
# Analysis Playbook

Policy for what the catalog runs. Edit the JSON block below; the dispatcher reads it.
The prose is for humans (and, later, the LLM); the JSON is the machine-readable core.

## SQUID traces
- Every CLEAN trace → time-series plot (plot_run) + Welch PSD (plot_psd) + voltage/temperature overlay (plot_overlay).
- Report band-integrated power for each band in `bands`.
- Skip any trace that fails the integrity gate (enforced at ingest; dispatch also filters on integrity_pass=1).

## How to change things
- Add a band → add a `[lo, hi]` pair to `bands`.
- Change Welch resolution → edit `welch_P`.
- Widen/narrow temperature grouping → edit `temp_group_tol_mK`.

```json
{
  "welch_P": [10, 100, 1000],
  "window": "hanning",
  "temp_group_tol_mK": 10,
  "bands": [[0.1, 1], [1, 10], [10, 100]],
  "skip_failed": true
}
```
````

- [ ] **Step 2: failing tests**

`tests/test_playbook.py`:

```python
from pathlib import Path
from catalog.playbook import parse_playbook

PB = Path(__file__).resolve().parents[1] / "analysis_playbook.md"

def test_core():
    pol = parse_playbook(PB)
    assert pol["welch_P"] == [10, 100, 1000] and pol["temp_group_tol_mK"] == 10
    assert [1, 10] in pol["bands"] and pol["skip_failed"] is True

def test_added_band(tmp_path):
    md = tmp_path / "pb.md"
    md.write_text('x\n```json\n{"welch_P":[10],"window":"hanning","temp_group_tol_mK":5,'
                  '"bands":[[1,10],[100,1000]],"skip_failed":true}\n```\n')
    assert [100, 1000] in parse_playbook(md)["bands"]
```

- [ ] **Step 3: run → FAIL.**

- [ ] **Step 4: implement**

`catalog/playbook.py`:

```python
"""Parse the machine-readable core (a fenced ```json block) out of the playbook Markdown."""
import json, re
from pathlib import Path

_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

def parse_playbook(md_path):
    m = _JSON_BLOCK.search(Path(md_path).read_text())
    if not m:
        raise ValueError(f"no ```json policy block in {md_path}")
    return json.loads(m.group(1))
```

- [ ] **Step 5: run → PASS; commit**

```bash
git add data_management_plan/analysis_playbook.md data_management_plan/catalog/playbook.py data_management_plan/tests/test_playbook.py
git commit -m "feat(catalog): human-editable analysis playbook + JSON-core parser"
```

---

### Task 10: End-to-end success-criteria gate + demo builder

**Files:**
- Create: `data_management_plan/tests/test_end_to_end.py`
- Create: `data_management_plan/builders/build_catalog_demo.py`

- [ ] **Step 1: the success-criteria gate**

`tests/test_end_to_end.py`:

```python
from pathlib import Path
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl
from catalog.dispatch import run_analysis
from catalog.lineage import raws_of_product, products_of_raw
from catalog.playbook import parse_playbook
from tests._fixtures import make_corpus, _healthy, SCAN_INTERVAL_S, set_header_date
from catalog.squid import sq

PB = Path(__file__).resolve().parents[1] / "analysis_playbook.md"

def test_full_pipeline(tmp_path):
    data_root = tmp_path / "data"; make_corpus(data_root)
    conn = connect(tmp_path / "cat.sqlite"); init_db(conn); seed_lookups(conn)

    # (1) idempotent crawl
    assert crawl(conn, [data_root])["ingested"] == 5
    assert crawl(conn, [data_root])["ingested"] == 0

    # (2) temperature query returns exactly the expected clean traces
    assert conn.execute("SELECT count(*) FROM raw_measurement WHERE temp_mK=14 AND integrity_pass=1").fetchone()[0] == 1

    # (3) dispatch honors the playbook policy (welch_P from the file), via AutoSQUID plot_psd
    pol = parse_playbook(PB)
    pid = run_analysis(conn, "psd", "temp_mK = 14", {"P": [pol["welch_P"][0]], "window": pol["window"]},
                       results_root=tmp_path / "r", stamp="2026-06-05_140000")[0]
    assert Path([d["artifact_path"] for d in [dict(conn.execute(
        "SELECT artifact_path FROM derived_product WHERE id=?", (pid,)).fetchone())]][0]).exists()

    # (4) lineage round-trips both directions
    raws = raws_of_product(conn, pid); assert len(raws) == 1
    assert pid in [p["id"] for p in products_of_raw(conn, raws[0]["id"])]

    # (5) playbook edit (bump P) -> new product, zero code change
    pid2 = run_analysis(conn, "psd", "temp_mK = 14", {"P": [100], "window": pol["window"]},
                        results_root=tmp_path / "r", stamp="2026-06-05_140100")[0]
    assert pid2 != pid and conn.execute("SELECT count(*) FROM derived_product").fetchone()[0] == 2

    # (6) auto-digest: drop a new file (dated into a cooldown window), re-crawl, it appears
    newp = data_root / "sample" / "DAQ_4us_50mK_20000pts_1.txt"
    sq.save_pcs102(str(newp), _healthy(99), SCAN_INTERVAL_S); set_header_date(newp, "12-26-2025")
    assert crawl(conn, [data_root])["ingested"] == 1
    row = conn.execute("""SELECT c.phi0_per_volt FROM raw_measurement r JOIN cooldown c ON c.id=r.cooldown_id
                          WHERE r.temp_mK=50""").fetchone()
    assert row is not None and row["phi0_per_volt"] == 0.837   # resolved via 12-26 date
```

- [ ] **Step 2: run → PASS** (fix the offending module, not the test, if anything fails).

Run: `python -m pytest tests/ -v` (the whole suite).

- [ ] **Step 3: demo builder**

`builders/build_catalog_demo.py`:

```python
"""Generate catalog_demo.ipynb — the step-by-step proof. Crawls SQUID/data (the live
root, may be empty) plus a synthetic demo root so it shows something today.
Run: python builders/build_catalog_demo.py"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "catalog_demo.ipynb"

def md(s):   return {"cell_type": "markdown", "metadata": {}, "source": s}
def code(s): return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s}

CELLS = [
    md("# Catalog demo — provable-now slice\nCrawls `SQUID/data` (live root, may be empty) + a synthetic demo root. All SQUID processing via the published AutoSQUID package."),
    code("import sys; sys.path.insert(0, '.')\n"
         "from pathlib import Path\n"
         "import tempfile\n"
         "from catalog.db import connect, init_db\n"
         "from catalog.seed import seed_lookups\n"
         "from catalog.crawl import crawl\n"
         "from catalog.dispatch import run_analysis\n"
         "from catalog.lineage import raws_of_product, products_of_raw\n"
         "from catalog.playbook import parse_playbook\n"
         "from roots import DEFAULT_ROOTS\n"
         "from tests._fixtures import make_corpus"),
    md("## 1. Crawl a synthetic demo root (fast). SQUID/data holds the real ~21 GB set — opt in at the end."),
    code("demo_root = Path(tempfile.mkdtemp()) / 'demo_data'; make_corpus(demo_root)\n"
         "conn = connect(':memory:'); init_db(conn); seed_lookups(conn)\n"
         "print('crawl:', crawl(conn, [demo_root]))\n"
         "for r in conn.execute('SELECT filename, temp_mK, integrity_pass, integrity_reason FROM raw_measurement ORDER BY temp_mK'):\n"
         "    print(dict(r))"),
    md("## 2. Query: all ~14 mK traces that passed integrity"),
    code("print([dict(r) for r in conn.execute('SELECT filename,temp_mK FROM raw_measurement WHERE temp_mK BETWEEN 13 AND 15 AND integrity_pass=1')])"),
    md("## 3. Dispatch PSD (plot_psd) + time-series (plot_run), policy from the playbook"),
    code("pol = parse_playbook('analysis_playbook.md')\n"
         "psd_ids = run_analysis(conn, 'psd', 'temp_mK BETWEEN 13 AND 15', {'P': pol['welch_P'], 'window': pol['window']}, results_root='results', stamp='demo')\n"
         "ts_ids  = run_analysis(conn, 'time_series', 'temp_mK BETWEEN 13 AND 15', {}, results_root='results', stamp='demo')\n"
         "print('psd products', psd_ids, 'time_series products', ts_ids)"),
    md("## 4. Lineage both ways"),
    code("raws = raws_of_product(conn, psd_ids[0]); print('figure -> raw:', [r['filename'] for r in raws])\n"
         "print('raw -> figures:', [p['kind'] for p in products_of_raw(conn, raws[0]['id'])])"),
    md("## 5. Edit the playbook (bump P) and re-dispatch — no code change"),
    code("more = run_analysis(conn, 'psd', 'temp_mK BETWEEN 13 AND 15', {'P':[5000],'window':pol['window']}, results_root='results', stamp='demo2')\n"
         "print('new products', more)"),
    md("## 6. (Optional) Crawl the REAL SQUID/data set — ~94 files / ~21 GB, a few minutes; uncomment to run"),
    code("# conn2 = connect(':memory:'); init_db(conn2); seed_lookups(conn2)\n"
         "# print('real crawl:', crawl(conn2, DEFAULT_ROOTS))\n"
         "# print(conn2.execute('SELECT c.label, count(*) n FROM raw_measurement r JOIN cooldown c ON c.id=r.cooldown_id GROUP BY c.label').fetchall())\n"
         "# -> expect YbZn2GaO5_Dec2025 (interval folders, 0.837) + Sapphire_Dec2025 (bkg/, 0.834)"),
]

OUT.write_text(json.dumps({"cells": CELLS, "metadata": {"language_info": {"name": "python"}},
                           "nbformat": 4, "nbformat_minor": 5}, indent=1))
print("wrote", OUT)
```

- [ ] **Step 4: generate + organize + commit**

```bash
cd "data_management_plan"
python builders/build_catalog_demo.py
python -m pytest tests/ -v                                  # full suite green
cd ..
python organize_project.py data_management_plan --apply      # confirms build_*.py lives in builders/
git add data_management_plan/builders/build_catalog_demo.py data_management_plan/catalog_demo.ipynb data_management_plan/tests/test_end_to_end.py
git commit -m "feat(catalog): end-to-end success-criteria gate + AutoSQUID demo notebook"
```

- [ ] **Step 5: project-root report**

Write `data_management_plan/2026-06-05_catalog-prototype_report.md` (durable narrative): what was built, the success criteria that passed (idempotent crawl, clean-only query, AutoSQUID-backed dispatch, lineage round-trip, playbook re-dispatch, auto-digest), the synthetic-fixture caveat, and a link to this plan. Commit it.

---

## Self-Review

**Spec coverage** — schema §4 → Task 1; crawler §5 → Tasks 2–5; registry/dispatcher §6 → Tasks 6–7; playbook §6 → Task 9; lineage → Task 8; "prove it now" §8 + success criteria → Task 10. Multi-root + auto-digest → Task 5 + Task 10 step (6). The four reconciliations → Task 5 (`is_surge_spec` gate, integrity_pass+reason), Task 3 (catalog-owned calibration, resolved by header `DATE`→cooldown window — validated against the real `DAQ-all-interval-for-denoising/` set, which mixes two cooldowns in one tree), Task 2 (filename temp), Task 10 (self-consistent validation; no `experiment_log.txt`/`psd_cache`).

**User updates applied** — (a) **no `denoising/` imports**: the loader → AutoSQUID `read_daq_file`, the integrity gate → AutoSQUID `is_surge_spec`, calibration → catalog-owned `calibration.py`; (b) **AutoSQUID's plot functions used directly** as the three analyzers (`plot_psd`/`plot_run`/`plot_overlay`); (c) **AutoSQUID imported as a published package** via `catalog/squid.py`, no `sys.path` bridge.

**Deferred (called out, not silently dropped)** — many-raws→one-product lineage (a single overlay over a temperature group) is not produced by AutoSQUID's per-trace plot functions; the schema supports it and a future group analyzer can add it. Real-data validation (incl. the lab's `PSD_*Seg.txt` cross-check) is deferred until `SQUID/data/` is populated → a future Task 11.

**Type consistency** — analyzer contract `run(row, factor, params, outdir) -> (artifact_path, scalars)` is identical across `analyzers.py`, `registry.py`, `dispatch.py`; `resolve_cooldown` returns `(label, factor)` everywhere; `run_analysis` returns a list of product ids (per-trace), reflected in every test; `crawl` returns `{ingested, skipped, failed_parse, unresolved}` used consistently.

**No placeholders** — every step ships runnable code or an exact command + expected result.
```
