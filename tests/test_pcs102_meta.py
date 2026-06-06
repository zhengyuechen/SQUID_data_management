import pytest
from catalog.pcs102_meta import parse_daq_filename, normalize_temp_mK

@pytest.mark.parametrize("name,iv,tmK,npts,run,outcome", [
    # simple / all-interval style
    ("DAQ_4us_33mK_2Mpts_1.txt",            4.0,    33.0,   2_000_000, 1, None),
    ("DAQ_100us_38mK_50000pts_2.txt",       100.0,  38.0,   50_000,    2, None),
    ("DAQ_500us_1p2K_10Mpts_1.txt",         500.0,  1200.0, 10_000_000,1, None),
    ("DAQ_10ms_14mK_1000pts.txt",           10_000.0, 14.0, 1000,      None, None),
    ("DAQ_20us_5p5K_100kpts_3.txt",         20.0,   5500.0, 100_000,   3, None),
    # AutoSQUID-native: date token and/or outcome suffix
    ("DAQ_Jun01_4us_4K_10Mpts_2.txt",       4.0,    4000.0, 10_000_000,2, None),
    ("DAQ_100us_15mK_1000000pts_1_JUMP.txt",100.0,  15.0,   1_000_000, 1, "JUMP"),
    ("DAQ_Jun02_4us_4K_10Mpts_3_SURGE.txt", 4.0,    4000.0, 10_000_000,3, "SURGE"),
])
def test_parse(name, iv, tmK, npts, run, outcome):
    m = parse_daq_filename(name)
    assert (m["scan_interval_us"], m["temp_mK"], m["n_points"], m["run_index"], m["outcome"]) \
        == (iv, tmK, npts, run, outcome)

def test_date_token_captured():
    assert parse_daq_filename("DAQ_Jun01_4us_4K_10Mpts_2.txt")["date_token"] == "Jun01"
    assert parse_daq_filename("DAQ_4us_33mK_2Mpts_1.txt")["date_token"] is None

def test_parse_rejects_garbage():
    assert parse_daq_filename("notes.txt") is None
    assert parse_daq_filename("DAQ_weird.txt") is None

@pytest.mark.parametrize("tok,mK", [("33mK",33.0),("300mK",300.0),("1p2K",1200.0),("5p5K",5500.0),("1K",1000.0)])
def test_normalize_temp(tok, mK):
    assert normalize_temp_mK(tok) == mK
