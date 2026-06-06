# Bench-PC Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the catalog bench-deployable — copy `data_management_plan/` to the bench PC as a shared engine, run Claude Code inside each `…\<user>\` folder, with calibration stored in a human-editable markdown registry (not Python) and all paths derived from the user folder.

**Architecture:** Three surgical changes to the existing package, all tested locally first: (1) calibration moves from `COOLDOWN_SEED` in `calibration.py` to a loader of `cooldowns/<label>.md` frontmatter; (2) a `config.py` derives roots/db/output/figures from the cwd (the user folder), overridable by a `_catalog/config.json`; (3) a single `python -m catalog` CLI (build/plot/show/cooldown/init) plus generic data-root `CLAUDE.md`/`README.md`. Cooldown registry is always the engine's own `cooldowns/` (one global source, shared by all users).

**Tech Stack:** Python 3.10 (anaconda), stdlib only for new code (`json`, `re`, `argparse`, `pathlib` — no `tomllib`/`yaml` deps), `pytest`, the existing `catalog` package + AutoSQUID.

**Git note:** this workspace has no git. The `git commit` steps are optional checkpoints — `git init` first or skip them.

**Run tests from** `data_management_plan/`: `python -m pytest tests/ -q` (currently 55 passing — keep them green).

---

## File Structure
- `catalog/calibration.py` — *modify*: replace hardcoded `COOLDOWN_SEED` with `parse_cooldown_md()` + `load_registry()`; `COOLDOWN_SEED`/`CALIBRATION_FO_PER_V` become loaded from `cooldowns/`.
- `cooldowns/<label>.md` (×3) — *modify*: prepend a `---` frontmatter header with the machine-readable calibration fields.
- `catalog/config.py` — *create*: `load_config(start)` → roots/db/output/figures (cwd-derived; `_catalog/config.json` overrides). Cooldowns dir is the engine's own.
- `catalog/__main__.py` — *create*: the `python -m catalog build|plot|show|cooldown|init` CLI (thin wrappers over existing logic).
- `catalog/bench_docs.py` — *create*: the generic data-root `CLAUDE.md` + `README.md` text + `write_root_docs()`.
- `_catalog/config.json` — *create (local)*: points local runs at `../SQUID/data` so nothing local breaks.
- `tests/test_registry.py`, `tests/test_config.py`, `tests/test_cli.py` — *create*: cover the new pieces.
- `build_full_catalog.py`, `catplot.py`, `coollog.py` — *modify*: read paths from `config` instead of the hardcoded `roots.py`/`"catalog.sqlite"`.

---

### Task 1: Cooldown markdown becomes the calibration source

**Files:**
- Modify: `cooldowns/YbZn2GaO5_Dec2025.md`, `cooldowns/Sapphire_Dec2025.md`, `cooldowns/Sapphire_May2026.md`
- Modify: `catalog/calibration.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Add frontmatter to the three logbooks**

Prepend this block to `cooldowns/YbZn2GaO5_Dec2025.md` (above its `# Cooldown logbook …` line):
```
---
label: YbZn2GaO5_Dec2025
sample: YbZn2GaO5
formula: YbZn2GaO5
fridge: dilution
start_date: 2025-12-22
end_date: 2026-01-04
f0_per_volt: 0.837
s_bias_ma: 0.0747
---
```
`cooldowns/Sapphire_Dec2025.md`:
```
---
label: Sapphire_Dec2025
sample: Sapphire-background
formula: Al2O3
fridge: dilution
start_date: 2025-12-08
end_date: 2025-12-14
f0_per_volt: 0.834
s_bias_ma: 0.0752
---
```
`cooldowns/Sapphire_May2026.md`:
```
---
label: Sapphire_May2026
sample: Sapphire-background
formula: Al2O3
fridge: dilution
start_date: 2026-05-18
end_date: 2026-06-30
f0_per_volt: 0.762
s_bias_ma: 0.0654
---
```

- [ ] **Step 2: Write the failing test**

