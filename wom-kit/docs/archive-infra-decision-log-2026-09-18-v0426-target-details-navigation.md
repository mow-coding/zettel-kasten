# Decision amendment: a late native navigation confirmation is not a failure

Date: 2026-09-18
Status: accepted; v0.4.26 hotfix, development verified

## Context

The v0.4.20 paged target preview trusts a swapped dialog page only after
the Windows task dialog confirms it (`TDN_NAVIGATED`), so no authority can
pass through a half-built page. The implementation additionally required
that confirmation to arrive inside the synchronous navigation call. Windows
11 delivers it afterwards through the message loop, so every real click on
"대상 자세히 보기" cancelled the dialog as a native failure. Every test used
a fake dialog that confirmed synchronously.

## Decisions

1. The confirmation stays mandatory: until `TDN_NAVIGATED` arrives, every
   button except cancel is refused and the click is simply lost to the
   person, who can click again. No page is ever trusted on construction
   alone.
2. Lateness is not failure. Only a dialog destroyed while a navigation is
   pending raises `exact_human_approval_native_call_failed`.
3. The fake dialog harness models three orderings: confirmation inside the
   call, confirmation deferred (Windows 11), and never confirmed; the last
   must end in cancel, never in approval and never in a raised failure.
4. Deferred, recorded: the dialog is owned by the window that was in the
   foreground when the command started and hides with it; a dedicated owner
   or an always-on-top placement is a later decision.

## Evidence

Real-dialog traces in the hotfix minutes; three new tests in
`tests/test_v0420_target_collection_preview.py` that fail against v0.4.25
with exactly the reported code and pass with the fix.
