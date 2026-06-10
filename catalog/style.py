"""House figure style: ONE place for rcParams, colors, and standard axis labels.
dispatch applies it before every analyzer run, so every dispatched figure (and any
new analyzer) inherits it automatically. Policy + rationale: figure_style_guide.md."""
import matplotlib
import numpy as np

DPI = 130                        # every dispatched figure saves at this dpi
FIGSIZE = (8, 6)                 # single-panel default (multi-panel stacks size per-row)

RC = {
    "figure.figsize": FIGSIZE,
    "savefig.dpi": DPI,
    "font.size": 11,
    "axes.titlesize": 11,
    "axes.labelsize": 11,
    "legend.fontsize": 8,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "lines.linewidth": 0.8,
}

# Standard labels — f0 is the flux quantum (the repo writes f0/V for the calibration factor).
PSD_XLABEL = "Frequency (Hz)"
PSD_YLABEL = r"PSD ($f_0^2$/Hz)"      # calibrated; an uncalibrated PSD must say (V$^2$/Hz)
TS_XLABEL = "Time (s)"
TS_YLABEL = "Voltage (V)"             # raw time series are uncalibrated volts

# Temperature -> color, log scale over the lab's full range (11 mK base ... 5.5 K runs),
# so the SAME temperature is the SAME color in every figure. Use ONLY when temperature
# is the comparison axis; same-temperature overlays keep the default cycle (see guide).
TEMP_RANGE_MK = (10.0, 10000.0)
TEMP_CMAP = "viridis"

def temp_color(temp_mK):
    """Consistent color for a temperature (log-scaled TEMP_CMAP); gray when unknown."""
    import matplotlib.pyplot as plt   # lazy: keep style importable before the backend is set
    if not temp_mK or temp_mK <= 0:
        return "0.5"
    lo, hi = np.log10(TEMP_RANGE_MK[0]), np.log10(TEMP_RANGE_MK[1])
    x = (np.log10(temp_mK) - lo) / (hi - lo)
    return plt.get_cmap(TEMP_CMAP)(min(max(x, 0.0), 1.0))

def apply():
    """Set the house rcParams (idempotent). dispatch calls this before analyzers run."""
    matplotlib.rcParams.update(RC)
