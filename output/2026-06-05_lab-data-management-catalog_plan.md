# Lab Data-Management Catalog — Design & Plan

**Date:** 2026-06-05
**Status:** Design approved (brainstorm complete) — ready to turn into an implementation plan
**Author context:** Ran's Lab (condensed-matter). SQUID magnetometry on YbZn₂GaO₅ (a QSL candidate), plus XRD, dilution-fridge, and DFT work, currently spread across separate lab computers and a Google Drive.

---

## 1. Vision (the goal in one paragraph)

The lab runs several instruments — XRD, the PCS102 SQUID on the dilution fridge, and related fridge hardware — each on its own computer, with files stored separately on a cloud drive. The vision is a **central server-rack machine, wired to all the instrument PCs, that holds a SQL database of every measurement's metadata and can run analysis automatically** — e.g. produce a refined XRD figure while a scan is being taken, or turn one raw SQUID trace into its time-series, PSD, and temperature-overlay plots. Because the same raw data feeds many different derived figures, the database stores the **metadata and the lineage** (what was measured, when, and what was computed from it), while the **raw bytes stay on disk**. A deterministic analysis engine produces the routine products; a local LLM sits on top later for natural-language queries and novel analysis.

This document designs that system, scopes a **zero-risk prototype that can be proven now** on the existing SQUID data, and lays out the path to the central-server end state.

---

## 2. The problem: a primitive database already exists — it is just scattered

The lab's conventions already do a database's job, badly. The pieces exist; nothing ties them together.

| Already acting like a DB                         | What it is                                       | What's missing                                                        |
| ------------------------------------------------ | ------------------------------------------------ | --------------------------------------------------------------------- |
| `DAQ_<τ>_<T>_<npts>_<run>.txt` filenames      | de-facto primary key (a parseable row)           | no cross-folder query                                                 |
| `experiment_log.txt` (TSV, append-only)        | one row per acquisition — the operational truth | local to one folder, not indexed                                      |
| `psd_cache_index.csv` + `psd_cache.npz`      | a materialized derived-product table             | does not span cooldowns                                               |
| `squid_calibration.py` (0.837 / 0.834 / 0.762) | per-cooldown Φ₀/V factors                      | **hardcoded in Python** — adding a cooldown means editing code |
| result-folder convention +`summary/*.md`       | per-run provenance namespace                     | no lineage linking raw → derived                                     |

There is **no SQLite, no manifest, nothing spanning folders** anywhere in the workspace. Today "all 33 mK sample traces across cooldowns" means a hand-rolled directory walk + filename regex in every notebook. The job is **not** to invent provenance from scratch — it is to consolidate what the conventions already encode into one queryable index.

### The vision is four subsystems with a hard dependency order

```
                    ┌─────────────────────────────────┐
   PROVABLE NOW →   │ 1. SQL metadata CATALOG (index) │  ← the foundation everything needs
                    └─────────────────────────────────┘
                          ↑            ↑            ↑
              2. Sync         3. On-acquisition   4. LLM auto-plotting
              (PC→server)     real-time analysis  (1 raw → PSD/TS/overlap)
              [infra/IT]      [hard: live XRD]    [needs the catalog to walk]
```

Subsystems 2–4 are the exciting parts, but none of them work without #1, and #1 is the only piece that is zero-risk to prototype today.

---

## 3. Scope decisions (settled during brainstorming)

| Decision                          | Choice                                                                 | Rationale                                                                                                                                                                                                                               |
| --------------------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Deliverable**             | Plan document**+** working proof                                 | "Proven now" — a vision doc the lab can react to, anchored by a prototype that actually queries real traces                                                                                                                            |
| **Prototype catalog scope** | **SQUID-only, go deep**                                          | Richest metadata, the dependency hub, validates against `psd_cache_index.csv`. The *schema* still generalizes — adding XRD later is an `INSERT`, not a rewrite                                                                   |
| **LLM role**                | **Deterministic engine + LLM on top**                            | Routine plots are pure functions of (raw trace + calibration); an LLM there only adds nondeterminism + a GPU dependency. LLM earns its place at the*query* boundary and for *novel* analysis. The provable-now slice needs no model |
| **Architecture**            | **Projection catalog — disk owns truth**                        | Matches AutoSQUID's disk-first/resume model + the byte-identical PCS102 invariant. The catalog is a rebuildable projection of disk; delete it and re-crawl to regenerate                                                                |
| **Extensibility**           | **Open/closed** — new analysis = new analyzer, no schema change | Direct requirement: "I want to add more analysis and the SQLite should index it too"                                                                                                                                                    |
| **Analysis policy**         | **Human-editable Markdown playbook**                             | Policy (what runs, what to change) is separate from mechanism (Python that knows how). Lab members edit the playbook without touching code                                                                                              |

