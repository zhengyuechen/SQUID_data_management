import json
from catalog.config import load_config, data_roots, ppt_roots, write_default_config

def test_defaults_used_when_no_file(tmp_path):
    cfg = load_config(tmp_path / "nope.json")
    assert cfg["db"] == "catalog.sqlite"
    assert "data_roots" in cfg and "ppt_roots" in cfg

def test_user_overrides_merge(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"data_roots": ["/data/a", "/data/b"], "ppt_roots": ["/ppt"]}))
    cfg = load_config(p)
    assert [str(r) for r in data_roots(cfg)] == ["/data/a", "/data/b"]
    assert cfg["ppt_roots"] == ["/ppt"]
    assert cfg["db"] == "catalog.sqlite"          # untouched key falls back to default

def test_empty_value_falls_back(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"db": "", "data_roots": []}))   # empty -> default
    cfg = load_config(p)
    assert cfg["db"] == "catalog.sqlite"

def test_ppt_roots_skips_unset_placeholder(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"ppt_roots": ["<absolute path to parameter PowerPoint decks (optional)>"]}))
    cfg = load_config(p)
    assert ppt_roots(cfg) == []                    # the --init placeholder is not a real root
    p.write_text(json.dumps({"ppt_roots": ["/decks/a", "/decks/b"]}))
    assert [str(r) for r in ppt_roots(load_config(p))] == ["/decks/a", "/decks/b"]

def test_write_default_config_is_safe(tmp_path):
    p = tmp_path / "config.json"
    out, created = write_default_config(p)
    assert created and out.exists()
    data = json.loads(out.read_text())
    assert "data_roots" in data and "ppt_roots" in data
    _, created_again = write_default_config(p)     # must not clobber an existing config
    assert created_again is False
