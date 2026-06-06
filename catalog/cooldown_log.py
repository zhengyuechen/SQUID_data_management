"""Per-cooldown lab logbooks: human-readable `cooldowns/<label>.md` files are the
source of truth (restore values + Array/SQUID V-Phi setup + a phased notes log);
the catalog indexes them onto the cooldown row (setup_notes) + cooldown_note table.

Logbook format (one file per cooldown, named for the cooldown label):
    # Cooldown logbook — <label>
    ## Setup
    <free text: restore values, Array/SQUID V-Phi, Calibration factor: 0.837 f₀/V, ...>
    ## Notes
    - [setup] message
    - [calibration] message
    - [run] message
"""
import re
from pathlib import Path

LOGBOOK_DIR = Path(__file__).resolve().parents[1] / "cooldowns"

_SECTION = re.compile(r"^##\s+(.+?)\s*$")
_NOTE = re.compile(r"^\s*-\s*\[(?P<phase>[^\]]+)\]\s*(?P<text>.+?)\s*$")
_FACTOR = re.compile(r"[Cc]alibration factor:?\s*([0-9]*\.?[0-9]+)")

def parse_logbook(md_path):
    """Return {'setup': str, 'notes': [(phase, text)], 'calibration_factor': float|None}."""
    text = Path(md_path).read_text()
    sections, cur, buf = {}, "_preamble", []
    for line in text.splitlines():
        m = _SECTION.match(line)
        if m:
            sections[cur] = "\n".join(buf).strip(); cur = m.group(1).strip().lower(); buf = []
        else:
            buf.append(line)
    sections[cur] = "\n".join(buf).strip()
    notes = []
    for line in sections.get("notes", "").splitlines():
        nm = _NOTE.match(line)
        if nm:
            notes.append((nm["phase"].strip(), nm["text"].strip()))
    fm = _FACTOR.search(sections.get("setup", "")) or _FACTOR.search(text)
    return {"setup": sections.get("setup", ""), "notes": notes,
            "calibration_factor": float(fm.group(1)) if fm else None}

def load_logbooks(conn, logbook_dir=LOGBOOK_DIR):
    """Index every cooldowns/<label>.md onto its cooldown (setup + notes). Returns count loaded.
    Warns if a logbook's calibration factor disagrees with the cooldown's stored f0_per_volt,
    or if a logbook names a cooldown that isn't registered yet."""
    logbook_dir = Path(logbook_dir)
    if not logbook_dir.exists():
        return 0
    cmap = {r["label"]: (r["id"], r["f0_per_volt"])
            for r in conn.execute("SELECT id, label, f0_per_volt FROM cooldown")}
    loaded = 0
    for md in sorted(logbook_dir.glob("*.md")):
        if md.name.startswith("_"):
            continue   # reference files (e.g. _calibration.md), not per-cooldown logbooks
        label = md.stem
        if label not in cmap:
            print(f"[logbook] no registered cooldown '{label}' for {md.name} — add it to COOLDOWN_SEED first")
            continue
        cid, f0 = cmap[label]
        lb = parse_logbook(md)
        if lb["calibration_factor"] is not None and abs(lb["calibration_factor"] - f0) > 1e-6:
            print(f"[logbook] WARNING {label}: logbook factor {lb['calibration_factor']} != cooldown {f0}")
        conn.execute("UPDATE cooldown SET setup_notes=?, logbook_path=? WHERE id=?", (lb["setup"], str(md), cid))
        conn.execute("DELETE FROM cooldown_note WHERE cooldown_id=?", (cid,))
        for i, (phase, note) in enumerate(lb["notes"]):
            conn.execute("INSERT INTO cooldown_note (cooldown_id, phase, note, ord) VALUES (?,?,?,?)",
                         (cid, phase, note, i))
        loaded += 1
    conn.commit()
    return loaded

def append_note(label, phase, text, logbook_dir=LOGBOOK_DIR):
    """Append `- [phase] text` to cooldowns/<label>.md (creating it / its ## Notes section if needed)."""
    md = Path(logbook_dir) / f"{label}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    body = md.read_text() if md.exists() else f"# Cooldown logbook — {label}\n\n## Notes\n"
    if "## Notes" not in body:
        body += "\n## Notes\n"
    md.write_text(body.rstrip() + f"\n- [{phase}] {text}\n")
    return md

def write_calibration_md(path=LOGBOOK_DIR / "_calibration.md"):
    """Generate the human-readable calibration reference (f₀/V + S-bias per cooldown) from
    COOLDOWN_SEED — so the calibration numbers live in markdown too, always in sync with
    `catalog/calibration.py` (the build-time source). Regenerated on each build."""
    from catalog.calibration import COOLDOWN_SEED
    lines = [
        "# Cooldown calibration reference", "",
        "## Essentials",
        "- Per-cooldown SQUID calibration **f₀/V** and **S-bias**, for quick human reference.",
        "- Generated from `catalog/calibration.py` (the build-time source) — edit calibration there; "
        "this file is regenerated every build. Full V-Phi setup per cooldown: `cooldowns/<label>.md`.", "",
        "---", "",
        "| Cooldown | Sample | Dates | f₀/V | S-bias (mA) |",
        "|---|---|---|---|---|",
    ]
    for r in COOLDOWN_SEED:
        lines.append(f"| {r['label']} | {r['sample']} | {r['start_date']} → {r['end_date']} | "
                     f"{r['f0_per_volt']} | {r['s_bias_ma']} |")
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n")
    return p

def render(conn, label):
    """Human-readable dump of a cooldown's setup + notes."""
    c = conn.execute("SELECT * FROM cooldown WHERE label=?", (label,)).fetchone()
    if not c:
        return f"no cooldown '{label}'"
    out = [f"COOLDOWN  {label}   (f₀/V = {c['f0_per_volt']}, {c['start_date']} → {c['end_date']})"]
    if c["setup_notes"]:
        out += ["", "SETUP", c["setup_notes"]]
    notes = conn.execute("SELECT phase, note FROM cooldown_note WHERE cooldown_id=? ORDER BY ord",
                         (c["id"],)).fetchall()
    if notes:
        out += ["", "NOTES"] + [f"  [{n['phase']}] {n['note']}" for n in notes]
    return "\n".join(out)
