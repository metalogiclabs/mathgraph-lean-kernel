#!/usr/bin/env python3
"""Canonical-reference tests for already admitted acyclic JSON index trees."""
import copy
import random
import unittest

import producer_delta as adapter


class IndexJsonEqualityTests(unittest.TestCase):
    def test_unknown_comparison_policy_refuses_before_accessing_inputs(self):
        for mode in ('unknown', None, True, 1, [], {}):
            with self.subTest(mode=mode), self.assertRaisesRegex(
                    ValueError, 'unsupported receipt index comparison mode'):
                adapter.DeltaSession(None, None, None, None, None, None, None,
                                     receipt_index_comparison=mode)

    def check_reference(self, left, right):
        expected = adapter.engine.encoded(left) == adapter.engine.encoded(right)
        self.assertEqual(adapter._same_index_json(left, right), expected)
        self.assertEqual(adapter._same_index_json(right, left), expected)

    def test_numeric_and_boolean_distinctions(self):
        values = [None, False, True, 0, 1, -1, 0.0, -0.0, 1.0,
                  float('nan'), float('nan'), float('inf'), -float('inf')]
        for left in values:
            for right in values:
                with self.subTest(left=repr(left), right=repr(right)):
                    self.check_reference(left, right)

    def test_unicode_values_and_keys_use_canonical_reference(self):
        astral, surrogates = '\U0001f600', '\ud83d\ude00'
        cases = [(astral, surrogates), ({astral: 1}, {surrogates: 1}),
                 ({astral: 1, surrogates: 2}, {surrogates: 2, astral: 1}),
                 ({'name': astral}, {'name': surrogates}),
                 ('α', 'a'), ('\\n', '\n'), ('a\x00', 'a')]
        for left, right in cases:
            self.check_reference(left, right)

    def test_order_shape_and_scalar_types(self):
        cases = [({'a': [1, True], 'b': None}, {'b': None, 'a': [1, True]}),
                 ({'a': 1}, {'a': True}), ([1], [1.0]),
                 ({'a': [0.0]}, {'a': [-0.0]}), ({'a': 1}, {'b': 1}),
                 ([], {}), ([1, 2], [2, 1]), ({}, {'extra': None})]
        for left, right in cases:
            self.check_reference(left, right)

    def test_non_json_containers_fall_back_to_legacy_encoder(self):
        class PlainDict(dict):
            pass
        for left, right in [((1, 2), [1, 2]), ({1: 'x'}, {'1': 'x'}),
                            (PlainDict(a=1), {'a': 1})]:
            self.check_reference(left, right)
        with self.assertRaises(TypeError):
            adapter._same_index_json(object(), object())

    def test_actual_shared_declaration_shape_detects_mutation(self):
        baseline = {'count': 2000, 'builtins': {}, 'declarations': [
            {'index': i, 'name': 'T.' + str(i), 'deps': [],
             'complex': False, 'own': 'a' * 64, 'closure': 'b' * 64}
            for i in range(2000)]}
        rebuilt = dict(baseline, declarations=list(baseline['declarations']))
        rebuilt['declarations'][17] = dict(baseline['declarations'][17])
        self.check_reference(baseline, rebuilt)
        for field, value in [('closure', 'c' * 64), ('index', True),
                             ('complex', 0), ('deps', ['foreign'])]:
            changed = dict(rebuilt, declarations=list(rebuilt['declarations']))
            changed['declarations'][17] = dict(rebuilt['declarations'][17], **{field: value})
            self.check_reference(baseline, changed)
            self.assertFalse(adapter._same_index_json(baseline, changed))

    def test_deterministic_generated_json_against_independent_encoding(self):
        rng = random.Random(20261021)
        atoms = [None, True, False, -3, 0, 1, 1.0, -0.0, '', 'ASCII', 'α', '\U0001f600']
        def tree(depth):
            if depth == 0 or rng.randrange(3) == 0:
                return rng.choice(atoms)
            if rng.randrange(2):
                return [tree(depth - 1) for _ in range(rng.randrange(5))]
            return {'k' + str(i): tree(depth - 1) for i in range(rng.randrange(5))}
        for _ in range(500):
            left = tree(4)
            self.check_reference(left, copy.deepcopy(left))
            self.check_reference(left, tree(4))


if __name__ == '__main__':
    unittest.main()
