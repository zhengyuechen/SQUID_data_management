"""Default crawl roots. SQUID/data is the canonical raw root (auto-digested on
the next crawl as data is dropped in)."""
from pathlib import Path

PROJECTS_ROOT = Path(__file__).resolve().parents[1]        # .../projects
DEFAULT_ROOTS = [PROJECTS_ROOT / "SQUID" / "data"]
