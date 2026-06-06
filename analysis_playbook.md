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
