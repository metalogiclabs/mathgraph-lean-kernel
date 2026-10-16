#!/usr/bin/env python3
"""Decision and authority boundary checks for producer-delta consumers.

The frozen pre-refactor adapter is the independent finite-control oracle. These
checks exercise admission decisions only; they provide no kernel acceptance.
"""
import ast
import copy
import hashlib
import hmac
import itertools
from pathlib import Path
import subprocess
import types
import unittest

import engine

ROOT = Path(__file__).resolve().parents[2]
BASELINE = 'c5ab126'


def fixture():
    declarations = [dict(key=name, name=name, kind=kind, own=name + '-own',
                         closure=name + '-closure', deps=[], index=i)
                    for i, (name, kind) in enumerate((('prefix', 'def'),
                                                     ('changed', 'thm'),
                                                     ('local', 'def'),
                                                     ('block', 'itype')))]
    index = dict(meta={'format': {'version': '3.1.0'}}, declarations=declarations,
                 count=len(declarations), builtins={'Nat': ['nat', 'nat-root']},
                 complex='blocks', schedule='schedule')
    provenance = {'policy': 'default', 'checker_sha256': 'checker'}
    old = dict(index=copy.deepcopy(index), provenance=copy.deepcopy(provenance))
    return old, index, provenance


def frozen_oracle():
    source = subprocess.check_output(
        ['git', 'show', f'{BASELINE}:experiments/incremental/engine.py'], cwd=ROOT,
        text=True)
    original = types.ModuleType('independent_pre_delta_engine')
    original.__file__ = f'{BASELINE}:experiments/incremental/engine.py'
    exec(compile(source, original.__file__, 'exec'), original.__dict__)
    tree = ast.parse(source)
    function = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == '_verify_with_binary')
    context = next(n for n in function.body if isinstance(n, ast.With))
    start = next(i for i, n in enumerate(context.body)
                 if isinstance(n, ast.If) and ast.unparse(n.test) ==
                 "compatible and old['index']['meta'] != index['meta']")
    end = next(i for i, n in enumerate(context.body[start:], start)
               if isinstance(n, ast.Assign) and
               any(isinstance(t, ast.Name) and t.id == 'counts' for t in n.targets))
    wrapper = ast.parse('def oracle(old, index, provenance, previous_evidence, '
                        'disable_cache=False, cache_error=None, identical=False):\n'
                        '    verifier_policy = {"disable_cache": disable_cache}\n'
                        '    compatible = old is not None and old["provenance"] == provenance\n'
                        '    return selected, decisions\n').body[0]
    wrapper.body[-1:-1] = context.body[start:end]
    code = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
    exec(compile(code, '<frozen-existing-predicate>', 'exec'), original.__dict__)
    return original.oracle


