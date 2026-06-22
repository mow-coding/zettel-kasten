# Tiro Import Plan

Status: v0.3.137 read-only Tiro meeting transcript import planning

`archive tiro-import-plan` is the first WOM-kit entry point for meeting notes
created by Tiro-style recording/transcription tools.

It is a planning gate, not an importer. It reads an archive-internal, reviewed
JSON manifest and reports whether the meeting metadata, speaker turns,
timestamps, transcript segments, confidence values, and optional audio objet
reference are shaped well enough for later human-reviewed derived-text capture
and zet drafting.

## Command

```powershell
archive tiro-import-plan <archive-root> --manifest workbench/tiro-meeting.sample.json --dry-run --format json
```

MCP exposes the same read-only surface as:

```text
tiro_import_plan
```

The manifest path must be archive-relative. Do not pass a local absolute path,
download path, account id, token, or private provider URL as a command value.

## Manifest Shape

The v0.1 manifest is a JSON object:

```json
{
  "schema": "wom-tiro-import-manifest/v0.1",
  "source": "tiro",
  "meeting": {
    "external_id": "tiro:note:fake-weekly-20260622",
    "title": "Fake weekly archive review",
    "started_at": "2026-06-22T09:00:00+09:00",
    "ended_at": "2026-06-22T09:30:00+09:00",
    "duration_seconds": 1800,
    "place": "online",
    "source_url": "https://example.invalid/tiro/fake-weekly-20260622",
    "language": "en-US"
  },
  "participants": [
    {"speaker_id": "speaker:facilitator", "display_name": "Facilitator"}
  ],
  "segments": [
    {
      "segment_id": "seg-0001",
      "speaker_id": "speaker:facilitator",
      "start_ms": 0,
      "end_ms": 8200,
      "text": "Reviewed transcript text",
      "confidence": 0.98
    }
  ],
  "audio": {
    "source_ref": "tiro-audio:fake-weekly-20260622",
    "mime": "audio/m4a",
    "duration_seconds": 1800
  }
}
```

The public fake archive includes a safe sample at:

```text
workbench/tiro-meeting.sample.json
```

## Output Contract

The plan reports structure, not private meeting content:

- meeting metadata presence such as title, time, duration, place, source URL,
  and language,
- participant and speaker counts,
- transcript segment count, timestamp unit, confidence count, empty-text count,
  and whether turns remain sorted,
- whether an audio object id or objet ref is present,
- whether that audio object id is already visible in
  `objects/manifests/files.jsonl`,
- safe `source_refs_for_draft` values when the manifest is valid.

The output does not echo meeting titles, participant display names, transcript
segment text, source URLs, audio filenames, local absolute paths, account ids,
emails, tokens, or secret values.

## Safety Boundary

This command is read-only:

- it writes no files,
- it calls no Tiro API,
- it starts no OAuth flow,
- it reads no audio bytes,
- it performs no ASR,
- it writes no derived text,
- it drafts no zets,
- it mints nothing.

The next safe step after a clean plan is still human review. Audio bytes should
be captured through the existing objet-capture flow, and transcript text should
be registered as derived text only through a separate approval-gated capture
path.

## Why This Exists

Meeting notes are neither ordinary Markdown imports nor plain attachments. A
useful WOM record needs the meeting time, source identity, speaker turns,
timestamps, transcript text, confidence, and original audio object to stay tied
together. This planning command makes that shape visible before any durable
write happens.
