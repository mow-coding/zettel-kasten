# GitHub Repository Strategy

Status: active baseline
Date: 2026-05-23

This project uses two GitHub repositories with different responsibilities.

## 1. Public Showcase Repository

```text
https://github.com/mow-coding/zettel-kasten
```

Visibility:

```text
public
```

Purpose:

- showcase the `zettel-kasten` and `zet` concept,
- publish the open-source implementation,
- publish protocol documents, schemas, setup docs, and fake examples,
- invite feedback, stars, collaboration, and investment inquiries.

This repository may contain:

- source code,
- schemas,
- public specs,
- product blueprint documents,
- implementation research,
- setup docs,
- security docs,
- fake examples,
- public-safe work logs.

This repository must not contain:

- real private archives,
- real private zets,
- real source maps,
- real receipts,
- provider tokens,
- credentials,
- local private file paths,
- private AI transcripts,
- raw personal media or documents.

## 2. Private Actual-Use Repository

```text
https://github.com/mow-coding/zettel-kasten-private
```

Visibility:

```text
private
```

Purpose:

- hold the user's actual working archive when the system is initialized for real use,
- keep real usage separate from public showcase materials,
- preserve the privacy-first philosophy of the base `zettel-kasten` system.

This repository should be initialized through the onboarding flow, not by manually dumping private files.

Expected future flow:

```text
one-command setup
-> local archive identity
-> WOM profile resolution
-> GitHub repository setup dry-run
-> private GitHub repo binding
-> object storage binding
-> source-world registration
-> dry-run scan
-> first draft zet
-> human-approved mint
```

## 3. v0.2.20 GitHub Repository Setup Planner

WOM-kit v0.2.20 adds a safe planner for profile-scoped GitHub repository setup:

```bash
archive github-repo <archive-root> --dry-run \
  --profile-id profile:personal:HongGilDong \
  --profile-slug HongGilDong \
  --github-owner example-user \
  --github-account-ref github:account:honggildong \
  --format json
```

The default proposed repository name is:

```text
zettel-kasten-<profile_slug>
```

The planner is dry-run-first. Approved mode can write/update `provider-bindings.yml`, write a provider setup receipt, and optionally write an ignored local account hint under `profiles/local/`.

It must not create GitHub repositories, run OAuth, call GitHub APIs, run `gh`, configure git remotes, push, or sync. Those steps remain manual until a future explicitly approved integration exists.

## 4. Attribution And License

The public repo uses the MIT License.

The original concept, product philosophy, naming, written design, schemas, source code, fake examples, and reference implementation are attributed to:

```text
Kim Seong Kyun (김성균)
Department of Urban Sociology, University of Seoul
GitHub: mow-coding
Email: mow.coding@gmail.com
Email: ellie0129@uos.ac.kr
```

The public `NOTICE.md` records this attribution and invites GitHub stars, thanks, collaboration, and investment inquiries.

## 5. Versioned Public Chain

The public repository should be friendly to readers who want to know which version of the system they are looking at.

The repo should treat release tags as compatibility checkpoints:

```text
v0.1.0
v0.2.0
v1.0.0
```

This follows the project's chain-like model:

```text
source code + specs + schemas + release tags
```

define the public rule set.

Users may follow the latest release or remain on an older release. Interoperability works best when users share the same major protocol version.

## 6. Practical Rule

When unsure whether something belongs in the public repo, ask:

```text
Could this file expose a real person's data, provider credentials, private business context, or local machine details?
```

If yes, keep it out of the public repo by default.
