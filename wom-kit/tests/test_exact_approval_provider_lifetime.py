"""Synthetic key copies, nested brokers, and fail-closed cleanup boundaries."""

from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from wom_kit import exact_human_approval_workflow as workflow
from wom_kit.exact_human_approval import CLAIMS_RELATIVE_ROOT
from wom_kit.operation_cancellation import ACTIVE_CLAIM
import test_exact_human_approval_workflow as base_tests
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID


class StrictKeys:
    def __init__(self):
        self.active = False
        self.calls = 0
        self.buffers = []
        self.after_consumer = None

    def use_key(self, _root, consumer, *, create_if_missing=False):
        assert not self.active, "credential provider was reentered"
        self.calls += 1
        self.active = True
        key = bytearray(range(32))
        self.buffers.append(key)
        try:
            result = consumer(memoryview(key))
            if self.after_consumer is not None:
                self.after_consumer()
            return result
        finally:
            key[:] = b"\0" * len(key)
            self.active = False


@pytest.fixture
def subject():
    fixture = base_tests.ExactHumanApprovalWorkflowTests()
    fixture.setUp()
    keys = StrictKeys()
    claims = []
    names = (
        "_claim_exact_human_approval_core",
        "_rehydrate_exact_human_approval_core",
        "_rehydrate_succeeded_exact_human_approval_core",
        "_rehydrate_existing_exact_human_approval_core",
    )
    patches = []
    for name in names:
        original = getattr(workflow, name)

        def observed(*args, _original=original, **kwargs):
            claim = _original(*args, **kwargs)
            claims.append(claim)
            return claim

        item = patch.object(workflow, name, side_effect=observed)
        item.start()
        patches.append(item)
    value = SimpleNamespace(
        root=fixture.root, context=fixture.context, keys=keys, claims=claims,
        boundary=fixture._resume_boundary,
    )
    try:
        yield value
    finally:
        for item in reversed(patches):
            item.stop()
        assert not keys.active
        assert all(not any(key) for key in keys.buffers)
        assert all(not any(claim._key) for claim in claims)
        assert ACTIVE_CLAIM.get() is None
        fixture.tearDown()


def execute(s, writer, **kwargs):
    return workflow._execute_exact_human_approved_write_core(
        s.root, s.context, writer,
        native=base_tests._Native((APPROVE_BUTTON_ID, True)), key_provider=s.keys, **kwargs,
    )


def test_fresh_writer_can_complete_exact_child_and_restores_parent_scope(subject):
    s = subject
    child_context = replace(s.context, plan_sha256="sha256:" + "c" * 64)

    def writer(parent):
        assert not s.keys.active
        assert ACTIVE_CLAIM.get() is parent
        assert all(not any(key) for key in s.keys.buffers)
        assert any(parent._key)

        def child_writer(child):
            assert not s.keys.active
            assert ACTIVE_CLAIM.get() is child
            assert child is not parent
            return {"ok": True}

        result = workflow._execute_exact_human_approved_write_core(
            s.root, child_context, child_writer,
            native=base_tests._Native((APPROVE_BUTTON_ID, True)), key_provider=s.keys,
        )
        assert result["ok"] is True
        assert ACTIVE_CLAIM.get() is parent
        parent.assert_ready_for_context(s.context)
        return {"ok": True}

    assert execute(s, writer)["ok"] is True
    assert s.keys.calls == 2


@pytest.mark.parametrize("failure", ["publication_exit", "provider_exit", "writer", "malformed", "finalizer"])
def test_fresh_exception_always_wipes_claim_copy(subject, failure):
    s = subject
    entered = []

    def fail():
        raise RuntimeError("synthetic failure")

    @contextmanager
    def publication():
        yield
        if failure == "publication_exit":
            fail()

    def writer(claim):
        entered.append(claim)
        assert not s.keys.active
        if failure == "writer":
            fail()
        return None if failure == "malformed" else {"ok": True}

    def finalizer(claim):
        assert not s.keys.active
        assert ACTIVE_CLAIM.get() is None
        assert claim.status == "succeeded"
        if failure == "finalizer":
            fail()

    if failure == "provider_exit":
        s.keys.after_consumer = fail
    with pytest.raises(workflow.ExactHumanApprovalWorkflowError) as raised:
        execute(s, writer, claim_publication_boundary=publication, claim_succeeded_finalizer=finalizer)
    assert bool(entered) == (failure not in {"publication_exit", "provider_exit"})
    assert raised.value.code == (
        "exact_human_approval_key_unavailable" if not entered else "exact_human_approval_state_unknown"
    )
    assert s.claims and all(not any(claim._key) for claim in s.claims)


