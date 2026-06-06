"""Analyzers: per-trace wrappers over AutoSQUID's plot functions. Under the Agg
backend plt.show() is a no-op and leaves the figure open, so we call the plot
function then capture + save the current figure(s)."""
import matplotlib
matplotlib.use("Agg")                       # headless: save, never show
import matplotlib.pyplot as plt
import numpy as np
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

def psd_overlay(inputs, params, outdir):
    """GROUP analyzer: overlay the Welch PSD of every input trace on one log-log axis
    (many traces -> ONE figure/product). inputs: list of (row, factor). Each trace uses
    its own per-cooldown conversion factor; curves are labelled by interval + temperature.
    Reuses AutoSQUID's _psd_welch (no single AutoSQUID plot fn overlays multiple traces)."""
    P = params.get("P", 100); P = P[-1] if isinstance(P, list) else P
    window = params.get("window", "hanning")
    title = params.get("title", "PSD overlay")
    plt.close("all")
    plt.figure(figsize=(8, 6))
    n = 0
    for row, factor in sorted(inputs, key=lambda rf: (rf[0].get("scan_interval_us") or 0,
                                                       rf[0].get("temp_mK") or 0)):
        folder, fn = str(Path(row["path"]).parent), row["filename"]
        header, df = sq.read_daq_file(folder, fn)
        dt = float(header["SCANINTVAL"])
        phi = df["CHAN_01(V)"].to_numpy() * factor
        usable = row.get("usable_s")
        partial = usable is not None and usable < (len(phi) - 1) * dt   # a jump/surge trace -> use the pre-jump prefix
        if partial:
            phi = phi[:max(2 * P, int(usable / dt))]
        if len(phi) // P < 2:
            continue
        f, S = _psd_welch(phi, dt, P, window)
        lab = f"{(row.get('scan_interval_us') or 0):.0f}us {(row.get('temp_mK') or 0):.0f}mK"
        if partial:
            lab += f" (pre-jump {usable:.0f}s)"
        plt.loglog(f[1:], S[1:], lw=0.7, label=lab)
        n += 1
    plt.xlabel("Frequency (Hz)"); plt.ylabel(r"PSD ($f_0^2$/Hz)")
    plt.title(f"{title}  (n={n}, P={P})"); plt.legend(fontsize=7, ncol=2); plt.tight_layout()
    art = str(outdir / "psd_overlay.png")
    plt.savefig(art, dpi=130); plt.close("all")
    return art, {"n_traces": n, "P": P, "window": window}

def raw_overlay(inputs, params, outdir):
    """GROUP analyzer: stack the RAW voltage time-series of each input as one figure
    (one panel per trace), decimated for display. Diagnostic — works on any trace
    (e.g. frozen/failed ones); shows raw volts, no calibration. inputs: [(row, factor)]."""
    ds = int(params.get("downsample", 20000))
    rows = sorted(inputs, key=lambda rf: rf[0]["filename"])
    plt.close("all")
    fig, axes = plt.subplots(len(rows), 1, figsize=(11, 1.7 * len(rows) + 0.6), squeeze=False)
    for ax, (row, _factor) in zip(axes[:, 0], rows):
        header, df = sq.read_daq_file(str(Path(row["path"]).parent), row["filename"])
        v = df["CHAN_01(V)"].to_numpy(); dt = float(header["SCANINTVAL"])
        step = max(1, len(v) // ds)
        ax.plot((np.arange(len(v)) * dt)[::step], v[::step], lw=0.4)
        ax.set_ylabel("V", fontsize=8); ax.tick_params(labelsize=7)
        ax.set_title(f"{row['filename']}   [{(row.get('integrity_reason') or 'ok')[:46]}]", fontsize=8)
    axes[-1, 0].set_xlabel("Time (s)")
    fig.suptitle(params.get("title", "Raw voltage traces"), fontsize=11)
    fig.tight_layout()
    art = str(outdir / "raw_overlay.png"); fig.savefig(art, dpi=120); plt.close("all")
    return art, {"n_traces": len(rows), "downsample": ds}
