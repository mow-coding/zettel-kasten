# IMAP Mailbox Source

Status: v0.4.44 current path (register, fetch whole messages, capture)

Email is often primary evidence: decisions, receipts, attachments and notices
arrive there before they become zets. WOM keeps whole messages, not summaries:
each selected message is stored byte for byte as `.eml` (attachments stay inside
it), then captured as an objet through the normal intake chain.

From a source checkout, run the same commands through the module launcher:
`$env:PYTHONPATH='src'; python -m wom_kit.archive_cli <command> ...`.

## 1. Register the mailbox

```powershell
archive add-source <archive-root> --source-id imap:personal --type imap_mailbox --dry-run
archive add-source <archive-root> --source-id imap:personal --type imap_mailbox --approve --reviewed-by person:me
```

Put the account name and an app password (not the account password) in two
environment variables. WOM stores only the references `env:NAME`, never values.

## 2. Fetch whole messages

```powershell
archive imap-mailbox-message-fetch <archive-root> --source-id imap:personal --batch-id mail-2026-09 `
  --imap-host imap.example.com --username-ref env:WOM_MAIL_USER --app-password-ref env:WOM_MAIL_APP_PASSWORD `
  --selection-rule newest_first --max-messages 50 --dry-run
```

The dry-run reads no credential and opens no connection; it prints a
`plan_sha256`. Run the same command with `--approve --reviewed-by <you>` to fetch
after one exact approval (a native dialog, or none under a valid session
grant). The mailbox is opened read-only and bodies are fetched with
`BODY.PEEK[]`, so no message is marked as read. Output:

- `workbench/imap-fetch/<batch>/mail-NNNN.eml` (new files, never overwritten)
- `workbench/imap-fetch/<batch>/source-intake-batch-request.json`
- `receipts/imap-message-fetch/<batch>.json` (digests and sizes only)

Selection rules: `newest_first`, `oldest_first`, `unread_first`,
`since_days_window` with `--since-days`. `--max-messages` is 1 to 1,000 per run.
Headers, subjects, addresses, bodies, the host and credential values are never
printed or stored in the receipt.

## 3. Capture as objets

```powershell
archive source-intake-batch <archive-root> --manifest workbench/imap-fetch/<batch>/source-intake-batch-request.json --dry-run
```

Then approve the same plan. Remove items from the request first if some
messages should not become objets.

## History

v0.3.19 to v0.3.72 built a stepwise plan toward a future adapter (source plan,
operation request, readiness, selection, manifest, audit, preflight, execution
contract, header scan, material selection and capture approval). The live
header scan was fixed closed in v0.4.0 and the capture step was never built.
v0.4.42 added the whole-message fetch and v0.4.44 removed the superseded chain.