### Disk vs. DB split (the rule)

**Disk owns the bytes; the DB owns the queryable metadata + the lineage.** The test for any value: *could you put it in a spreadsheet cell and sort a column by it?* If yes → DB. If it is a whole curve or an image → file on disk, DB holds the path.

| In the DB (small, queryable)                      | On disk (large, pointed to)         |
| ------------------------------------------------- | ----------------------------------- |
| date, time, τ, temperature (mK), # points, run # | the raw `DAQ_*.txt` voltage array |
| mean voltage, noise std, RMS, peak-to-peak        | the full PSD curve (an array)       |
| integrity verdict, jump_V, frozen-fraction        | the `TEMP_*.csv` sidecar          |
| Φ₀/V calibration factor (one per cooldown)      | figures (`.png` / `.pdf`)       |
| named band-integrated powers (one number each)    | denoised traces (arrays)            |
| a `path` + `params` for every derived product |                                     |

> **Note:** the PSD exponent α is deliberately **not** a catalog field. For a QSL the noise PSD is predicted ~white; the fingerprint is the temperature dependence, not a 1/f exponent. α is not metadata for this system.

---

## 4. Design §1 — The schema (6 tables)

```
┌─────────┐     ┌──────────┐     ┌────────────┐
│ sample  │────<│ cooldown │     │ instrument │      lookup tables
└─────────┘     └──────────┘     └────────────┘   (cooldown holds the Φ₀/V factor — as DATA)
                      │  │              │
                      ▼  ▼              ▼
              ┌──────────────────────────────┐
              │      raw_measurement         │   one row per raw file on disk
              │  path, date, temp_mK, τ, npts│   (DB = metadata; bytes stay on disk)
              │  integrity_pass, jump_V,     │
              │  mean_V, std_V, fail_tag     │
              └──────────────────────────────┘
                      │
                      │  product_input  (many-to-many link)
                      ▼
              ┌──────────────────────────────┐
              │      derived_product         │   one row per analysis output
              │  kind, params(JSON),         │   NEW analysis = new `kind` string,
              │  scalars(JSON), artifact_path│   NO schema change
              └──────────────────────────────┘
```

### Table definitions

**`sample`** — the physical specimen.
`id` PK · `name` (e.g. `YbZn2GaO5`, `Sapphire-background`) · `formula` · `notes`

**`cooldown`** — one fridge cooldown; **holds the calibration factor as data**.
`id` PK · `sample_id` → sample · `label` (e.g. `Dec2025-YbZn`) · `fridge` · `start_date` · `end_date` · `phi0_per_volt` (the Φ₀/V factor: 0.837 / 0.834 / 0.762) · `setup_notes` (bias, PFL gain, lock config)

**`instrument`** — the measuring device (present from day one so the schema is lab-wide).
`id` PK · `name` (e.g. `PCS102-SQUID`, `Rigaku-MiniFlex`) · `kind` (`squid`, `xrd`, …)

**`raw_measurement`** — one row per raw file on disk; the metadata projection of that file.
`id` PK · `instrument_id` → instrument · `sample_id` → sample · `cooldown_id` → cooldown · `path` (UNIQUE, absolute) · `filename` · `acquired_date` · `acquired_time` · `temp_mK` (normalized numeric) · `scan_interval_us` · `n_points` · `run_index` · `duration_s` (derived) · `fs_hz` (derived) · `fail_tag` (JUMP/SURGE/RAIL/BADBASE or NULL) · `integrity_pass` · `jump_V` · `frozen_frac` · `mean_V` · `std_V` · `temp_sidecar_path` · `content_hash` (idempotent upsert + change detection) · `crawled_at`

