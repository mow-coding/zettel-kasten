# Decision Log: Retire MOW Harness Integration Guidance

Date: 2026-08-08
Status: accepted for v0.3.306
Supersedes: `archive-infra-decision-log-2026-07-16-v03253-mow-harness-compatibility.md`

## Decision

Retire WOM's optional MOW Harness recommendation, compatibility guide, external
repository link, and install/update/activation guidance. WOM must not advertise
or imply a supported integration with the retired external project.

Retain `/collab/` and legacy `/.mow-harness/` as generic, fail-closed local-state
quarantine patterns. Add a generic source alias for active artifact-hygiene
code while preserving the exact historical machine-output and import label.
Default archive-root Doctor checks, source discovery, restore copying, and
artifact-hygiene recursion must exclude both roots; the artifact checker also
refuses them as direct targets. Keep them outside default WOM discovery,
backups, and public Git surfaces.

## Evidence

- The reported MOW Harness repository and local standalone checkout are no
  longer accessible or present as of this decision.
- WOM has no MOW Harness package dependency, import, subprocess invocation, MCP
  surface, schema, bundled CLI, receipt parser, or UI.
- The former integration consisted of public guidance plus defensive namespace
  isolation.
- Existing local folders may contain prompts, mailboxes, installer metadata,
  or secrets. Removing the isolation would increase disclosure risk even though
  the external product is retired.

## Consequences

- Active onboarding and public navigation no longer recommend MOW Harness or
  link to its unavailable repository.
- No archive schema, zet, objet, receipt, index, provider, or canonical record
  changes; no archive migration is required.
- Old `.mow-harness/` bytes are not WOM records. Default archive-root discovery
  and restore do not descend into or copy them, and WOM does not delete them.
  A separate explicit file-selection command is not a retired-tool cleaner and
  must not be pointed at either quarantine root.
  Removing a verified local installation residue is an explicit operator-side
  cleanup outside archive mutation.
- `collab/` remains a generic local coordination/history boundary; durable
  project decisions still belong in normal project records.
- Historical changelog, release note, and superseded decision evidence remain
  available as history and are not presented as current integration guidance.
