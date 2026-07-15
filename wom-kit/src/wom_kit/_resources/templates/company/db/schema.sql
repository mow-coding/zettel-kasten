-- WOM-kit SQLite schema v0.1

CREATE TABLE IF NOT EXISTS archives (
  archive_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  principal_id TEXT NOT NULL,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS zettels (
  zettel_id TEXT PRIMARY KEY,
  archive_id TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  path TEXT NOT NULL,
  created_at TEXT,
  updated_at TEXT,
  visibility_scope TEXT,
  provenance_json TEXT
);

CREATE TABLE IF NOT EXISTS objects (
  object_id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  logical_key TEXT NOT NULL,
  mime TEXT,
  size_bytes INTEGER,
  provenance_json TEXT
);

CREATE TABLE IF NOT EXISTS derived_texts (
  derived_text_id TEXT PRIMARY KEY,
  source_object_id TEXT NOT NULL,
  derivation_kind TEXT NOT NULL,
  review_status TEXT NOT NULL,
  language TEXT,
  text_logical_key TEXT NOT NULL,
  text_sha256 TEXT NOT NULL,
  provenance_json TEXT
);

CREATE TABLE IF NOT EXISTS object_locations (
  object_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  location_ref TEXT NOT NULL,
  availability TEXT,
  PRIMARY KEY (object_id, provider, location_ref)
);

CREATE TABLE IF NOT EXISTS zettel_assets (
  zettel_id TEXT NOT NULL,
  object_id TEXT NOT NULL,
  role TEXT,
  label TEXT,
  PRIMARY KEY (zettel_id, object_id, role)
);

CREATE TABLE IF NOT EXISTS zettel_facets (
  zettel_id TEXT NOT NULL,
  facet_key TEXT NOT NULL,
  facet_value TEXT NOT NULL,
  PRIMARY KEY (zettel_id, facet_key, facet_value)
);

CREATE TABLE IF NOT EXISTS edges (
  edge_id TEXT PRIMARY KEY,
  from_id TEXT NOT NULL,
  to_id TEXT NOT NULL,
  type TEXT NOT NULL,
  visibility TEXT,
  provenance_json TEXT
);

CREATE TABLE IF NOT EXISTS views (
  view_id TEXT PRIMARY KEY,
  archive_id TEXT NOT NULL,
  name TEXT NOT NULL,
  path TEXT NOT NULL,
  query_json TEXT
);

CREATE TABLE IF NOT EXISTS workpacks (
  package_id TEXT PRIMARY KEY,
  source_archive TEXT NOT NULL,
  target_archive TEXT,
  mode TEXT NOT NULL,
  purpose TEXT,
  expires_at TEXT,
  provenance_json TEXT
);
