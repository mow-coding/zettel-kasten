# IMAP Mailbox Adapter Manifest Write

Status: v0.4.0 dry-run-only local manifest preview; write fixed closed
Date: 2026-06-16

`imap-mailbox-adapter-manifest-write --dry-run` previews a reviewed, non-secret
IMAP mailbox adapter manifest. In v0.4.0 approval returns
`compound_exact_human_approval_binding_required` before private input/archive
target reads and records nothing.

It is not an IMAP client. It does not connect, login, select a mailbox, search
a mailbox, list messages, read headers, read bodies, read attachments, retrieve
credentials, start OAuth, or call providers.

## Command

Preview:

```bash
archive imap-mailbox-adapter-manifest-write <archive-root> \
  --adapter-id local-imap \
  --provider gmail \
  --provider naver \
  --operation header_metadata_scan \
  --selection-rule newest_first \
  --reviewed-by person:me \
  --dry-run \
  --format json
```

Alias:

```text
mailbox-adapter-manifest-write
```

There is no MCP live write tool for this command.

## Historical Write Layout

v0.3 approval wrote these two archive-relative files. v0.4.0 creates neither:

```text
config/imap-adapters/<adapter-id>.imap-mailbox-adapter.json
receipts/imap/adapter-manifests/<case-id>.imap-mailbox-adapter-manifest-write.json
```

The manifest is validated against:

```text
imap-mailbox-adapter-manifest.schema.json
```

The receipt records:

- manifest path,
- manifest hash,
- safe adapter labels,
- safe provider labels,
- safe operation labels,
- safe selection-rule labels,
- reviewer label,
- closed action flags.

## What It Must Not Contain

The manifest and receipt must not contain:

- email addresses,
- username values,
- exact account refs,
- exact credential refs,
- exact mailbox refs,
- real mailbox names,
- IMAP host values,
- provider URLs,
- IMAP UIDs,
- Message-ID values,
- subjects,
- sender or recipient values,
- message headers,
- message bodies,
- attachment names,
- approval receipt paths,
- selection receipt paths,
- local absolute paths,
- tokens,
- passwords,
- secret values.

Safe public labels such as `gmail`, `naver`, `generic_imap`, `local-imap`,
`header_metadata_scan`, and `newest_first` may appear.

## Current Boundary

v0.4.0 retains the reviewed, non-secret dry-run only. Approval reads no private
adapter input or target and writes no manifest or receipt. Historical v0.3
files remain readable but grant no execution authority.

It still does not:

- execute a live adapter,
- open an IMAP connection,
- attempt login,
- select a mailbox,
- search a mailbox,
- list candidate messages,
- read IMAP UIDs,
- read Message-ID values,
- read message headers,
- read message bodies,
- read attachments,
- create derived text,
- retrieve credential values,
- open a password manager, keyring, browser password store, or secret manager,
- start OAuth,
- call providers,
- draft zets,
- mint zets.

For beginners: the command can show the adapter's proposed job description,
but v0.4.0 cannot file it. The preview never lets an adapter read mail.
