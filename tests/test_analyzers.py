from pathlib import Path
from catalog.registry import REGISTRY
from tests._fixtures import make_corpus

def _row(daq):
    return {"path": str(daq), "filename": daq.name,
            "temp_sidecar_path": str(daq.parent / daq.name.replace("DAQ", "TEMP", 1).replace(".txt", ".csv"))}

def test_psd_wraps_plot_psd(tmp_path):
    p = make_corpus(tmp_path / "data"); out = tmp_path / "out"; out.mkdir()
    art, sc = REGISTRY["psd"](_row(p["sample_33mK_clean"]), 0.837, {"P": [10, 100]}, out)
    assert Path(art).exists() and art.endswith(".png")
    assert sc["conversion"] == 0.837 and sc["white_level"] > 0

def test_time_series_wraps_plot_run(tmp_path):
    p = make_corpus(tmp_path / "data"); out = tmp_path / "out"; out.mkdir()
    art, sc = REGISTRY["time_series"](_row(p["sample_33mK_clean"]), 0.837, {}, out)
    assert Path(art).exists() and art.endswith(".png")
    assert abs(sc["mean_V"] - 0.012) < 0.003 and sc["duration_s"] > 0
