"""Default crawl roots. SQUID/data is the canonical raw root (auto-digested on
the next crawl as data is dropped in)."""
from pathlib import Path

PROJECTS_ROOT = Path(__file__).resolve().parents[2]        # .../projects  (file: projects/data_management_plan/SQUID_data_management/roots.py)
DEFAULT_ROOTS = [PROJECTS_ROOT / "SQUID" / "data"]
DEFAULT_PPT_ROOTS = [PROJECTS_ROOT / "SQUID" / "data-analysis" / "ppt"]   # parameter decks