@pytest.mark.parametrize("route", ["started", "transaction", "auto", "terminal", "terminal_transaction", "terminal_auto"])
@pytest.mark.parametrize("failure", [None, "guard", "guard_false", "finalizer"])
def test_resume_releases_provider_before_guards_and_always_wipes(subject, route, failure):
    s = subject
    terminal = route.startswith("terminal")
    initial = execute(s, lambda _claim: {"ok": terminal})
    approval_id = initial["exact_human_approval"]["approval_id"]
    events = []

    def guard(claim):
        assert not s.keys.active
        assert ACTIVE_CLAIM.get() is (None if terminal else claim)
        s.keys.use_key(s.root, lambda _key: events.append("guard_authenticated"))
        if failure == "guard":
            raise RuntimeError("synthetic checkpoint failure")
        return failure != "guard_false"

    def writer(claim):
        assert not terminal
        assert not s.keys.active
        assert ACTIVE_CLAIM.get() is claim
        events.append("writer")
        return {"ok": True}

    def finalizer(claim):
        assert not s.keys.active
        assert ACTIVE_CLAIM.get() is None
        assert claim.status == "succeeded"
        s.keys.use_key(s.root, lambda _key: events.append("finalizer_authenticated"))
        if failure == "finalizer":
            raise RuntimeError("synthetic tail failure")

    def resume():
        common = {"key_provider": s.keys, "resume_boundary": s.boundary}
        if route == "started":
            return workflow._resume_exact_human_approved_write_core(
                s.root, s.context, approval_id, guard, writer,
                claim_succeeded_finalizer=finalizer, **common,
            )
        if route == "terminal":
            return workflow._resume_succeeded_claim_finalizer_core(
                s.root, s.context, approval_id, guard, finalizer, **common,
            )
        if route.endswith("auto"):
            return workflow._resume_exact_human_approved_transaction_auto_core(
                s.root, s.context, guard, writer, guard, finalizer, **common,
            )
        return workflow._resume_exact_human_approved_transaction_core(
            s.root, s.context, approval_id, guard, writer, guard, finalizer, **common,
        )

    if failure is None:
        assert resume()["ok"] is True
        assert ("writer" in events) is not terminal
    else:
        with pytest.raises(workflow.ExactHumanApprovalWorkflowError) as raised:
            resume()
        assert raised.value.code == (
            "exact_human_approval_state_unknown" if failure == "finalizer"
            else "exact_human_approval_resume_candidate_missing" if failure == "guard_false" and route.endswith("auto")
            else "exact_human_approval_resume_checkpoint_invalid"
        )
        if failure.startswith("guard"):
            assert "writer" not in events and "finalizer_authenticated" not in events


def test_claim_changed_on_provider_release_never_reaches_writer(subject):
    s = subject
    initial = execute(s, lambda _claim: {"ok": False})
    approval_id = initial["exact_human_approval"]["approval_id"]
    claim_path = s.root / CLAIMS_RELATIVE_ROOT / (approval_id + ".json")

    def change_claim():
        claim_path.write_bytes(claim_path.read_bytes() + b" ")

    s.keys.after_consumer = change_claim
    entered = []
    with pytest.raises(workflow.ExactHumanApprovalWorkflowError):
        workflow._resume_exact_human_approved_write_core(
            s.root, s.context, approval_id, lambda _claim: True,
            lambda _claim: entered.append(True) or {"ok": True},
            key_provider=s.keys, resume_boundary=s.boundary,
        )
    assert entered == []


@pytest.mark.parametrize("provider_failure", [False, True])
def test_discovery_wipes_every_retained_candidate_on_failure(subject, provider_failure):
    s = subject
    execute(s, lambda _claim: {"ok": False})
    execute(s, lambda _claim: {"ok": False})

    def fail():
        raise RuntimeError("synthetic provider cleanup failure")

    if provider_failure:
        s.keys.after_consumer = fail
    with pytest.raises(workflow.ExactHumanApprovalWorkflowError) as raised:
        workflow._resume_exact_human_approved_transaction_auto_core(
            s.root, s.context, lambda _claim: True, lambda _claim: {"ok": True},
            lambda _claim: True, lambda _claim: None,
            key_provider=s.keys, resume_boundary=s.boundary,
        )
    assert raised.value.code == (
        "exact_human_approval_key_unavailable" if provider_failure
        else "exact_human_approval_resume_candidate_ambiguous"
    )
    assert len(s.claims) == 4


@pytest.mark.parametrize("guard_failure", [False, True])
def test_abandon_checkpoint_runs_after_provider_release(subject, guard_failure):
    s = subject
    execute(s, lambda _claim: {"ok": False})

    def guard(claim):
        assert ACTIVE_CLAIM.get() is claim
        assert not s.keys.active
        s.keys.use_key(s.root, lambda _key: None)
        if guard_failure:
            raise RuntimeError("synthetic guard failure")
        return True

    def abandon():
        return workflow._abandon_started_exact_human_approved_claims_core(
            s.root, s.context, guard, key_provider=s.keys, resume_boundary=s.boundary,
        )

    if guard_failure:
        with pytest.raises(workflow.ExactHumanApprovalWorkflowError) as raised:
            abandon()
        assert raised.value.code == "exact_human_approval_resume_checkpoint_invalid"
    else:
        assert abandon()["abandoned_started_claim_count"] == 1
