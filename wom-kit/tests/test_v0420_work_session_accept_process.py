"""Real accept process loss and original continuation, from source fixtures.

The native decision and archive key are synthetic; locks, approval claims,
registry writes, actor CAS, receipts and their independent checks are real.
These source-loaded children are not installed-wheel acceptance evidence.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_v0420_work_session_accept_lifecycle as fixture
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_establishment as establishment
from wom_kit import work_session_operation as operation


_CHILD = r'''
import json, os, sys
from pathlib import Path
from unittest.mock import patch
from wom_kit import exact_operation_manifest as exact
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import work_session_actor as actor
from wom_kit import work_session_execution as execution
from wom_kit import work_session_lifecycle as lifecycle
from wom_kit import work_session_operation as operation
from test_v0420_work_session_execution import SessionNative
from test_v0420_work_session_operation import _Key

root, app, route, action, mode, *extra = sys.argv[1:]
assert action == 'accept'
root = Path(root)
native = SessionNative()

if mode in {'before_checkpoint', 'after_terminal'}:
    assert len(extra) == 1
    predecessor = extra[0]
    if mode == 'before_checkpoint':
        def before_checkpoint(store, prepared, *, context, claim, **kwargs):
            # The real broker already published and authenticated this claim.
            # Exit at the writer entry, before the original registry runner can
            # create its first checkpoint. No fake result is returned.
            assert prepared.transition.action == 'accept'
            assert claim.status == 'started' and native.calls == 1
            claim.assert_ready_for_context(context)
            kwargs['held_lock'].verify_held()
            os._exit(73)
        operation.apply_session_decision_with_claim = before_checkpoint
    else:
        original_save = actor.WorkSessionActorStore.save
        def after_terminal(store, **kwargs):
            result = original_save(store, **kwargs)
            if kwargs.get('established_origin') is not None:
                assert kwargs['established_origin'].action == 'accept'
                assert result.document()['pending_manifest_sha256'] is None
                assert native.calls == 1
                kwargs['held_lock'].verify_held()
                os._exit(74)
            return result
        actor.WorkSessionActorStore.save = after_terminal
    with exact.ExactOperationWriterLock(root) as held:
        lifecycle._establish_task_held(root, held=held, action=action,
            client_app_ref=app, task_route_ref=route,
            predecessor_work_session_ref=predecessor,
            reviewer_claim='person:synthetic-reviewer', native=native, key_provider=_Key())
    raise AssertionError('expected_process_cut_not_reached')

assert mode == 'resume' and not extra
with patch.object(workflow, '_request_exact_human_approval_core',
                  side_effect=AssertionError('new_native_decision_forbidden')) as request:
    with patch.object(execution, '_execute_session_decision_held',
                      side_effect=AssertionError('new_operation_forbidden')) as execute:
        with exact.ExactOperationWriterLock(root) as held:
            result = lifecycle._resume_task_establishment_held(root, held=held,
                action=action, client_app_ref=app, task_route_ref=route, key_provider=_Key())
            held.verify_held()
        request.assert_not_called()
        execute.assert_not_called()
assert result['ok'] is True and result['independent_post_verification'] is True
assert result['native_approval_redisplayed'] is False
print(json.dumps({
    'ok': result['ok'], 'independent_post_verification': result['independent_post_verification'],
    'native_approval_redisplayed': result['native_approval_redisplayed'],
    # The started branch does not publish this succeeded-tail diagnostic.
    # Preserve that absence instead of inventing a false no-write claim.
    'domain_writer_reentered': result.get('domain_writer_reentered'),
    'receipt_sha256': result['receipt_sha256'], 'execution_sha256': result['execution_sha256'],
    'already_completed': result.get('original_task_operation_already_completed', False),
    'started_resume_state': result.get('started_resume_state'),
}, sort_keys=True))
'''


class AcceptProcessTests(unittest.TestCase):
    # Module-qualified fixture avoids collecting its TestCase methods again.
    setUp = fixture.AcceptLifecycleTests.setUp
    files = fixture.AcceptLifecycleTests.files

    def child(self, mode):
        kit = Path(__file__).resolve().parents[1]
        environment = dict(os.environ)
        environment['PYTHONPATH'] = os.pathsep.join((str(kit / 'src'), str(kit / 'tests')))
        environment['PYTHONDONTWRITEBYTECODE'] = '1'
        command = [sys.executable, '-B', '-c', _CHILD, str(self.root), self.receiving,
                   self.route, 'accept', mode]
        # No predecessor, manifest, context, claim, receipt or checkpoint ID is
        # supplied to the fresh continuation process.
        if mode != 'resume':
            command.append(self.predecessor)
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        return subprocess.run(command, env=environment, capture_output=True, text=True,
                              encoding='utf-8', timeout=90, **options)

    def exact_files(self, root):
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob('*') if path.is_file()} if root.exists() else {}

    def assert_lock_released(self):
        # A process exit must release the original OS-held archive authority.
        # Successful acquisition is not inferred from a PID or a stale label.
        with exact.ExactOperationWriterLock(self.root) as held:
            held.verify_held()

    def assert_original_receipt_and_origin(self, result, bound):
        selected = self.routing.read().document()
        origin = establishment.EstablishmentSelector.from_document(selected['established_origin'])
        successor = bound.prepared.manifest.work_session_binding.work_session_ref
        self.assertEqual(origin.action, 'accept')
        self.assertEqual(origin.manifest_sha256, bound.prepared.manifest.manifest_sha256)
        self.assertEqual(selected['work_session_ref'], successor)
        self.assertEqual(selected['last_completed_operation']['manifest_sha256'], origin.manifest_sha256)
        self.assertIsNone(selected['pending_manifest_sha256'])
        self.assertIsNone(selected['claim_ref'])
        sessions = self.store.read()._document['sessions']
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[self.predecessor]['state'], 'handed_off')
        self.assertEqual(sessions[successor]['predecessor_ref'], self.predecessor)
        self.assertEqual(sessions[successor]['workstream_ref'], sessions[self.predecessor]['workstream_ref'])
        self.assertEqual(sessions[successor]['state'], 'created')
        self.assertIsNone(sessions[successor]['claim_ref'])
        self.assertEqual(self.store.read().sha256, bound.prepared.transition.after.sha256)
        receipt = exact.load_exact_operation_final_receipt_read_only(self.root, result['execution_sha256'])
        self.assertEqual(receipt['receipt_sha256'], result['receipt_sha256'])
        self.assertEqual(receipt['result']['manifest_sha256'], origin.manifest_sha256)
        before = self.files()
        with patch.object(operation, 'apply_session_decision_with_claim',
                          side_effect=AssertionError('independent_verification_cannot_write')) as writer:
            with exact.ExactOperationWriterLock(self.root) as held:
                original = establishment.verify_original_establishment_held(
                    self.root, self.store, held=held, selector=origin,
                    client_app_ref=self.receiving, task_route_ref=self.route,
                    work_session_ref=successor, key_provider=self.case.key)
        writer.assert_not_called()
        self.assertEqual(original, bound)
        self.assertEqual(self.files(), before)

    def test_claim_publication_cut_then_fresh_accept_resume_keeps_original_claim_and_successor(self):
        previous_generation = self.store.read().sha256
        previous_claims = self.case.claims()
        checkpoints = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / 'checkpoints'
        receipts = self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT
        previous_checkpoints, previous_receipts = self.exact_files(checkpoints), self.exact_files(receipts)
        cut = self.child('before_checkpoint')
        self.assertEqual((cut.returncode, cut.stdout, cut.stderr), (73, '', ''))
        self.assert_lock_released()
        self.assertEqual(self.store.read().sha256, previous_generation)
        self.assertEqual(self.exact_files(checkpoints), previous_checkpoints)
        self.assertEqual(self.exact_files(receipts), previous_receipts)
        pending = self.routing.read().document()
        self.assertNotIn('established_origin', pending)
        bound = bundle.load_context_bound_session_decision(self.store,
            manifest_sha256=pending['pending_manifest_sha256'])
        claims = self.case.claims()
        original_claims = set(claims) - set(previous_claims)
        self.assertEqual(len(original_claims), 1)
        original_claim = original_claims.pop()
        self.assertEqual(json.loads(claims[original_claim])['status'], 'started')
        resumed = self.child('resume')
        self.assertEqual((resumed.returncode, resumed.stderr), (0, ''))
        result = json.loads(resumed.stdout)
        self.assertFalse(result['native_approval_redisplayed'])
        self.assertFalse(result['already_completed'])
        self.assertEqual(result['started_resume_state'], 'authenticated_before_first_checkpoint')
        self.assertEqual(set(self.case.claims()), set(claims))
        self.assertEqual(json.loads(self.case.claims()[original_claim])['status'], 'succeeded')
        self.assertEqual({name: self.case.claims()[name] for name in previous_claims}, previous_claims)
        self.assertEqual(len(self.exact_files(receipts)), len(previous_receipts) + 1)
        self.assert_original_receipt_and_origin(result, bound)
        self.assert_lock_released()

    def test_terminal_actor_cut_then_fresh_accept_resume_is_read_only_same_original_receipt(self):
        previous_claims = self.case.claims()
        cut = self.child('after_terminal')
        self.assertEqual((cut.returncode, cut.stdout, cut.stderr), (74, '', ''))
        self.assert_lock_released()
        selected = self.routing.read().document()
        bound = bundle.load_context_bound_session_decision(self.store,
            manifest_sha256=selected['established_origin']['manifest_sha256'])
        claims = self.case.claims()
        self.assertEqual(len(set(claims) - set(previous_claims)), 1)
        self.assertEqual({json.loads(raw)['status'] for raw in claims.values()}, {'succeeded'})
        before = self.files()
        resumed = self.child('resume')
        self.assertEqual((resumed.returncode, resumed.stderr), (0, ''))
        result = json.loads(resumed.stdout)
        self.assertTrue(result['already_completed'])
        self.assertFalse(result['native_approval_redisplayed'])
        self.assertFalse(result['domain_writer_reentered'])
        self.assertEqual(self.files(), before)
        self.assertEqual(self.case.claims(), claims)
        self.assert_original_receipt_and_origin(result, bound)
        self.assert_lock_released()


if __name__ == '__main__':
    unittest.main()
