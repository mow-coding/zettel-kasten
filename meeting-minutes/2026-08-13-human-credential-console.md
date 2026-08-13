# Meeting minutes: WOM human credential console

Date: 2026-08-13

## Chronology

1. The human clarified that Notion PAT and API-token intake must happen in a
   visible black Windows console, not in AI chat, command arguments, or an
   ordinary inherited terminal prompt.
2. The first prototype proved that a spawned credential worker could allocate
   a new console, disable echo, read a synthetic token, close the console, and
   keep the raw value out of parent output and process IPC.
3. The human corrected the generic prototype copy. The visible text must
   describe the real task currently being performed by the helper AI and the
   human; it must not merely repeat the developer instruction “enter a Notion
   PAT or API key.”
4. The human then divided copy ownership explicitly:
   - WOM owns stable security language such as “입력한 자격 증명은 도우미
     AI와 채팅에 전달되지 않습니다.”
   - the active helper AI supplies the current-task explanation and the reason
     the current operation needs the Notion connection.
5. The human clarified persistence: the console is for first enrollment, not
   for every operation. The credential must be stored and reused.
6. The human watched the visible console canary and explicitly required Korean
   text not to render as `???`.
7. Independent review then found two identity mistakes behind the initial reuse
   claim. A Notion bot workspace and a person PAT have different API evidence,
   and released v0.3.311-v0.3.316 receipts had used the reviewed page as their
   workspace fingerprint. A corrected model therefore also needed a no-prompt
   compatibility path for already stored credentials.
8. Current official Notion documentation was reviewed. It states that one PAT
   belongs to one user in one workspace, `/v1/users/me` can return a person or
   bot, and only the bot shape exposes `workspace_id`. The design was changed
   to express those two authorities explicitly instead of treating a page UUID
   or label as workspace identity.

## Implemented decisions

- Added a dedicated Windows visible-console module using `FreeConsole`,
  `AllocConsole`, `CONIN$`, `CONOUT$`, `ReadConsoleW`, and `WriteConsoleW`.
- The console sets UTF-8 input/output code pages for the session and restores
  the original settings afterward.
- Input echo and processed Ctrl+C handling are disabled. Empty Enter and
  Ctrl+C cancel safely; input buffers are wiped. Real Windows testing showed
  that Escape does not reliably wake the cooked `ReadConsoleW` loop, so the UI
  does not promise Escape cancellation.
- Added two reviewed AI context fields: `task_summary` and
  `connection_reason`. They are public-safe, bounded, and reject secret or
  private-locator shapes.
- WOM's security, masking, cancellation, storage, and reuse copy is hardcoded
  outside those fields.
- The canonical CLI request and spawned-worker plan bind the AI context and
  `replace_existing` intent by SHA-256.
- `credential-adopt` is initial-enrollment by default. A matching registration
  skips the prompt only after its authenticated receipt selects one exact
  Windows entry, the saved secret matches its HMAC fingerprint, and the worker
  rechecks access to the currently reviewed Notion anchor. Missing, unreadable,
  or fingerprint-mismatched saved entries fail closed and require explicit
  `--replace-existing`. A current-anchor/provider check failure keeps the saved
  entry and routes to page, sharing, and connection review without prompting.
- Account/workspace labels are presentation text, not credential authority.
  Label-only drift reuses the same exact saved credential after revalidation;
  it does not open another prompt or create a duplicate registration.
- Successful intake continues to use an exact Windows Credential Manager
  Generic Credential and authenticated local receipt. Later recovery uses the
  receipt-backed broker and does not create the intake UI.
- New authenticated v0.2 receipts record an explicit workspace identity basis.
  Internal integrations use Notion's returned `bot.workspace_id`. Person PATs
  use a token-scoped witness derived from the archive-keyed HMAC fingerprint of
  the exact saved PAT plus current person and reviewed-page revalidation. The
  same saved PAT can serve another reviewed page; another PAT is not silently
  merged into the same scope.
- Released v0.3.311-v0.3.316 v0.1 receipts stay immutable. One compatible
  legacy registration can receive an authenticated append-only workspace-scope
  evolution after exact saved-secret and live provider/page revalidation. This
  opens no console and writes or deletes no Credential Manager entry. A simple
  singleton lifecycle can transition; absent lifecycle remains human-decision
  required, and duplicate or complex topology stops before publication.
- Windows console output counts UTF-16 code units rather than Python code
  points, so dynamic non-BMP text such as emoji is not truncated. The fixed
  Korean copy distinguishes AI/programmatic clipboard access from a human's
  deliberate paste into the masked console.

## Files changed in this scope

- `wom-kit/src/wom_kit/credential_visible_console_windows.py`
- `wom-kit/src/wom_kit/credential_secure_intake_windows.py`
- `wom-kit/src/wom_kit/credential_workflows.py`
- the `credential-adopt` surface in
  `wom-kit/src/wom_kit/archive_cli.py`
- credential console, Windows facade, workflow, CLI, and documentation tests
- runtime Agent Skill guidance and public credential continuity documents
- this meeting record and the v0.3.317 decision log

## Related completed work

Letter 130 staged-cleanup evidence remained a separate implementation scope.
Its v0.3.317 result keeps deferred entries staged and blocks cleanup; deferment
is not deletion authority.

## Evidence boundary

No real PAT or API token is written in this record. Tests and Windows canaries
must use synthetic values only. Local implementation and test completion are
separate from merge, CI, release, wheel installation, and client live
acceptance.
No real Notion account, workspace, page, protected archive, or Credential
Manager secret was used while designing or testing these paths.