**`derived_product`** — one row per analysis output; the generic, open/closed table.
`id` PK · `kind` (string — a new analysis is a new value here) · `params` (JSON) · `scalars` (JSON, queryable) · `artifact_path` · `result_folder` · `code_ref` (e.g. `plot_psd@autosquid`) · `created_at`

**`product_input`** — the lineage link (many-to-many).
`derived_product_id` → derived_product · `raw_measurement_id` → raw_measurement · `role` (e.g. `primary`, `overlay_member`) · PK (`derived_product_id`, `raw_measurement_id`)

**Indexes:** `raw_measurement(temp_mK)`, `raw_measurement(cooldown_id)`, `raw_measurement(integrity_pass)`, `derived_product(kind)`, `product_input(raw_measurement_id)`.

### What the schema buys, traced to requirements

| Requirement                                | Schema mechanism                                                             |
| ------------------------------------------ | ---------------------------------------------------------------------------- |
| "disk owns raw data, DB has metadata"      | `raw_measurement` stores `path` + parsed fields; never the voltage array |
| "add more analysis, SQLite indexes it too" | new analyzer → new `kind` in `derived_product`; zero schema change      |
| "I'd know what raw data made a figure"     | `product_input` link table, queryable **both** directions            |
| "all data around 14 mK"                    | normalized numeric `temp_mK` column → `WHERE temp_mK BETWEEN 13 AND 15` |
| per-cooldown calibration (today hardcoded) | `cooldown.phi0_per_volt` — adding a cooldown is an `INSERT`             |

---

## 5. Design §2 — The crawler / ingest (read-only)

A `crawl()` that walks existing files and populates the catalog — **opening files, never writing them.**

For each `DAQ_*.txt`:

1. **Parse the filename** → τ, T, npts, run, fail_tag.
2. **Read the PCS102 header** via the existing `load_pcs102_data()` (never hand-rolled) → DATE, TIME, DATAPOINTS, SCANINTVAL.
3. **Resolve sample + cooldown** from the folder path (sample/cooldown live in the path, e.g. `SAMPLE-YbZnGaO4/SAMPLE_38mK/`).
4. **Normalize temperature** → numeric `temp_mK` (handles `38mK`, `1p2K`, `4p5K`).
5. **Run the mandatory integrity gate** `daq_integrity.check_daq_jump()` → `integrity_pass`, `jump_V`, `frozen_frac`. *(This is where the MANDATORY gate is enforced — every trace, at ingest.)*
6. **Compute cheap scalars** (mean_V, std_V — one pass).
7. **UPSERT** a `raw_measurement` row keyed on `path` + `content_hash` → idempotent.

**Bootstrap once:** migrate the hardcoded factors in `squid_calibration.py` (0.837 / 0.834 / 0.762) into `cooldown` rows. After that, calibration lives in the DB as data, and `squid_calibration.py` can read from it.

**Properties:**

| Property              | Why it matters                                                                                             |
| --------------------- | ---------------------------------------------------------------------------------------------------------- |
| Read-only on raw data | the crawler can never corrupt a trace — it only reads                                                     |
| Rebuildable           | delete the `.sqlite`, re-run `crawl()`, get the identical DB — disk is truth, catalog is a projection |
| Incremental           | a second crawl only touches new/changed files (mtime/hash)                                                 |

**Validation gate (ground-truth check):** regenerate the existing `psd_cache_index.csv` (84 rows) **from a DB query** and diff. Row-for-row match proves the catalog is faithful to the hand-built index.

---

## 6. Design §3 — The analyzer registry + dispatcher

An **analyzer** is a tiny unit with three parts:

```
analyzer "psd_welch":
   needs   : one CLEAN SQUID trace
   run(inputs, params) -> (artifact_path, scalars)
       reads raw via the loader, pulls the cooldown's Φ₀/V factor,
       computes, writes the .npz/.png into results/<ts>_<desc>/,
       returns {std, white_level, line_60Hz, ...} + the file path
```