class DeltaReuseTests(unittest.TestCase):
    def decide(self, mutate=None, **kwargs):
        old, index, provenance = fixture()
        if mutate:
            mutate(old, index, provenance)
        return engine.reuse_decisions(old, index, provenance, 'previous', **kwargs)

    def test_unchanged_prefix_preserves_witness_and_evidence(self):
        selected, decisions = self.decide()
        self.assertEqual(selected, [])
        self.assertTrue(all(d['reason'] == 'exact_verified_prefix' for d in decisions))
        self.assertEqual(decisions[0]['dependency_witness'],
                         dict(own='prefix-own', closure='prefix-closure', direct=[]))
        self.assertTrue(all(d['evidence_id'] == 'previous' for d in decisions))

    def test_changed_body_keeps_dependency_local_reuse_but_not_complex(self):
        selected, decisions = self.decide(
            lambda old, index, provenance: index['declarations'][1].update(own='new'))
        self.assertEqual(selected, [1, 3])
        self.assertEqual([d['reason'] for d in decisions],
                         ['exact_verified_prefix', 'content_or_transitive_dependency_changed',
                          'dependency_closure_unchanged', 'complex_outside_verified_prefix'])
        self.assertEqual([d['evidence_id'] for d in decisions],
                         ['previous', None, 'previous', None])

    def test_transitive_change_revokes_local_reuse(self):
        def mutate(old, index, provenance):
            index['declarations'][0]['own'] = 'new'
            index['declarations'][2]['closure'] = 'new-closure'
        selected, decisions = self.decide(mutate)
        self.assertEqual(selected, [0, 2, 3])
        self.assertEqual(decisions[2]['reason'], 'content_or_transitive_dependency_changed')

    def test_schedule_change_preserves_only_exact_prefix(self):
        def mutate(old, index, provenance):
            index['schedule'] = 'new'
            index['declarations'][1]['own'] = 'new'
        selected, decisions = self.decide(mutate)
        self.assertEqual(selected, [1, 2, 3])
        self.assertTrue(all(d['reason'] == 'declaration_schedule_changed' for d in decisions[1:]))

    def test_global_builtin_and_complex_changes_revoke_all_reuse(self):
        for field, value in [('builtins', {}), ('complex', 'new')]:
            with self.subTest(field=field):
                selected, decisions = self.decide(
                    lambda old, index, provenance: index.update({field: value}))
                self.assertEqual(selected, [0, 1, 2, 3])
                self.assertTrue(all(d['reason'] == 'global_builtin_or_complex_assumption_changed'
                                    for d in decisions))

    def test_metadata_and_provenance_drift_revoke_all_reuse(self):
        for mutate in [lambda old, index, provenance: index.update(meta={}),
                       lambda old, index, provenance: provenance.update(policy='new')]:
            selected, decisions = self.decide(mutate)
            self.assertEqual(selected, [0, 1, 2, 3])
            self.assertTrue(all(d['reason'] == 'toolchain_or_policy_changed' for d in decisions))

    def test_missing_old_and_refused_cache_reasons(self):
        _, index, provenance = fixture()
        for error, expected in [(None, 'no_previous_evidence'), ('bad HMAC', 'cache_refused:bad HMAC')]:
            selected, decisions = engine.reuse_decisions(
                None, index, provenance, 'previous', cache_error=error)
            self.assertEqual(selected, [0, 1, 2, 3])
            self.assertTrue(all(d['reason'] == expected for d in decisions))

    def test_disabled_cache_reason_preserves_existing_precedence(self):
        _, index, provenance = fixture()
        selected, decisions = engine.reuse_decisions(
            None, index, provenance, 'previous', disable_cache=True, cache_error='bad')
        self.assertEqual(selected, [0, 1, 2, 3])
        self.assertTrue(all(d['reason'] == 'cache_disabled' for d in decisions))

    def test_exact_export_reason_precedes_prefix(self):
        selected, decisions = self.decide(identical=True)
        self.assertEqual(selected, [])
        self.assertTrue(all(d['reason'] == 'exact_export' for d in decisions))

    def test_finite_controls_equal_independently_loaded_original(self):
        oracle = frozen_oracle()
        # Exhaust all 4,096 combinations, including structurally odd controls,
        # so extraction cannot silently strengthen or weaken the old predicate.
        for controls in itertools.product((False, True), repeat=12):
            old, index, provenance = fixture()
            (missing, policy, meta, builtin, complex_, schedule, own, closure,
             absent, disabled, cache_error, identical) = controls
            if policy:
                provenance['policy'] = 'changed'
            if meta:
                index['meta'] = {}
            if builtin:
                index['builtins'] = {}
            if complex_:
                index['complex'] = 'changed'
            if schedule:
                index['schedule'] = 'changed'
            if own:
                index['declarations'][1]['own'] = 'changed'
            if closure:
                index['declarations'][2]['closure'] = 'changed'
            if absent:
                old['index']['declarations'].pop(2)
            if missing:
                old = None
            args = (old, index, provenance, 'previous', disabled,
                    'corruption' if cache_error else None, identical)
            self.assertEqual(engine.encoded(engine.reuse_decisions(*args)),
                             engine.encoded(oracle(*args)), controls)


class RecordAuthenticationTests(unittest.TestCase):
    def record(self, **updates):
        key = bytes(range(32))
        payload = dict(schema=engine.SCHEMA, status='VERIFIED', export_sha256='export')
        payload.update(updates)
        raw = engine.encoded(dict(payload=payload, hmac_sha256=hmac.new(
            key, engine.encoded(payload), hashlib.sha256).hexdigest()))
        return raw, hashlib.sha256(raw).hexdigest(), key, payload

    def test_authentication_returns_payload_without_claiming_export_validation(self):
        raw, evidence, key, payload = self.record()
        self.assertEqual(engine.authenticate_record(raw, evidence, key), payload)

    def test_id_address_and_foreign_key_are_refused(self):
        raw, evidence, key, _ = self.record()
        for args, message in [((raw, 'bad', key), 'identifier'),
                              ((raw + b' ', evidence, key), 'content address'),
                              ((raw, evidence, b'x' * 32), 'authentication')]:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                engine.authenticate_record(*args)

    def test_other_schema_or_nonaccepted_status_is_not_acceptance_evidence(self):
        for update in [dict(schema='producer.identity.v1'), dict(status='UNKNOWN')]:
            raw, evidence, key, _ = self.record(**update)
            with self.assertRaisesRegex(ValueError, 'not accepted'):
                engine.authenticate_record(raw, evidence, key)


if __name__ == '__main__':
    unittest.main()
