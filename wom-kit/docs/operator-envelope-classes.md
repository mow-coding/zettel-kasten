# Operator Envelope Classes

Status: v0.3.156 operator envelope class fields checkpoint

v0.3.156 begins the command-output retrofit promised by the operation status,
input provenance, secret-signal, and AI response contract work.

Core read-only operator commands now expose these top-level fields:

- `status_class`
- `input_provenance_class`
- `secret_signal_class`
- `operator_envelope`

The nested `operator_envelope` object carries schema
`wom-kit/operator-envelope-classes/v0.1` and repeats the same class fields for
operators that prefer a single grouped object.

## First Commands Covered

- `archive operation-status-taxonomy --dry-run`
- `archive input-provenance-taxonomy --dry-run`
- `archive secret-signal-taxonomy --dry-run`
- `archive ai-response-contract --dry-run`

## Initial Class Values

For these read-only safety commands:

- `status_class` is `preview` when the command is valid, or `blocked` when its
  own precondition blocks execution.
- `input_provenance_class` is `caller_supplied` because the archive root is
  supplied by the caller and then validated before use.
- `secret_signal_class` is `concept_word` because these commands return built-in
  safety vocabulary and safe references, not secret values.

## Safety Boundary

This retrofit does not make commands read more material or write more files.
The covered commands keep their existing privacy guards: no archive body text,
sample values, providers, network checks, local absolute paths, tokens, secret
values, or writes.

## Still Future

- Extending class fields to more JSON-producing commands.
- Using more specific input provenance classes for commands whose inputs come
  from receipts, generated indexes, or local manifests.
- Adding item-level class fields for batch commands with mixed outcomes.
