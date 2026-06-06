"""Single import point for the published AutoSQUID package the catalog depends on.

AutoSQUID is pip-installed (do NOT add its source tree to sys.path) and imported
as `sq` per lab convention; use `sq.read_daq_file`, `sq.is_surge_spec`,
`sq.plot_psd`, `sq.Config`, etc. `_psd_welch` is not re-exported at package level,
so it comes from the submodule.

Install once:  pip install -e SQUID/automation/AutoSQUID
"""
import AutoSQUID as sq
from AutoSQUID.plotting import _psd_welch

__all__ = ["sq", "_psd_welch"]