- **Registry** — `kind → analyzer`. **Adding a new analysis = write one analyzer + register it.** No schema change, no catalog change.
- **Dispatcher** — `run_analysis(kind, query, params)`:
  1. resolves the query against the catalog (e.g. *all ~14 mK traces that passed integrity*),
  2. pulls each trace's calibration factor from its `cooldown` row,
  3. calls the analyzer,
  4. writes the `derived_product` row + `product_input` links — lineage recorded automatically.
- **Reuse, don't reinvent** — the first three analyzers are thin wrappers over AutoSQUID's existing `plot_psd`, `plot_run`, `plot_overlay`.
- **Caching** — before running, check whether a `derived_product` with the same (kind, parent-set, params) exists → skip / return cached.

**Open/closed in physical form:** the catalog and dispatcher are *closed* (never edited); analyses are *open* (added freely). The moment an analyzer returns `(path, scalars)`, the generic `derived_product` row makes it queryable — "the SQLite indexes my new analysis too" is a consequence of the shape, not a bolted-on feature.

### The analysis playbook (policy, not mechanism)

A human-editable `analysis_playbook.md` declares **what** runs and **what to change** — separate from the Python that knows **how**:

```markdown
# Analysis Playbook

## SQUID traces
- Every CLEAN trace → time-series plot + PSD (Welch, nperseg = 65536)
- Group traces by temperature (±10 mK) → temperature-overlay plot
- Report band-power for: 0.1–1 Hz, 1–10 Hz, 10–100 Hz
- Skip any trace that fails the integrity gate

## How to change things
- Add a band → add one line under "Report band-power"
- New sample/cooldown → add its Φ₀/V factor to the cooldown table
- Stop overlays below 20 mK → edit the grouping line
```

A student edits the playbook to add a band and the next dispatch includes it — no code review, no merge. The playbook has a **small machine-readable core** the dispatcher parses deterministically now, wrapped in human prose that is also what the LLM reads later. One file serves humans, the parser, and the model.

---

## 7. Design §4 — Deployment: Google Drive now → central server later

Same schema and same code throughout; only *where the disk lives* changes.

| Phase                      | DB engine                                          | Runs on                                                     | What changes                                                                                       |
| -------------------------- | -------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **0 — now**         | SQLite (one file, stdlib `sqlite3`, no new deps) | laptop, reading Drive-synced files                          | nothing to set up — prove it today                                                                |
| **1 — server rack** | Postgres (identical schema, engine swap)           | central machine; instrument PCs keep writing files as today | crawler becomes a scheduled job or a file-watcher daemon —*same dispatcher*, now long-running   |
| **2 — LLM layer**   | (unchanged)                                        | server                                                      | LLM added on top: English→query, reads the playbook to pick analyzers, drafts the summary `.md` |

The instrument PCs **never change** — they keep writing files (AutoSQUID disk-first), preserving the byte-identical PCS102 invariant and the resume model. The server only ingests + analyzes. Disk owns the bytes at every phase; the DB only ever holds metadata + paths. The deterministic engine (Phases 0–1) works with **no LLM**; the LLM is a convenience layer added last.

---

## 8. Design §5 — What we build to *prove it now*

A focused slice, living in `data_management_plan/` (typed-subfolder layout per `organize_project.py`):

| # | Artifact                                               | What it is                                                                                                                        |
| - | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| 1 | `schema.sql`                                         | the 6 tables + indexes                                                                                                            |
| 2 | `crawl.py`                                           | read-only ingest — uses `load_pcs102_data()` + `daq_integrity`, seeds `cooldown`/calibration from `squid_calibration.py` |
| 3 | `registry.py` + 3 analyzers                          | thin wrappers over `plot_psd` / `plot_run` / `plot_overlay`                                                                 |
| 4 | `dispatch.py`                                        | `run_analysis(kind, query, params)` → writes `derived_product` + lineage into `results/<ts>_<desc>/`                       |
| 5 | `analysis_playbook.md`                               | the human-editable policy file                                                                                                    |
| 6 | demo notebook (from a `build_*.py` in `builders/`) | the step-by-step proof                                                                                                            |

