# Developer Letters

Load this reference when the human asks to write to the WOM developers.

1. Run `operator-feedback-ledger` to see the numbers already used.
2. Preview `operator-feedback-compose` without a `feedback_id`; WOM assigns the
   next standard id (`wom-feedback-YYYYMMDD-NNN`). Never invent or reuse one.
3. Approve the same plan once. Then run `operator-feedback-body-check` and tell
   the human the letter is "전달 전". Do not create review copies.
   The human sees exactly two states, "전달 전" and "전달 완료". An approved
   compose IS the letter: there is no further registration step, so never
   describe one and never ask again for an instruction already given.
4. An undelivered letter is revised through compose's revise path, not by a
   new number and not by editing the file.
5. When the human says it was delivered, run `operator-feedback-mark-delivered
   --only <id> --approve`.
6. When the human asks to clean up (정리) delivered or resolved letters, that
   means delete. Preview `operator-feedback-delete <root> --dry-run`, tell the
   human the letter count and `bytes_freed_total`, then approve that plan once.
   It cannot be undone; letters not yet delivered stay. If the plan reports
   `moved_letter_needs_moved_folder`, ask the human for the folder an older
   WOM moved letters to and add `--moved-folder <that folder>`.

Author block (required, v0.4.54): fill `author.ai_product`, `author.model`
and `author.reasoning_level` with what this conversation actually uses. If
you cannot read them yourself, ask the human (the app shows them) and set
`author.source` to `confirmed_by_user`. Only if the human cannot tell either,
set `user_could_not_tell`. Never write `미수집`/`unknown` on your own.

Content rules:

- Quote the human's request faithfully; do not soften or reinterpret it.
- Separate observed facts from guesses, and say which AI and model wrote it.
- Include no names, account ids, archive ids, hashes, local paths, secrets, or
  private excerpts.
- Never write the letter body, ledger, or status files by hand.
