"""Per-deployment paths, read from `config.json` at the repo root.

Each machine sets its own roots once (copy `config.example.json` -> `config.json`, or run
`build_full_catalog.py --init`). `config.json` is git-ignored, so a `git pull` never clobbers
a machine's paths. When it's absent, this loader falls back to the dev-tree defaults
(`roots.DEFAULT_ROOTS`), so the repo still works unconfigured during development.

Extensible: it's just a JSON dict. Add new `*_roots` keys as new data sources appear
(e.g. `ppt_roots` for parameter decks) — declare them here in `defaults()`, then consume
them wherever a tool needs them.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config.json"


def _dev_default(attr):
    try:
        import roots
        return [str(p) for p in getattr(roots, attr)]
    except Exception:
        return []


def defaults():
    return {
        "db": "catalog.sqlite",
        "data_roots": _dev_default("DEFAULT_ROOTS"),     # folders holding raw DAQ_*.txt (crawled)
        "ppt_roots": _dev_default("DEFAULT_PPT_ROOTS"),  # folders holding parameter PowerPoint decks (setup/calibration)
    }


def load_config(path=CONFIG_PATH):
    """`config.json` merged over `defaults()`. A missing key, or an empty value
    (``""`` / ``[]`` / ``null``), falls back to the default for that key."""
    cfg = defaults()
    p = Path(path)
    if p.exists():
        for k, v in json.loads(p.read_text()).items():
            if v not in (None, "", []):
                cfg[k] = v
    return cfg


def data_roots(cfg=None):
    """The configured data roots as `Path`s."""
    return [Path(r) for r in (cfg or load_config())["data_roots"]]


def ppt_roots(cfg=None):
    """The configured PowerPoint-deck roots as `Path`s (skips unset placeholder paths)."""
    return [Path(r) for r in (cfg or load_config()).get("ppt_roots", []) if not str(r).startswith("<")]


def write_default_config(path=CONFIG_PATH, force=False):
    """Write a starter `config.json` with placeholder paths (used by `--init`).
    Returns (path, created); won't overwrite an existing file unless `force`."""
    p = Path(path)
    if p.exists() and not force:
        return p, False
    template = {
        "db": "catalog.sqlite",
        "data_roots": ["<absolute path to the folder holding raw DAQ_*.txt>"],
        "ppt_roots": ["<absolute path to parameter PowerPoint decks (optional)>"],
    }
    p.write_text(json.dumps(template, indent=2) + "\n")
    return p, True
