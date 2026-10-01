# Archive infra decision log: mail as threads (2026-10-01)

Status: proposed by the owner on 2026-10-01; the recommendation below was
approved ("추천대로 구현해봐 ... 불만 있으면 피드백에 맞춰 고쳐나가면 되니까");
implemented for v0.4.57.

## Idea

Archived mail should also be readable the way Gmail shows it: replies that
went back and forth form one thread, per receiving mailbox account. No user
interface; only the text record takes the thread form.

## What existed

`imap-mailbox-message-fetch` keeps every message as its whole raw `.eml`
objet, so sender, recipients, Cc, date, attachments and the reply headers
(Message-ID, In-Reply-To, References) are all preserved inside the bytes.
Nothing extracted them; files were `mail-0001.eml` and the mailbox account
address was recorded only as hashed credential references.

## Decision

1. Threads are a derived snapshot, not an appended document and not a zet.
   Appending in place would create a third kind of record between immutable
   objets (evidence) and approved zets (canon) that changes on every fetch and
   needs its own approvals, receipts and backups. A snapshot is rebuilt from
   the objets like the search, relation and title snapshots, so the objet and
   zet flow is unchanged: the objets stay the evidence, and a person who wants
   to keep a conversation as knowledge drafts and mints a zet that cites the
   mail objets.
2. `mail-threads <archive-root> --build` (no approval: it writes only the
   rebuildable snapshot and never changes an objet) writes one Markdown record
   per thread under `db/mail-threads/<generation>/<account>/`, points
   `latest.json` at it and deletes older generations (current, the newest
   other and anything younger than an hour stay). The folder ignores itself in
   Git. `--dry-run` reports counts only.
3. Threading follows RFC 5322 Message-ID / In-Reply-To / References; mail
   without those headers falls back to the normalised subject (Re:, Fwd:,
   답장:, 회신:, 전달: removed) and the same participants. The same message
   fetched twice is counted once.
4. Per receiving mailbox account: a fetch now records the account address of
   the source it reads under `profiles/local/mail-accounts/` (private, never
   echoed); otherwise the mail's own Delivered-To / X-Original-To, then From,
   To and Cc decide.
5. Each record lists the participants and every message in date order with
   sender, recipients, Cc, date, subject, the objet reference, attachment
   names and the body text (text/plain preferred, HTML reduced to text);
   quoted lines (`>`) are folded with a note, since they remain in the objet.
6. Command output never echoes addresses, subjects or bodies.

## Not yet

Thread records are built on request; nothing runs them after a fetch
automatically. Offloaded mail (bytes only remote) is counted and skipped until
restored. Real mailboxes from different providers are not yet tested; the
beta testers' feedback decides the next changes.
