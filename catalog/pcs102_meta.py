"""Parse the DAQ filename grammar and normalize temperature to milli-kelvin.

Handles BOTH naming styles:
  - simple / GUI:  DAQ_<interval>_<temp>_<npts>_<run>.txt
  - AutoSQUID:     DAQ_<DateTok>_<interval>_<temp>_<npts>_<run>[_OUTCOME].txt
The optional date token (e.g. Jun01) and optional uppercase OUTCOME suffix
(JUMP/SURGE/RAIL/...) are AutoSQUID's; clean traces carry no OUTCOME suffix.
Returns None on anything that does not match (the crawler surfaces these).
"""
import re

_INTERVAL_US = {"us": 1.0, "ms": 1000.0}
_NPTS_MULT = {"": 1, "k": 1_000, "M": 1_000_000}

_FN = re.compile(
    r"^DAQ_(?:(?P<date>[A-Za-z][A-Za-z0-9-]*)_)?"      # optional AutoSQUID date token, e.g. Jun01
    r"(?P<ival>\d+(?:\.\d+)?)(?P<iunit>us|ms)"
    r"_(?P<temp>\d+(?:p\d+)?(?:mK|K)[A-Za-z]*)"
    r"_(?P<npts>\d+(?:p\d+)?)(?P<nmult>[kM]?)pts"        # npts may carry a 'p' decimal (AutoSQUID usable-count tag, e.g. 8p4M)
    r"(?:_(?P<run>\d+))?"                              # optional order/run index
    r"(?:_(?P<outcome>[A-Z]+))?\.txt$")                # optional outcome suffix (failed traces)

def normalize_temp_mK(tok):
    m = re.match(r"^(?P<num>\d+(?:p\d+)?)(?P<unit>mK|K)", tok)
    if not m:
        return None
    val = float(m["num"].replace("p", "."))
    return val if m["unit"] == "mK" else val * 1000.0

def parse_daq_filename(name):
    """Dict with scan_interval_us, temp_mK, n_points, run_index, date_token, outcome; or None."""
    m = _FN.match(name)
    if not m:
        return None
    temp_mK = normalize_temp_mK(m["temp"])
    if temp_mK is None:
        return None
    return {"scan_interval_us": float(m["ival"]) * _INTERVAL_US[m["iunit"]],
            "temp_mK": temp_mK,
            "n_points": round(float(m["npts"].replace("p", ".")) * _NPTS_MULT[m["nmult"]]),   # round, not int: 8.2*1e6 truncates to 8199999
            "run_index": int(m["run"]) if m["run"] else None,
            "date_token": m["date"],
            "outcome": m["outcome"]}            # None for clean traces
