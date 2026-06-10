"""Read the measurement PowerPoint decks (read-only) and extract the per-cooldown SETUP
parameters — above all the calibration factor (f0/V), the one field that feeds PSD analysis.
Decks are the ONLY source of these numbers (until auto_s_tune writes them to action_log).

Scope (per the 2026-06-09 decisions): setup-parameter extraction + a HUMAN-CONFIRMED proposal.
The deck tables record what the deck says; calibration only ever enters the cooldown table via
a human running `coollog add-cooldown`. No trace-linking, no mid-cooldown change tracking.

Real grammar (from SQUID/data-analysis/ppt): a setup slide titled e.g.
"5/16/2026 Setup for 11 mK MXC", body lines like "S-bias = 0.3 mA" / "Output ~ 4.5 Vpp" /
"Calibration Factor: 0.837 Fo/V". `=`, `:`, `~` all separate; S-bias appears in BOTH the
Array and SQUID sections with different values, so parsing is section-aware.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

# --- pure parsing (no DB, no file IO) -------------------------------------------------

_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
_MXC = re.compile(r"([0-9]*\.?[0-9]+)\s*mK", re.I)
_FACTOR = re.compile(r"(?:calibration\s+)?factor\s*[=:~]\s*([0-9]*\.?[0-9]+)", re.I)
_FLUXJUMP = re.compile(r"flux\s*jump\s*[=:~]\s*([0-9]*\.?[0-9]+)", re.I)
# one V-Phi parameter occurrence: <name> <sep> <number> <unit?>  (many may share a line)
_PARAM = re.compile(r"\b(S-bias|A-bias|S-flux|A-flux|Offset|Output)\s*[=:~]\s*"
                    r"([0-9]*\.?[0-9]+)\s*(mA|uA|µA|mV|Vpp|V)?", re.I)

_ARRAY_MARK = ("array v-phi", "array auto-tuning", "array auto tuning", "locked array")
_SQUID_MARK = ("squid v-phi", "squid manual", "squid auto", "locked squid")
_UNIT = {"ma": "ma", "ua": "ua", "µa": "ua", "mv": "mv", "vpp": "vpp", "v": "v"}
_SETUP_MARKERS = ("v-phi", "auto-tuning", "auto tuning", "auto-calibration", "setup")


def _iso_date(title):
    m = _DATE.search(title or "")
    if not m:
        return None
    mo, d, y = (int(x) for x in m.groups())
    if y < 100:
        y += 2000
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _param_key(section, name, unit):
    name = name.lower().replace("-", "_")               # S-bias -> s_bias
    u = _UNIT.get((unit or "").lower())
    return f"{section}_{name}" + (f"_{u}" if u else "")


def parse_setup_slide(title, body):
    """If this slide is a setup slide, return a dict with the calibration factor (f0_per_volt),
    flux jump, date, MXC label, and a section-namespaced params dict; else None.
    `body` is the slide's text (excluding its title); newlines separate lines.

    Section assumption: the SQUID block is introduced by the decks' established wording
    (`SQUID V-Phi` / `SQUID manual` / `SQUID auto…` / `Locked squid`, see `_SQUID_MARK`).
    A future deck that introduces it differently would leave a SQUID param under `array_*`.
    The calibration factor (the load-bearing field) is section-independent, so it is robust
    regardless; only the V-Phi context could be mis-bucketed. Proposals are human-confirmed."""
    title = title or ""
    body = body or ""
    blob = f"{title}\n{body}".lower()
    if not any(mk in blob for mk in _SETUP_MARKERS) and not _FACTOR.search(body):
        return None

    fm = _FACTOR.search(body) or _FACTOR.search(title)
    jm = _FLUXJUMP.search(body)
    params, section = {}, "array"                        # array always leads in these decks
    for line in body.splitlines():
        low = line.lower()
        if any(mk in low for mk in _SQUID_MARK):
            section = "squid"
        elif any(mk in low for mk in _ARRAY_MARK):
            section = "array"
        for name, val, unit in _PARAM.findall(line):
            params[_param_key(section, name, unit)] = float(val)

    mxc = _MXC.search(title) or _MXC.search(body)
    return {
        "setup_date": _iso_date(title),
        "mxc_label": f"{mxc.group(1)} mK" if mxc else None,
        "f0_per_volt": float(fm.group(1)) if fm else None,
        "flux_jump_v": float(jm.group(1)) if jm else None,
        "params": params,
        "raw_text": body,
    }


def sample_from_filename(name):
    """'SQ180 w Sapphire - Measurements May2026.pptx' -> 'Sapphire'."""
    m = re.search(r"\bw\s+([A-Za-z0-9]+)", Path(name).stem)
    return m.group(1) if m else None


# --- deck IO (read-only on the .pptx) -------------------------------------------------

def _slide_title_body(slide):
    title_shape = slide.shapes.title
    title = title_shape.text if title_shape is not None else ""
    body = "\n".join(sh.text_frame.text for sh in slide.shapes
                     if sh.has_text_frame and sh is not title_shape and sh.text_frame.text.strip())
    return title, body


def extract_deck(path):
    """Open a .pptx read-only and return its provenance + every setup slide found."""
    from pptx import Presentation                        # imported lazily (optional dependency)
    path = Path(path)
    prs = Presentation(str(path))
    cp = prs.core_properties
    setups = []
    for i, slide in enumerate(prs.slides):
        title, body = _slide_title_body(slide)
        s = parse_setup_slide(title, body)
        if s is not None:
            s["slide_index"] = i
            setups.append(s)
    return {
        "path": str(path), "filename": path.name,
        "sample_guess": sample_from_filename(path.name),
        "slide_count": len(prs.slides),
        "core_created": str(cp.created) if cp.created else None,
        "core_modified": str(cp.modified) if cp.modified else None,
        "content_hash": hashlib.sha1(path.read_bytes()).hexdigest(),
        "setups": setups,
    }


def _find_decks(roots):
    seen = set()
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.pptx")):
            if p.name.startswith("~$") or "__MACOSX" in p.parts or p in seen:
                continue                                  # skip PowerPoint lock files
            seen.add(p)
            yield p


def crawl_decks(conn, roots):
    """Index every .pptx under roots into the deck/deck_setup tables. Idempotent + incremental
    by content hash; re-extracts a deck whose bytes changed. Read-only on the decks.
    Returns {'decks','setups','skipped'}."""
    stats = {"decks": 0, "setups": 0, "skipped": 0, "failed": 0}
    for path in _find_decks(roots):
        st = path.stat()
        prior = conn.execute("SELECT id, content_hash FROM deck WHERE path=?", (str(path),)).fetchone()
        try:                                              # an unreadable/corrupt deck must not abort the crawl
            d = extract_deck(path)
        except Exception as e:                            # (DB writes below are left to propagate — a real bug should surface)
            stats["failed"] += 1
            print(f"[decks] skipped unreadable deck {path.name}: {e}")
            continue
        if prior and prior["content_hash"] == d["content_hash"]:
            stats["skipped"] += 1
            continue
        if prior:                                         # changed deck: replace its rows
            conn.execute("DELETE FROM deck_setup WHERE deck_id=?", (prior["id"],))
            conn.execute("DELETE FROM deck WHERE id=?", (prior["id"],))
        cur = conn.execute(
            """INSERT INTO deck (path,filename,sample_guess,slide_count,core_created,core_modified,
                                 size_bytes,mtime_ns,content_hash,crawled_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (d["path"], d["filename"], d["sample_guess"], d["slide_count"],
             d["core_created"], d["core_modified"], st.st_size, st.st_mtime_ns, d["content_hash"],
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
        deck_id = cur.lastrowid
        for s in d["setups"]:
            conn.execute(
                """INSERT INTO deck_setup (deck_id,slide_index,setup_date,mxc_label,
                                           f0_per_volt,flux_jump_v,params,raw_text)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (deck_id, s["slide_index"], s["setup_date"], s["mxc_label"],
                 s["f0_per_volt"], s["flux_jump_v"], json.dumps(s["params"], sort_keys=True), s["raw_text"]))
            stats["setups"] += 1
        stats["decks"] += 1
    conn.commit()
    return stats


# --- proposal (human-confirmed; never auto-writes calibration) ------------------------

def _suggested_label(sample, setup_date):
    if not setup_date:
        return f"{sample or 'SAMPLE'}_cooldown"
    y, m, _ = setup_date.split("-")
    mon = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")[int(m) - 1]
    return f"{sample or 'SAMPLE'}_{mon}{y}"


def propose_cooldowns(conn):
    """For each deck setup slide that carries a calibration factor, build a registration proposal
    (the f0/V + SQUID S-bias + a suggested label). One per (deck, factor-bearing slide); the human
    reviews and runs the printed command. Calibration is never written here."""
    proposals = []
    rows = conn.execute(
        """SELECT ds.setup_date, ds.f0_per_volt, ds.flux_jump_v, ds.params, ds.slide_index,
                  d.filename, d.sample_guess
           FROM deck_setup ds JOIN deck d ON d.id=ds.deck_id
           WHERE ds.f0_per_volt IS NOT NULL
           ORDER BY d.filename, ds.slide_index""").fetchall()
    for r in rows:
        params = json.loads(r["params"] or "{}")
        proposals.append({
            "deck_filename": r["filename"],
            "slide_index": r["slide_index"],
            "sample_guess": r["sample_guess"],
            "setup_date": r["setup_date"],
            "f0_per_volt": r["f0_per_volt"],
            "flux_jump_v": r["flux_jump_v"],
            "squid_s_bias_ma": params.get("squid_s_bias_ma"),
            "suggested_label": _suggested_label(r["sample_guess"], r["setup_date"]),
        })
    return proposals


def format_proposal(p):
    """Render one proposal as a ready-to-run `coollog add-cooldown` command + provenance.
    The human edits the label / end date and runs it — that is the calibration confirmation."""
    sbias = f" --s-bias {p['squid_s_bias_ma']}" if p.get("squid_s_bias_ma") is not None else ""
    cmd = (f"python scripts/coollog.py add-cooldown {p['suggested_label']} "
           f"--sample {p['sample_guess'] or '<SAMPLE>'} --start {p['setup_date'] or '<START>'} "
           f"--end <END-DATE> --f0 {p['f0_per_volt']}{sbias}")
    fj = f", flux jump {p['flux_jump_v']} V" if p.get("flux_jump_v") is not None else ""
    return (f"# from {p['deck_filename']} (slide {p['slide_index']}): "
            f"f0/V = {p['f0_per_volt']}{fj}\n"
            f"#   review the label + end date, then run:\n{cmd}")