The **demo notebook** (one cell per stage, on the data dropped into `SQUID/data`):

1. **Crawl** → display the catalog (row counts, sample `raw_measurement` rows, the seeded cooldown/calibration table)
2. **Query** → *"all ~14 mK traces that passed integrity"* → show the returned rows
3. **Dispatch** PSD + time-series → show the figures
4. **Lineage both ways** → pick a figure → trace to its raw file(s); pick a raw trace → list everything derived from it
5. **Validate** → regenerate `psd_cache_index.csv` from the DB and diff → row-for-row match
6. **Edit the playbook** (add a band) → re-dispatch → new output appears with no code change

### Verifiable success criteria

- Crawl is **idempotent** — run twice → identical row counts
- DB-generated index **==** existing `psd_cache_index.csv`
- A temperature query returns **exactly** the expected traces
- Lineage **round-trips** in both directions (figure → raw, raw → figure)
- A **playbook edit** changes the output with **zero** code edits

---

## 9. Non-goals (YAGNI — explicitly out of scope for the prototype)

- No live file-watcher daemon (Phase-2; the prototype crawls on demand).
- No Postgres / server deployment (Phase-1; the prototype is SQLite on the laptop).
- No LLM (Phase-2; the prototype is fully deterministic).
- No XRD / fridge ingest (the schema supports it; the prototype ingests only SQUID).
- No change to acquisition or to how instrument PCs write files.
- No storing of raw arrays, PSD curves, or figures in the DB — those stay on disk.

---

## 10. Invariants honored & risks

**Invariants (from the lab's CLAUDE.md, all preserved):**

- Mandatory DAQ integrity gate — enforced at ingest, recorded on every row.
- Per-cooldown (not per-temperature) calibration — now data in the `cooldown` table.
- Byte-identical PCS102 — the crawler never writes raw files.
- Result-folder + summary conventions — derived products land in `results/<ts>_<desc>/`.
- `.pptx` files are deliverables — never touched.

**Risks & mitigations:**

- *Temperature-notation drift* (`38mK` vs `1p2K`) → normalization is an explicit ingest step; surface any unparseable label rather than guessing.
- *Sample/cooldown inferred from folder path* → seed a small, reviewed cooldown table; flag any trace whose folder doesn't resolve.
- *Playbook over-engineering* → keep the machine-readable core minimal; prose for humans/LLM.
- *Google Drive sync latency* → the prototype is on-demand, not live, so sync races don't matter yet.

---

## 11. Future phases (roadmap beyond the proof)

1. **XRD ingest** mirroring the SQUID schema (`.rasx` XML → same `raw_measurement` + `derived_product`) — proves the schema is instrument-agnostic.
2. **File-watcher daemon** — tail new `DAQ_*.txt`, auto-gate, insert, flag FAILs (Phase-2 wrapper around the same dispatcher).
3. **Postgres migration** + server deployment connected to the instrument PCs.
4. **LLM layer** — natural-language query → SQL; playbook-driven auto-dispatch on new data; auto-drafted summary `.md`.
5. **On-acquisition analysis** (e.g. refined XRD while scanning) — the hardest piece, built last on the proven foundation.

---

## 12. References (existing code this builds on)

- `SQUID/denoising/Trial-with-Spectral-Substraction/data_loader_pcs102.py` — `load_pcs102_data()` (the only sanctioned PCS102 reader)
- `SQUID/denoising/Trial-with-Spectral-Substraction/daq_integrity.py` — `check_daq_jump()` (the mandatory gate)
- `SQUID/denoising/Trial-with-Spectral-Substraction/squid_calibration.py` — the per-cooldown Φ₀/V map to migrate into the `cooldown` table
- `SQUID/automation/` (AutoSQUID) — `plot_psd`, `plot_run`, `plot_overlay`, the `Config` pattern, `experiment_log.txt` / `action_log.txt` ledgers, `scan_indices()` resume primitive
- `SQUID/data/` — the raw corpus the crawler ingests; validation target `psd_cache_index.csv`
- `Ran's Lab/projects/organize_project.py` — the typed-subfolder layout enforcer
