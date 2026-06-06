from pathlib import Path
from catalog.playbook import parse_playbook

PB = Path(__file__).resolve().parents[1] / "analysis_playbook.md"

def test_core():
    pol = parse_playbook(PB)
    assert pol["welch_P"] == [10, 100, 1000] and pol["temp_group_tol_mK"] == 10
    assert [1, 10] in pol["bands"] and pol["skip_failed"] is True

def test_added_band(tmp_path):
    md = tmp_path / "pb.md"
    md.write_text('x\n```json\n{"welch_P":[10],"window":"hanning","temp_group_tol_mK":5,'
                  '"bands":[[1,10],[100,1000]],"skip_failed":true}\n```\n')
    assert [100, 1000] in parse_playbook(md)["bands"]
