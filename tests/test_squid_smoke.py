import numpy as np
from catalog.squid import sq
from tests._fixtures import make_corpus

def test_autosquid_reads_fixture(tmp_path):
    paths = make_corpus(tmp_path / "data")
    daq = paths["sample_33mK_clean"]
    header, df = sq.read_daq_file(str(daq.parent), daq.name)
    assert header["SCANINTVAL"] == 4.0e-6
    assert len(df["CHAN_01(V)"]) == 20_000

def test_integrity_gate_flags_railed(tmp_path):
    paths = make_corpus(tmp_path / "data")
    rail = paths["sample_33mK_railed"]
    header, df = sq.read_daq_file(str(rail.parent), rail.name)
    bad, reason = sq.is_surge_spec(df["CHAN_01(V)"].to_numpy())
    assert bad is True and isinstance(reason, str)
    good = paths["sample_33mK_clean"]
    _, gdf = sq.read_daq_file(str(good.parent), good.name)
    assert sq.is_surge_spec(gdf["CHAN_01(V)"].to_numpy())[0] is False