`tests/test_registry.py`:
```python
from pathlib import Path
from catalog.calibration import parse_cooldown_md, load_registry, COOLDOWN_SEED, resolve_cooldown

REG = Path(__file__).resolve().parents[1] / "cooldowns"

def test_parse_cooldown_md():
    c = parse_cooldown_md(REG / "YbZn2GaO5_Dec2025.md")
    assert c["label"] == "YbZn2GaO5_Dec2025" and c["sample"] == "YbZn2GaO5"
    assert c["start_date"] == "2025-12-22" and c["end_date"] == "2026-01-04"
    assert c["f0_per_volt"] == 0.837 and c["s_bias_ma"] == 0.0747

def test_load_registry_finds_all_three():
    reg = load_registry(REG)
    labels = {c["label"]: c["f0_per_volt"] for c in reg}
    assert labels == {"YbZn2GaO5_Dec2025": 0.837, "Sapphire_Dec2025": 0.834, "Sapphire_May2026": 0.762}

def test_default_seed_loaded_from_registry_and_resolves():
    assert len(COOLDOWN_SEED) == 3
    assert resolve_cooldown("12-23-2025") == ("YbZn2GaO5_Dec2025", 0.837)
    assert resolve_cooldown("06-05-2026") == ("Sapphire_May2026", 0.762)
```

- [ ] **Step 3: Run it — FAIL** (`parse_cooldown_md`/`load_registry` not defined)

Run: `python -m pytest tests/test_registry.py -q` → FAIL (ImportError).

- [ ] **Step 4: Implement the loader in `catalog/calibration.py`**

Replace the whole file with:
```python
"""Per-cooldown f0/V calibration, sourced from the markdown registry (cooldowns/<label>.md
frontmatter) — NOT hardcoded in Python. Cooldown is resolved by the PCS102 header
acquisition DATE against each cooldown's date range."""
import re
from pathlib import Path

DEFAULT_COOLDOWNS_DIR = Path(__file__).resolve().parents[1] / "cooldowns"
_FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)

def parse_cooldown_md(path):
    """Parse the YAML-ish frontmatter of a cooldowns/<label>.md file -> dict, or None."""
    m = _FM.match(Path(path).read_text())
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    if "label" not in fm or "f0_per_volt" not in fm:
        return None
    return {"label": fm["label"], "sample": fm.get("sample"), "formula": fm.get("formula"),
            "fridge": fm.get("fridge"), "start_date": fm["start_date"], "end_date": fm["end_date"],
            "f0_per_volt": float(fm["f0_per_volt"]),
            "s_bias_ma": float(fm["s_bias_ma"]) if fm.get("s_bias_ma") else None}

def load_registry(cooldowns_dir=DEFAULT_COOLDOWNS_DIR):
    """Every cooldowns/<label>.md (skipping _-prefixed reference files) -> list of cooldown dicts."""
    out = []
    d = Path(cooldowns_dir)
    if not d.exists():
        return out
    for md in sorted(d.glob("*.md")):
        if md.name.startswith("_"):
            continue
        c = parse_cooldown_md(md)
        if c:
            out.append(c)
    return out

COOLDOWN_SEED = load_registry()
CALIBRATION_FO_PER_V = {c["label"]: c["f0_per_volt"] for c in COOLDOWN_SEED}

def _iso(mdy):
    m, d, y = mdy.split("-")
    return f"{y}-{m}-{d}"

def resolve_cooldown(header_date, cooldowns=None):
    """(label, factor) for a PCS102 header DATE ('MM-DD-YYYY'); (None, None) if in no window."""
    cooldowns = COOLDOWN_SEED if cooldowns is None else cooldowns
    try:
        dd = _iso(header_date)
    except (ValueError, AttributeError, TypeError):
        return None, None
    for c in cooldowns:
        if c["start_date"] <= dd <= c["end_date"]:
            return c["label"], c["f0_per_volt"]
    return None, None
```

