"""Parse the machine-readable core (a fenced ```json block) out of the playbook Markdown."""
import json
import re
from pathlib import Path

_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

def parse_playbook(md_path):
    m = _JSON_BLOCK.search(Path(md_path).read_text())
    if not m:
        raise ValueError(f"no ```json policy block in {md_path}")
    return json.loads(m.group(1))
