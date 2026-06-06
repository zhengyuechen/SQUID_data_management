# Bench-PC Deployment — Design

## Essentials
- Copy `data_management_plan/` to the bench PC once as the **shared engine** (code + global cooldown registry + one CLAUDE.md + one README). Data lives at `F:\Dilution Refrigerator Data\<user>\`.
- **Per-user catalogs**: each user's `catalog.sqlite` + `output/` + `figures/` live under their own `<user>\_catalog\`. Users only see their own data.
- **Calibration leaves Python**: the global `cooldowns\<label>.md` registry (machine-readable header + human setup/notes) is the source; the catalog *loads* it into the DB. Adding a cooldown = edit a markdown file, run build. No code.
- **Identity = the folder Claude opens in.** Open Claude Code in `…\<user>\`; the engine auto-detects the user, raw root, and DB. Operated by people *and* other Claude sessions (Claude Code is installed there).
- Naming corrected to **`f0_per_volt` / f₀/V** (done in the existing code).

---

## Goal & constraints
Deploy the catalog on the lab bench PC, which holds ~1–2 years of dilution-fridge data at `F:\Dilution Refrigerator Data\<user>\`, has **Claude Code installed**, and will be run by multiple people (and their Claude sessions). Must be: operable without editing Python, isolated per user, and self-documenting so a fresh Claude session "just picks it up." AutoSQUID is present on the PC (can be read for reference).

## Topology
```
F:\Dilution Refrigerator Data\
  CLAUDE.md          ← THE one CLAUDE.md (a session opened in any <user>\ reads it as a parent)
  README.md          ← THE one human README
  _engine\           ← the copied data_management_plan (shared, once)
    catalog\         (the package)
    cooldowns\       GLOBAL cooldown registry: <label>.md per cooldown = the calibration SOURCE
    tests\  …
  Alice\
    <her raw cooldown folders>\          ← raw DAQ (untouched)
    _catalog\  catalog.sqlite · output\ · figures\
  Bob\  …same shape…
```
- **Shared**: `_engine\` (code) + `_engine\cooldowns\` (calibration). One copy, one source of truth.
- **Per-user**: everything under `<user>\_catalog\`. Separate DB files → no concurrency issues.
- **Why the CLAUDE.md sits at the data root**: Claude Code reads `CLAUDE.md` from the cwd upward, so a session started in `…\Alice\` automatically picks up `F:\Dilution Refrigerator Data\CLAUDE.md`.

## Calibration as data (the key change)
`calibration.py` stops holding numbers and becomes a **loader** of the global registry. Each cooldown is one markdown file with a machine-readable header + the existing human logbook body:
```markdown
---
label: YbZn2GaO5_Dec2025
sample: YbZn2GaO5
start_date: 2025-12-22
end_date: 2026-01-04
f0_per_volt: 0.837
s_bias_mA: 0.0747
---
## Essentials … ## Setup (V-Phi) … ## Notes …
```
- `resolve_cooldown(date)` and `seed_lookups` read the registry instead of a hardcoded `COOLDOWN_SEED`.
- The DB still holds a loaded copy (rebuildable projection); the **markdown is the durable, human-editable source** — consistent with the catalog's disk-owns-truth model.
- **Register/extend a cooldown** = add/edit a `cooldowns\<label>.md` file and run build. The existing factor↔logbook cross-check still guards against typos.

## Operation (people and Claude)
- **One `CLAUDE.md`** (generic) at the data root tells any session: "you're in `<user>\`; raw = this folder; calibration = `_engine\cooldowns\`; your DB = `.\_catalog\catalog.sqlite`. Run `build` to index, `catplot …` to plot, add a cooldown by editing the global registry."
- **One `README.md`** mirrors it for a human (install, build, register a cooldown, query, plot).
- **Current-user resolution**: derived from cwd (the `<user>\` folder Claude opens in). If run from `_engine\` instead, the engine asks "which user?" or reads a tiny config.
- Commands are the existing ones, made path-aware: `build` (crawl + enrich + usable_s + load registry), `catplot`, `coollog`.

## Config (light)
A small `_catalog\config.toml` per user (auto-created on first build) records `raw_roots`, `cooldowns_dir` (the global registry), `db`. Defaults derive from the folder, so it usually needs no editing — same engine code serves every user; only the folder differs.

## Install / copy steps
1. Copy `data_management_plan\` → `F:\Dilution Refrigerator Data\_engine\`.
2. `pip install -e F:\…\_engine\..\SQUID\automation\AutoSQUID` *(or the published AutoSQUID)* + `pip install -e F:\…\_engine` so `catalog` imports anywhere.
3. Put the generic `CLAUDE.md` + `README.md` at `F:\Dilution Refrigerator Data\`.
4. Seed the global `cooldowns\` with the known cooldown markdown files.
5. Per user: open Claude Code in `…\<user>\`, run `build`.

## What changes in the code (scope for the plan)
1. **Calibration loader** — replace `COOLDOWN_SEED` (Python) with a parser of `cooldowns\<label>.md` headers; `resolve_cooldown`/`seed_lookups`/`write_calibration_md` read it. (`f0_per_volt` naming already done.)
2. **Config-driven paths** — `roots.py` → read `config.toml` / derive from cwd, instead of the hardcoded `SQUID/data`. Global cooldowns dir is configurable.
3. **A single entry point** — `python -m catalog build|plot|cooldown|show` (thin wrapper over the existing scripts) so there's one command.
4. **`catalog init`** — scaffold a user's `_catalog\` (config) + confirm the global registry path.
5. **Generic CLAUDE.md + README** generators for the data root.
6. Keep the full test suite green; add tests for the registry loader + config resolution.

## Non-goals (YAGNI)
- No cross-user / lab-wide catalog (confirmed not needed).
- No Postgres / server / file-watcher yet (later phase).
- No change to AutoSQUID, the analyzers, or the figure/markdown conventions.

## Decided: run inside the user folder
Claude Code is run **inside each `…\<user>\` folder** — the folder is the identity (cwd → user, raw root, DB). `_engine\` is shared, `pip install -e`'d so `catalog` imports from anywhere; the data-root `CLAUDE.md` is read as a parent of the user folder. (Running from `_engine\` and picking a user via prompt/config remains a documented fallback, not the primary path.)
