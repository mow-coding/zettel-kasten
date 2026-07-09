# Archive Infra Decision Log - v0.3.202 Operator Vocabulary Translation

Date: 2026-07-09
Release: v0.3.202

## Context

After adding the `ai-start-here` signpost in v0.3.201, the next gap was the
human-facing language an AI operator should use while helping a beginner run
WOM. Existing translation support covered edge types, connection mechanisms,
lifecycle fragments, and git/infrastructure terms, but not the broader everyday
WOM operator vocabulary.

## Decision

Add an `operator_vocabulary` topic to `archive ai-response-concept-guide`.

The topic groups common WOM operator terms by archive entry, knowledge records,
evidence layers, actions/checks, connections, and provider/secret safety. Each
entry carries a Korean phrase and a "speak like this" hint for human-facing
answers.

## Consequences

- AI operators have a single read-only lookup for beginner-facing WOM wording.
- Machine terms remain stable and unchanged in JSON, receipts, and CLI command
  names.
- The guide remains advisory: it shapes human-facing prose but does not enforce
  output wording.
