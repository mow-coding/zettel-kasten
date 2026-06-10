---
id: zet_20260519_fake_family_memory
title: Fake shared family memory
created_at: "2026-05-19T09:00:00+09:00"
updated_at: "2026-05-19T12:00:00+09:00"
archive_id: archive:personal:fake-life
status: canonical
kind: record_note
facets:
  domain: family
  record_type: memory
  subject_kind: household
  event_type: daily_life
  sharing_status: family_shared
assets:
  - object_id: sha256:9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647
    role: source_memory
    label: Fake family memory original
edges:
  - type: shared_with
    target: archive:family:fake-household
    visibility: shared_record
provenance:
  created_by: person:fake-user
  created_in: archive:personal:fake-life
  source: fake_sample
  derived_from: []
visibility:
  scope: family_shared
  allowed_archives:
    - archive:family:fake-household
  source_visibility: shared
promotion:
  stage: promoted
  reviewed_by: person:fake-user
  reviewed_at: "2026-05-19T12:00:00+09:00"
  checklist_version: zettel-promotion/v0.2
---

# Fake shared family memory

This zettel represents a record that can be shared with a family archive.

The same original may be physically replicated on multiple PCs, but it keeps one logical `object_id`.
