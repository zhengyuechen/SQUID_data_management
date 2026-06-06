-- Projection catalog: disk owns the bytes; these tables own queryable metadata + lineage.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sample (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, formula TEXT, notes TEXT);

CREATE TABLE IF NOT EXISTS instrument (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, kind TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS cooldown (
  id INTEGER PRIMARY KEY,
  sample_id INTEGER REFERENCES sample(id),
  label TEXT UNIQUE NOT NULL,
  fridge TEXT, start_date TEXT, end_date TEXT,
  f0_per_volt REAL NOT NULL,           -- per-cooldown calibration factor, AS DATA
  s_bias_ma REAL,
  setup_notes TEXT,                      -- the human-readable SETUP block (restore values + V-Phi tuning)
  logbook_path TEXT);                    -- link to cooldowns/<label>.md (the source of truth)

-- Free-text lab-notebook entries per cooldown (setup / calibration / run), parsed from the logbook.
CREATE TABLE IF NOT EXISTS cooldown_note (
  id INTEGER PRIMARY KEY,
  cooldown_id INTEGER NOT NULL REFERENCES cooldown(id),
  phase TEXT,                            -- setup | calibration | run | ...
  note TEXT,
  ord INTEGER);

CREATE TABLE IF NOT EXISTS raw_measurement (
  id INTEGER PRIMARY KEY,
  instrument_id INTEGER REFERENCES instrument(id),
  sample_id INTEGER REFERENCES sample(id),
  cooldown_id INTEGER REFERENCES cooldown(id),
  path TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
  acquired_date TEXT, acquired_time TEXT,
  temp_mK REAL,                          -- normalized from the FILENAME (not the folder)
  scan_interval_us REAL, n_points INTEGER, run_index INTEGER,
  duration_s REAL, fs_hz REAL,
  integrity_pass INTEGER NOT NULL,       -- 1/0 from AutoSQUID is_surge_spec
  integrity_reason TEXT,                 -- is_surge_spec's reason string
  outcome TEXT,                          -- acquisition's own verdict (filename suffix / experiment_log): CLEAN/JUMP/SURGE/...
  n_resets INTEGER,                      -- from experiment_log
  t_start_K REAL, t_end_K REAL,          -- from experiment_log
  jump_time_s REAL,                      -- from experiment_log
  usable_s REAL,                         -- usable (pre-jump) duration: full for clean, the prefix for jump/surge, NULL for stuck/dead
  mean_V REAL, std_V REAL,
  temp_sidecar_path TEXT,
  cooldown_resolved INTEGER NOT NULL,    -- 1 if cooldown/calibration resolved from header date, else 0
  size_bytes INTEGER, mtime_ns INTEGER, content_hash TEXT, crawled_at TEXT);

CREATE TABLE IF NOT EXISTS derived_product (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,                    -- a NEW analysis is a new value here; no schema change
  params TEXT, scalars TEXT,             -- JSON
  artifact_path TEXT, result_folder TEXT, code_ref TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS product_input (
  derived_product_id INTEGER NOT NULL REFERENCES derived_product(id),
  raw_measurement_id INTEGER NOT NULL REFERENCES raw_measurement(id),
  role TEXT,
  PRIMARY KEY (derived_product_id, raw_measurement_id));

CREATE INDEX IF NOT EXISTS ix_raw_temp      ON raw_measurement(temp_mK);
CREATE INDEX IF NOT EXISTS ix_raw_cooldown  ON raw_measurement(cooldown_id);
CREATE INDEX IF NOT EXISTS ix_raw_integrity ON raw_measurement(integrity_pass);
CREATE INDEX IF NOT EXISTS ix_raw_outcome   ON raw_measurement(outcome);
CREATE INDEX IF NOT EXISTS ix_prod_kind     ON derived_product(kind);
CREATE INDEX IF NOT EXISTS ix_pi_raw        ON product_input(raw_measurement_id);
