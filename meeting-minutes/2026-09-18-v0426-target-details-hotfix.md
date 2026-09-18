# v0.4.26 target-details page hotfix record

Date: 2026-09-18 (Korea Standard Time)
Status: development verified on a real dialog and on fake-dialog tests; release candidate in preparation; not client-verified

Executing model: Claude Opus 5, solo. The user asked what the approval
dialog's "대상 자세히 보기" button is, reported that the client's operator
saw nothing happen and the AI client got confused, and approved a live
reproduction on a synthetic dialog ("그래 뭐 한 번 해보던가"), then the
hotfix release ("아 그래 일단 하고 있어봐"). Boundaries unchanged: synthetic
labels only, no archive, the client workspace untouched; every decision
recorded here, in the decision log and in the acceptance register.

## Reproduction

A probe script (`native_dialog_probe.py`, session scratchpad) shows the real
`_CtypesTaskDialogNative` collection dialog with three synthetic items and
traces every callback message. The button was clicked through the real
window procedure (`BM_CLICK` on the "대상 자세히 보기" button found by
caption) so that Windows' own navigation path ran. The user also clicked the
dialogs by hand while they were on screen; those clicks are in the traces.

Unfixed handler (v0.4.25 source), click on the details button:

```
[page] built page=0 buttons=1
[cb] message=7 (TDN_DIALOG_CONSTRUCTED) pending=True   <- inside TDM_NAVIGATE_PAGE
[cb] message=2 wparam=2  error=exact_human_approval_native_call_failed  <- our own cancel
[cb] message=2 wparam=1002 -> 1
[cb] message=5 (TDN_DESTROYED)
raised ExactHumanApprovalWindowsError: exact_human_approval_native_call_failed
```

`TDN_NAVIGATED` (message 1) never arrived before `SendMessage` returned, so
the handler raised, set the error, clicked cancel on itself and the window
closed: "nothing happens" for the person, a native failure for the AI.

Fixed handler on the same real dialog: details → page (`7` inside the call,
`1` afterwards) → "승인 화면으로 돌아가기" → main page (`7`, then `1`) →
cancel, result `(2, False)`; with the user clicking: details → return →
details → return → approve, result `(1001, False)`.

## Fix

`exact_human_approval_windows._TaskDialogCollectionNavigation._on_notification`:
after sending `TDM_NAVIGATE_PAGE` the handler no longer raises when
`navigation_pending` is still set; it raises only if the dialog was
destroyed. The existing guard keeps every button except cancel inert until
`TDN_NAVIGATED` clears the pending flag. Tests: the fake dialog harness
gains a `"deferred"` confirmation mode (construction notice inside the call,
confirmation before the next click) and the never-confirmed case now asserts
an inert page ending in cancel; three new tests fail against the v0.4.25
source with exactly the reported code.

## Observed, deferred

The dialog is created with the foreground window at start time as its
owner (`GetForegroundWindow()`); minimising or hiding that window hides the
dialog too. During this reproduction the screen-control tool hid other
applications' windows, and the dialog went with them until its owner was
visible again. Recorded in the decision log; no change in this hotfix.

## Verification

- `test_v0420_target_collection_preview`, `test_v0420_approval_workflow_preview`,
  `test_exact_human_approval_windows`: green (46 tests).
- Wider cohorts, the bump cohort and CI are recorded below as they complete.
