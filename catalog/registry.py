"""Analyzer registries.
Per-trace analyzers:  run(row, factor, params, outdir)  -> (artifact_path, scalars)
Group analyzers:      run(inputs, params, outdir)        -> (artifact_path, scalars)  (inputs = [(row, factor), ...])"""
from catalog import analyzers

REGISTRY, CODE_REF = {}, {}
GROUP_REGISTRY, GROUP_CODE_REF = {}, {}

def register(kind, fn, code_ref):
    REGISTRY[kind] = fn; CODE_REF[kind] = code_ref

def register_group(kind, fn, code_ref):
    GROUP_REGISTRY[kind] = fn; GROUP_CODE_REF[kind] = code_ref

register("psd",         analyzers.psd,         "plot_psd@AutoSQUID")
register("time_series", analyzers.time_series, "plot_run@AutoSQUID")

register_group("psd_overlay", analyzers.psd_overlay, "psd_overlay@AutoSQUID._psd_welch")
register_group("raw_overlay", analyzers.raw_overlay, "raw_overlay@catalog.analyzers")
