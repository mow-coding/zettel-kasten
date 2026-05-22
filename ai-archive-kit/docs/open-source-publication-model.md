# Open Source Publication Model

Status: planning baseline
Date: 2026-05-22

This project is intended to be released as open source.

The public project should explain the thinking, blueprint, schemas, logic, reference research, implementation plans, and work logs behind `zettel-kasten` and `zet`.

Actual user archives, source data, credentials, private receipts, provider tokens, and local runtime state must remain private by default.

## 1. Core Principle

Open source the system.

Keep each user's archive private.

```text
public:
  code
  schemas
  specs
  reference implementation
  planning documents
  research notes
  tests
  templates
  fake/example archives
  implementation plans
  work logs

private:
  real user source data
  real zets
  real object manifests
  real receipts
  real source maps
  secrets
  provider tokens
  local paths
  private AI conversation transcripts
```

## 2. Why This Project Should Be Open Source

The user wants the project to be public so that people can:

- understand the intent behind the system,
- inspect the schema and logic,
- criticize the design,
- suggest better standards and references,
- implement compatible tools,
- adapt the system for their own archives,
- verify that the system does not require a central company server.

The project philosophy is itself aligned with openness:

```text
The protocol and tools can be shared.
The user's archive remains theirs.
```

## 3. What Can Be Open

The following can be published safely when checked for accidental secrets or private data:

- source code,
- CLI implementation,
- MCP server implementation,
- schema files,
- action/policy/rule files,
- fake example archives,
- product blueprint,
- implementation research,
- implementation plans,
- work logs,
- architecture decision records,
- security model,
- threat model,
- onboarding docs,
- templates.

## 4. What Must Not Be Open

Never publish:

- `.env` files,
- API tokens,
- OAuth refresh tokens,
- local keyring files,
- private object manifests from real archives,
- real source maps containing private paths,
- private AI conversation transcripts,
- private zets,
- private receipts,
- Notion/Google Drive export data from real workspaces,
- provider account IDs if they identify private infrastructure,
- local absolute paths that reveal personal information.

The local project root may contain hidden provider login files; they must be treated as sensitive and excluded before any GitHub publication.

## 5. License Direction

Before publication, choose an explicit license.

Recommended default:

```text
Code: Apache-2.0 or MIT
Documentation/specs: CC BY 4.0 or CC BY-SA 4.0
```

Reasoning:

- MIT is simple and permissive.
- Apache-2.0 is permissive and includes an explicit patent grant.
- CC BY 4.0 is suitable for documentation and conceptual writing that should be reused with attribution.
- CC BY-SA 4.0 is suitable if derivative docs/specs should remain similarly shared.

Do not publish without a license if the goal is open source reuse.

Reference:

- Open Source Initiative maintains the Open Source Definition.
- GitHub recommends adding a license so others know what they may do with the code.
- Creative Commons licenses are commonly used for non-code creative/documentation material.

## 6. Public Repository Shape

Recommended public repository layout:

```text
README.md
LICENSE
NOTICE
CODE_OF_CONDUCT.md
CONTRIBUTING.md
SECURITY.md

ai-archive-kit/
  cli/
  src/
  mcp/
  schemas/
  specs/
  docs/
  plans/
  templates/
  examples/
  tests/

meeting-minutes/
  public-safe planning minutes only

archive-infra-decision-log-*.md
  public-safe architecture decisions only
```

Before public release, meeting minutes must be reviewed for private names, tokens, workspace IDs, sensitive business details, and accidental source leakage.

## 7. Documentation Separation

Keep these document categories separate:

```text
Product blueprint
  What the system is and why.

Implementation research
  Which standards, protocols, papers, and open-source references inform implementation.

Implementation plan
  What to build next, in what order, with acceptance criteria.

Work log
  What was actually done, when, and what changed.

Decision log
  Compact architecture decisions and consequences.

Meeting minutes
  Detailed chronological conversation context.
```

This separation is important because the project is meant to be inspected by future contributors.

## 8. Public Examples

Use fake archives only.

Example archives should:

- use fake names,
- use fake object hashes,
- use fake provider IDs,
- avoid real URLs unless they are public documentation references,
- avoid real business/customer/personal records.

## 9. Provider Integrations In An Open Source Project

The open-source repo may include connector logic for:

- local filesystem,
- external SSD,
- GitHub,
- object storage,
- Notion,
- Google Drive,
- Google Photos,
- external web URLs.

But credentials must be supplied by each user locally.

The public repo should use:

- env var references,
- keyring references,
- local profile names,
- example `.env.example` files,
- dry-run commands.

It must not include real tokens.

## 10. Community Feedback Goals

The public project should invite feedback on:

- whether `zet` is modeled correctly,
- whether minting and receipts are enough,
- whether source references are safe,
- whether provenance is too heavy or too light,
- whether provider references should be represented differently,
- whether workpacks should follow BagIt, RO-Crate, CAR, or another package model,
- whether future sharing should build on Nostr, Matrix, SimpleX-like queues, Radicle-like Git replication, or another layer.

## 11. Open Source Boundary Sentence

Recommended public framing:

```text
Zettel-kasten is open-source infrastructure for private, AI-assisted archives.
The code, schemas, and design process are public.
Your archive, sources, zets, receipts, and keys remain private unless you explicitly share them.
```
