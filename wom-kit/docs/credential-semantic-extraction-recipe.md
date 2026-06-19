# Credential Semantic Extraction Recipe

Status: v0.3.113 read-only semantic extraction recipe with store-scenario routing
Date: 2026-06-19

v0.3.60 adds a read-only recipe for the moment before plaintext credential
migration.

This is for messy human notes that may contain several different things at
once:

- several accounts for the same service,
- a normal password plus an app password,
- an API key or CLI token,
- mail access through IMAP, OAuth, app passwords, or institutional login,
- SSO or passkey notes where no password should be invented,
- backup or recovery codes,
- wallet seed or private-key material,
- status/toggle notes such as old, disabled, reset, or needs review.

The command helps a human and AI discuss how to split the note into safe
credential candidates. It does not read the note.

## Command

```bash
archive credential-semantic-extraction-recipe <archive-root> \
  --source-label legacy-note-001 \
  --source-kind plaintext_note \
  --context mixed \
  --target-store-id keepassxc \
  --platform windows \
  --dry-run \
  --format json
```

Aliases:

```text
credential-extraction-recipe
secret-semantic-extraction-recipe
```

## What The Recipe Returns

The JSON response includes:

- safe source metadata,
- a `recipe_context`,
- human review questions,
- classification rules,
- `proposed_output_shape`,
- closed actions,
- privacy guards,
- current capability flags.

Entry classes:

```text
login_password
multi_account_same_service
api_key_or_cli_token
mail_access
sso_or_passkey_route
recovery_codes
wallet_seed_or_private_key_material
toggle_or_status_note
```

v0.3.113 adds store-scenario routing hints for the highest-risk classes:

```text
recovery_codes -> account_recovery_codes
wallet_seed_or_private_key_material -> break_glass_secrets
```

These hints do not lower the risk of the material. They tell the next planner to
use a break-glass policy: encrypted `secret:` ref, independent offline redundancy,
no single digital-only copy, and an explicit circular-dependency check before
the human relies on the vault.

## Human Review Questions

The recipe asks the human to decide:

- whether the source is one credential or several credentials,
- which parts are identifiers, labels, URLs, usernames, or secret values,
- whether login uses SSO, passkeys, OAuth, app passwords, or a normal password,
- whether multiple accounts for the same service must stay separate,
- whether recovery codes, backup codes, seed phrases, or wallet material are
  present,
- whether a line is only a status/toggle note,
- which external vault/keyring/store should hold each confirmed secret.

## Classification Rules

The command tells AI agents to:

- split multi-account notes instead of merging by provider,
- keep multi-secret notes as separate candidates,
- classify SSO/passkey notes as auth routes, not missing passwords,
- classify toggle/status notes as non-secret context unless a human confirms a
  real secret,
- treat wallet/recovery material as high-risk and separate from generic
  credential migration,
- record only safe refs in WOM.

## Current Closed Actions

`credential-semantic-extraction-recipe` does not read plaintext files.

It does not detect secret values.

It does not open password managers.

It does not return secret values to AI.

It also does not:

- read local file paths,
- hash source bytes,
- detect secret values,
- open password managers,
- open OS keyrings,
- open browser password stores,
- read environment variables,
- call providers,
- start OAuth,
- write files,
- write vault entries,
- import browser passwords,
- migrate wallet seed material,
- return secret values to AI.

This command is a semantic review recipe, not a secret scanner, importer, vault
writer, browser import tool, or wallet migration flow.

## Relationship To Plaintext Migration

Use this recipe before
[Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md)
when a note might contain several accounts, several secret values, SSO/passkey
routes, wallet material, recovery material, or status/toggle lines.

Safe flow:

```text
credential-semantic-extraction-recipe
-> human classifies one candidate at a time without pasting secret values
-> credential-plaintext-migration-plan
-> credential-ref-plan
-> credential-ref-inventory
-> credential-access-approval-plan
-> credential-policy-check
-> approved future adapter
```

v0.3.60 only adds the first semantic review step. Automatic candidate
extraction, local secret scanning, password-manager imports, browser password
imports, wallet migration, and live vault writes remain future work.

v0.3.113 connects `recovery_codes` to the account recovery storage scenario and
`wallet_seed_or_private_key_material` to the break-glass scenario. The command
still reads no source file and returns no secret values.
