"""Synthetic PCS102 corpora for tests, written with AutoSQUID's own writers.

make_corpus()        -> the simple all-interval-style layout (sample/ + bkg/).
make_native_corpus() -> the AutoSQUID-native layout: a date-named folder with a
                        date-token + outcome-suffix filename and an experiment_log.txt.
Calibration resolves on the PCS102 header DATE, so each file's DATE is patched into
the right cooldown window (save_pcs102 stamps 'today', which is in no window).
"""
import numpy as np
from pathlib import Path
from catalog.squid import sq
from catalog.seed import register_cooldown

SCAN_INTERVAL_S = 4.0e-6
N = 20_000

def seed_test_cooldowns(conn):
    """Register the cooldowns the synthetic corpora's header dates fall into. Cooldowns are
    operational data (not baked into the app), so tests register the ones they need."""
    register_cooldown(conn, "YbZn2GaO5_Dec2025", "YbZn2GaO5", "2025-12-22", "2026-01-04", 0.837,
                      formula="YbZn2GaO5", s_bias_ma=0.0747)
    register_cooldown(conn, "Sapphire_Dec2025", "Sapphire-background", "2025-12-08", "2025-12-14", 0.834,
                      formula="Al2O3", s_bias_ma=0.0752)
    register_cooldown(conn, "Sapphire_May2026", "Sapphire-background", "2026-05-18", "2026-06-30", 0.762,
                      formula="Al2O3", s_bias_ma=0.0654)

def _healthy(seed):
    rng = np.random.default_rng(seed)
    return rng.normal(0.012, 0.002, N).astype(np.float64)

def _railed(seed):
    v = _healthy(seed); v[N // 2:] = 1.0; return v          # frozen second half -> "stuck", not partially usable

def _jumped(seed):
    v = _healthy(seed); v[3 * N // 4:] += 0.02; return v     # baseline steps ~10σ at 75% (noise preserved) -> a JUMP

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
    """bkg/ = background (Sapphire window 12-14), else = YbZn sample (12-22→01-04)."""
    spec = [
        ("sample_33mK_clean", "sample", "DAQ_4us_33mK_20000pts_1.txt", _healthy(1), 0.033, "12-23-2025"),
        ("sample_14mK_clean", "sample", "DAQ_4us_14mK_20000pts_1.txt", _healthy(2), 0.014, "12-24-2025"),
        ("sample_33mK_run2",  "sample", "DAQ_4us_33mK_20000pts_2.txt", _healthy(3), 0.033, "12-23-2025"),
        ("sample_33mK_railed","sample", "DAQ_4us_33mK_20000pts_3.txt", _railed(4),  0.033, "12-23-2025"),
        ("bkg_300mK_clean",   "bkg",    "DAQ_4us_300mK_20000pts_1.txt", _healthy(5), 0.300, "12-14-2025"),
    ]
    return {k: _write(root / folder, name, v, T, mdy) for k, folder, name, v, T, mdy in spec}

def make_bare_corpus(root, date="12-23-2025"):
    """Real lab-PC style: DAQ_<interval>_<temp>_<npts>_<run>.txt with NO TEMP_*.csv and
    NO experiment_log.txt (the common case). Header date controls calibration."""
    folder = root / "run"
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, v in [("DAQ_100us_4K_20000pts_1.txt", _healthy(21)),
                    ("DAQ_4us_4K_20000pts_1.txt", _healthy(22))]:
        daq = folder / name
        sq.save_pcs102(str(daq), v, SCAN_INTERVAL_S)   # save_pcs102 only; no temp csv, no log
        set_header_date(daq, date)
        paths[name] = daq
    return paths

def make_native_corpus(root):
    """AutoSQUID-native: date-named folder, date-token + outcome-suffix filenames,
    TEMP sidecars, and a real experiment_log.txt. Returns {key: daq_path}."""
    folder = root / "Jun01-2026"
    clean_name = "DAQ_Jun01_4us_33mK_20000pts_2.txt"          # clean: no outcome suffix
    jump_name = "DAQ_Jun01_4us_33mK_20000pts_1_JUMP.txt"      # failed: JUMP suffix + date token
    paths = {"native_clean": _write(folder, clean_name, _healthy(11), 0.033, "12-23-2025"),
             "native_jump":  _write(folder, jump_name,  _railed(12),  0.033, "12-23-2025")}
    dur = N * SCAN_INTERVAL_S
    log = str(folder / "experiment_log.txt")
    sq.log_experiment(log, {"timestamp": "2026-06-01T12:00:00", "scan_interval_us": 4, "n_target": N,
                            "n_acquired": N // 2, "n_clean": 0, "attempt": 1, "outcome": "JUMP",
                            "jump_index": N // 2, "jump_time_s": round(dur / 2, 3), "n_resets": 1,
                            "mean_V": 0.5, "std_V": 0.2, "T_start_K": 0.033, "T_end_K": 0.034,
                            "filename": jump_name})
    sq.log_experiment(log, {"timestamp": "2026-06-01T12:01:00", "scan_interval_us": 4, "n_target": N,
                            "n_acquired": N, "n_clean": 1, "attempt": 2, "outcome": "CLEAN",
                            "jump_index": -1, "jump_time_s": "", "n_resets": 2,
                            "mean_V": 0.012, "std_V": 0.002, "T_start_K": 0.0331, "T_end_K": 0.0332,
                            "filename": clean_name})
    return paths
