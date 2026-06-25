# Secret Signal Taxonomy

Status: v0.3.154 secret signal taxonomy checkpoint

WOM now has a read-only taxonomy for secret and sensitive-signal handling.

This helps an AI distinguish harmless concept words such as `secret`,
`credential`, `token`, or `key` from actual secret-like values, private
locators, and account identifiers.

## Command

```powershell
archive secret-signal-taxonomy <archive-root> `
  --dry-run `
  --format json
```

Aliases:

```powershell
archive secret-taxonomy <archive-root> --dry-run
archive sensitive-signal-taxonomy <archive-root> --dry-run
```

## Signal Classes

- `concept_word`: documentation or schema words such as secret, token, credential, password, or key.
- `safe_reference`: non-secret labels that point to a vault, OS store, approval receipt, or future adapter.
- `credential_reference`: structured references such as secret refs, credential ids, or vault entry labels without the value.
- `secret_value_pattern`: value-shaped API keys, passwords, private key blocks, cookies, or bearer strings.
- `private_locator`: local absolute paths, provider locators, private file URLs, or object locations.
- `account_identifier`: email addresses, account ids, org ids, tenant ids, or provider profiles.
- `unknown_sensitive_context`: ambiguous text near auth, provider, mailbox, credential, or private-material context.

## AI Operator Rule

Concept words are not secret values.

Actual value-shaped tokens, private locators, account identifiers, and ambiguous
sensitive context should fail closed in public outputs. Prefer safe refs, object
ids, receipt paths, or non-reversible fingerprints over secret values.

## Safety Boundary

The command:

- reads no archive body text,
- accepts no sample values,
- echoes no sample values,
- calls no providers,
- checks no network,
- echoes no local absolute paths, tokens, or secret values,
- writes nothing.

## Still Future

- Adding `secret_signal_class` fields to command-specific JSON outputs.
- Replacing string-only secret checks with class-aware diagnostics.
- Auditing existing commands where concept words may be over-classified.
- Adding non-reversible fingerprint receipts for places that need durable
  evidence without value disclosure.
