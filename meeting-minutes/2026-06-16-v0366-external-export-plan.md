# Meeting Minutes - v0.3.66 External Export Plan

Date: 2026-06-16

## Context

Remaining field feedback after the version truth-source and R2 setup-guide work
included a large-media export trap: a user may want text, but a broad provider
export can pull large uploaded files, attachments, images, audio, or video into
the local download.

## Decision

v0.3.66 adds a read-only pre-export planning command before any provider export
automation or import.

## Implemented

- Added `archive external-export-plan`.
- Added source choices for Notion, Google Drive, and generic workspace exports.
- Added export goals and media policies so an AI helper can ask the human about
  scope before pressing provider export buttons.
- Added risk classification and `stop_and_split_media_before_export` guidance.
- Added documentation, changelog, release notes, capability matrix coverage, and
  CLI tests.

## Safety Boundary

The new command:

- starts no provider export,
- calls no provider API,
- starts no OAuth,
- reads no files or media bytes,
- downloads no attachments,
- writes no archive files,
- echoes no provider URLs, local paths, filenames, account ids, emails, tokens,
  or secret values.