- [ ] **Step 5: Run the full suite** — `python -m pytest tests/ -q`
Expected: PASS. (`seed.py`, `crawl.py`, `cooldown_log.write_calibration_md` all consume `COOLDOWN_SEED`/`resolve_cooldown`, whose shapes are unchanged — only the source moved. `resolve_cooldown`'s default arg changed from `COOLDOWN_SEED` to `None`-then-`COOLDOWN_SEED`; behavior identical.)

- [ ] **Step 6: Commit**
```bash
git add catalog/calibration.py cooldowns/*.md tests/test_registry.py
git commit -m "feat(catalog): calibration sourced from cooldowns/ markdown registry, not Python"
```

---

### Task 2: Config-driven paths

**Files:**
- Create: `catalog/config.py`
- Create: `_catalog/config.json` (local override so nothing local breaks)
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import json
from pathlib import Path
from catalog.config import load_config

def test_cwd_derived_defaults(tmp_path):
    cfg = load_config(tmp_path)                       # no config.json -> derive from the folder
    assert cfg["raw_roots"] == [str(tmp_path)]
    assert cfg["db"] == str(tmp_path / "_catalog" / "catalog.sqlite")
    assert cfg["output"] == str(tmp_path / "_catalog" / "output")
    assert cfg["figures"] == str(tmp_path / "_catalog" / "figures")

def test_config_json_overrides(tmp_path):
    (tmp_path / "_catalog").mkdir()
    (tmp_path / "_catalog" / "config.json").write_text(json.dumps(
        {"raw_roots": ["X/raw"], "db": "X/cat.sqlite", "output": "X/out", "figures": "X/fig"}))
    cfg = load_config(tmp_path)
    assert cfg["raw_roots"] == ["X/raw"] and cfg["db"] == "X/cat.sqlite"
```

- [ ] **Step 2: Run it — FAIL** (`catalog.config` missing).
Run: `python -m pytest tests/test_config.py -q` → FAIL.

- [ ] **Step 3: Implement `catalog/config.py`**
```python
"""Resolve catalog paths from where Claude is run (the user folder). A `_catalog/config.json`
overrides; otherwise everything derives from the start dir. Cooldowns are always the engine's
own registry (the global, shared source) — see catalog.calibration.DEFAULT_COOLDOWNS_DIR."""
import json
import os
from pathlib import Path

def load_config(start=None):
    """Return {'raw_roots': [str], 'db': str, 'output': str, 'figures': str}."""
    start = Path(start or os.getcwd())
    cfg_file = start / "_catalog" / "config.json"
    if cfg_file.exists():
        d = json.loads(cfg_file.read_text())
        return {"raw_roots": list(d["raw_roots"]), "db": d["db"],
                "output": d["output"], "figures": d["figures"]}
    cat = start / "_catalog"
    return {"raw_roots": [str(start)], "db": str(cat / "catalog.sqlite"),
            "output": str(cat / "output"), "figures": str(cat / "figures")}
```

- [ ] **Step 4: Run — PASS** (`python -m pytest tests/test_config.py -q`).

- [ ] **Step 5: Local override so existing local layout is unchanged**

Create `_catalog/config.json` (paths relative to `data_management_plan/`, the local run dir):
```json
{
  "raw_roots": ["../SQUID/data"],
  "db": "catalog.sqlite",
  "output": "output",
  "figures": "figures"
}
```

- [ ] **Step 6: Commit**
```bash
git add catalog/config.py _catalog/config.json tests/test_config.py
git commit -m "feat(catalog): config-driven paths (cwd-derived, _catalog/config.json override)"
```

---

### Task 3: One `python -m catalog` CLI

**Files:**
- Create: `catalog/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test** (drives `build` over a synthetic root, end-to-end)

`tests/test_cli.py`:
```python
import json, subprocess, sys
from pathlib import Path
from tests._fixtures import make_corpus

def _user_folder(tmp_path):
    make_corpus(tmp_path / "run")                      # raw under the user folder
    cat = tmp_path / "_catalog"; cat.mkdir()
    (cat / "config.json").write_text(json.dumps(
        {"raw_roots": [str(tmp_path / "run")], "db": str(cat / "c.sqlite"),
         "output": str(cat / "output"), "figures": str(cat / "figures")}))
    return tmp_path

def test_cli_build(tmp_path):
    folder = _user_folder(tmp_path)
    r = subprocess.run([sys.executable, "-m", "catalog", "build"], cwd=str(folder),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (folder / "_catalog" / "c.sqlite").exists()
    import sqlite3
    n = sqlite3.connect(folder / "_catalog" / "c.sqlite").execute(
        "SELECT count(*) FROM raw_measurement").fetchone()[0]
    assert n == 5
```
(The subprocess inherits this repo's `sys.path` because `catalog` is importable from `data_management_plan/`; run the test from there.)

- [ ] **Step 2: Run it — FAIL** (no `catalog.__main__`).
Run: `python -m pytest tests/test_cli.py -q` → FAIL.

- [ ] **Step 3: Implement `catalog/__main__.py`**
```python
"""Single entry point: `python -m catalog <command>` run from a user folder.
  build              crawl raw_roots -> catalog.sqlite (+ enrich, usable_s, load registry)
  plot <kind> …      dispatch a figure (forwards flags to the dispatch layer)
  show <label>       print a cooldown's setup + notes
  cooldown <label> --phase <p> "<note>"   append a logbook note
  init               scaffold this folder's _catalog/ (config.json + reminder)
"""
import sys
from pathlib import Path
from catalog.config import load_config
from catalog.db import connect, init_db
from catalog.seed import seed_lookups
from catalog.crawl import crawl, reresolve_cooldowns, compute_usable_s
from catalog.explog import enrich_from_logs
from catalog.cooldown_log import load_logbooks, write_calibration_md, render, append_note

def _open(cfg):
    Path(cfg["db"]).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg["db"]); init_db(conn); seed_lookups(conn)
    return conn

def cmd_build(cfg, argv):
    conn = _open(cfg)
    roots = [Path(r) for r in cfg["raw_roots"]]
    stats = crawl(conn, roots)
    enriched = enrich_from_logs(conn, roots)
    reresolve_cooldowns(conn); compute_usable_s(conn); load_logbooks(conn); write_calibration_md()
    print(f"build: {stats}  enriched={enriched}  db={cfg['db']}")

def cmd_show(cfg, argv):
    conn = _open(cfg); print(render(conn, argv[0]))

def cmd_cooldown(cfg, argv):
    # cooldown <label> --phase <p> "<note>"
    label = argv[0]; phase = "run"; rest = argv[1:]
    if "--phase" in rest:
        i = rest.index("--phase"); phase = rest[i + 1]; rest = rest[:i] + rest[i + 2:]
    note = rest[0]
    md = append_note(label, phase, note); conn = _open(cfg); load_logbooks(conn)
    print(f"noted [{phase}] -> {md}")

def cmd_init(cfg, argv):
    cat = Path(load_config()["db"]).parent; cat.mkdir(parents=True, exist_ok=True)
    cfgfile = cat / "config.json"
    if not cfgfile.exists():
        import json
        start = cat.parent
        cfgfile.write_text(json.dumps({"raw_roots": [str(start)], "db": str(cat / "catalog.sqlite"),
                                       "output": str(cat / "output"), "figures": str(cat / "figures")}, indent=2))
    print(f"initialized {cat}  (edit {cfgfile} if your raw data is in subfolders)")

def cmd_plot(cfg, argv):
    # Defer to the existing catplot module, injecting the per-user db + figures dir.
    import catplot
    sys.argv = ["catplot"] + argv + ["--db", cfg["db"]]
    catplot.FIGURES_ROOT = cfg["figures"]               # see Task 3 Step 5
    catplot.main()

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    argv = sys.argv[2:]
    cfg = load_config()
    {"build": cmd_build, "show": cmd_show, "cooldown": cmd_cooldown,
     "init": cmd_init, "plot": cmd_plot}.get(cmd, cmd_build)(cfg, argv)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Make `catplot.py` honor a configurable figures dir**

In `catplot.py`, add near the top (after imports): `FIGURES_ROOT = "figures"`. Change the two `run_group_analysis(... results_root="figures" ...)` and the `run_analysis(... results_root="figures" ...)` calls to `results_root=FIGURES_ROOT`. (So `python -m catalog plot` can point figures at `<user>/_catalog/figures`.)

- [ ] **Step 5: Run — PASS** (`python -m pytest tests/test_cli.py -q`), then the full suite (`python -m pytest tests/ -q`).

- [ ] **Step 6: Commit**
```bash
git add catalog/__main__.py catplot.py tests/test_cli.py
git commit -m "feat(catalog): single `python -m catalog` CLI (build/plot/show/cooldown/init)"
```

---

### Task 4: Data-root docs (one CLAUDE.md + one README) + `init-root`

**Files:**
- Create: `catalog/bench_docs.py`
- Modify: `catalog/__main__.py` (add `init-root`)
- Test: `tests/test_bench_docs.py`

- [ ] **Step 1: Write the failing test**

`tests/test_bench_docs.py`:
```python
from catalog.bench_docs import write_root_docs

def test_write_root_docs(tmp_path):
    paths = write_root_docs(tmp_path)
    cm = (tmp_path / "CLAUDE.md").read_text()
    assert "user folder" in cm and "python -m catalog build" in cm
    assert (tmp_path / "README.md").exists()
    assert set(p.name for p in paths) == {"CLAUDE.md", "README.md"}
```

- [ ] **Step 2: Run it — FAIL.**
Run: `python -m pytest tests/test_bench_docs.py -q` → FAIL.

- [ ] **Step 3: Implement `catalog/bench_docs.py`**
```python
"""The ONE CLAUDE.md + README placed at the data root (F:\\Dilution Refrigerator Data\\),
read by any Claude session opened inside a <user>\\ subfolder."""
from pathlib import Path

CLAUDE_MD = """# CLAUDE.md — Dilution Fridge Data Catalog

You are operating inside a **user folder** (the one you opened). That folder is the identity:
- Raw DAQ data = this folder (and its subfolders).
- Your catalog DB + outputs = `.\\_catalog\\` (catalog.sqlite, output\\, figures\\).
- Calibration = the **shared** cooldown registry in `..\\_engine\\cooldowns\\` (markdown, one file per cooldown). Never edit calibration in Python.

Commands (run from this user folder):
- `python -m catalog build`  — index this folder's raw DAQ into `_catalog\\catalog.sqlite`.
- `python -m catalog plot psd_overlay --temp 50 --cooldown <label>` — make + index a figure.
- `python -m catalog show <label>` — a cooldown's setup + notes.
- `python -m catalog cooldown <label> --phase run "note"` — log a note.

Register/extend a cooldown = add or edit `..\\_engine\\cooldowns\\<label>.md` (frontmatter:
label/sample/start_date/end_date/f0_per_volt/s_bias_ma), then `build`. No code.

Conventions: figures -> `_catalog\\figures\\`; narrative markdown -> `_catalog\\output\\`;
every markdown doc leads with a short `## Essentials` then the full detail.
"""

README_MD = """# Dilution Fridge Data Catalog — quick start

1. Open a terminal **inside your user folder** (e.g. `F:\\Dilution Refrigerator Data\\<you>\\`).
2. `python -m catalog build`  — indexes your DAQ data into `_catalog\\catalog.sqlite`.
3. Plot: `python -m catalog plot psd_overlay --temp 50 --cooldown <label>`.
4. New cooldown? Add `..\\_engine\\cooldowns\\<label>.md` (copy an existing one, edit the
   frontmatter numbers) and run `build` again.

Calibration lives in `_engine\\cooldowns\\` as plain markdown — readable and editable by hand.
"""

def write_root_docs(data_root):
    data_root = Path(data_root); data_root.mkdir(parents=True, exist_ok=True)
    cm = data_root / "CLAUDE.md"; rm = data_root / "README.md"
    cm.write_text(CLAUDE_MD); rm.write_text(README_MD)
    return [cm, rm]
```

- [ ] **Step 4: Add `init-root` to `catalog/__main__.py`**

In `main()`'s command dict add `"init-root": cmd_init_root`, and define:
```python
def cmd_init_root(cfg, argv):
    from catalog.bench_docs import write_root_docs
    target = Path(argv[0]) if argv else Path.cwd().parent      # default: parent of this user folder
    for p in write_root_docs(target):
        print("wrote", p)
```

- [ ] **Step 5: Run — PASS** (`python -m pytest tests/test_bench_docs.py -q`), then full suite.

- [ ] **Step 6: Commit**
```bash
git add catalog/bench_docs.py catalog/__main__.py tests/test_bench_docs.py
git commit -m "feat(catalog): generic data-root CLAUDE.md + README + init-root"
```

---

### Task 5: Point the existing build/plot scripts at config + local validation

**Files:**
- Modify: `build_full_catalog.py`, `coollog.py`
- (No new tests — validated by running against the real local data.)

- [ ] **Step 1: Make `build_full_catalog.py` use config**

Replace its hardcoded `DB = Path("catalog.sqlite")` and `DEFAULT_ROOTS` usage with:
```python
from catalog.config import load_config
_cfg = load_config()
DB = Path(_cfg["db"])
ROOTS = [Path(r) for r in _cfg["raw_roots"]]
```
and change `crawl(conn, DEFAULT_ROOTS)` / `enrich_from_logs(conn, DEFAULT_ROOTS)` to use `ROOTS`. (Local `_catalog/config.json` from Task 2 points `ROOTS` at `../SQUID/data` and `DB` at `catalog.sqlite`, so behavior is unchanged locally.)

- [ ] **Step 2: Make `coollog.py` use the configured db**

Change `ap.add_argument("--db", default="catalog.sqlite")` to default from config:
```python
from catalog.config import load_config
ap.add_argument("--db", default=load_config()["db"])
```

- [ ] **Step 3: Full local validation**

Run, from `data_management_plan/`:
```bash
python -m pytest tests/ -q                      # all green (now incl. registry/config/cli/docs tests)
rm -f catalog.sqlite && python build_full_catalog.py   # rebuilds 225 traces, calibration from the registry
python -m catalog show YbZn2GaO5_Dec2025         # prints setup + notes
```
Expected: tests pass; build reports 225 rows across the 3 cooldowns (f0 = 0.837/0.834/0.762, now loaded from `cooldowns/*.md`); `show` prints the logbook.

- [ ] **Step 4: Commit**
```bash
git add build_full_catalog.py coollog.py
git commit -m "feat(catalog): build/plot/coollog read paths from config"
```

- [ ] **Step 5: Write the deployment note**

Create `output/2026-06-06_bench-deployment_report.md` (Essentials-first): the copy steps (`data_management_plan\` → `F:\Dilution Refrigerator Data\_engine\`; `pip install -e _engine`; `python -m catalog init-root F:\Dilution Refrigerator Data`; per user: open Claude in `<user>\`, `python -m catalog build`), that calibration is edited in `_engine\cooldowns\*.md`, and the local-vs-bench config difference. Commit it.

---

## Self-Review

**Spec coverage:** registry-sourced calibration → Task 1; config-driven paths → Task 2; one CLI → Task 3; one CLAUDE.md + README + `init` → Tasks 3–4; install/copy steps → Task 5 Step 5; `f0_per_volt` naming → already done (pre-plan). Non-goals (no cross-user catalog, no Postgres) respected. Per-user isolation = separate `_catalog/` per folder (Task 2/3).

**Placeholder scan:** every code step has complete code; commands have expected output. No TBDs.

**Type consistency:** `load_config()` returns the same dict keys (`raw_roots/db/output/figures`) used by `__main__.py`, `build_full_catalog.py`, and `coollog.py`. `parse_cooldown_md`/`load_registry`/`resolve_cooldown` keep the `COOLDOWN_SEED` dict shape (`label/sample/formula/fridge/start_date/end_date/f0_per_volt/s_bias_ma`) that `seed.py`, `crawl.py`, and `cooldown_log.py` already consume. `FIGURES_ROOT` in `catplot.py` matches the `results_root` parameter name used by the dispatch functions.

**Known caveat (not a gap):** cooldowns dir is intentionally fixed to the engine's own `cooldowns/` (the shared global registry) — not in per-user config — per the approved design.
