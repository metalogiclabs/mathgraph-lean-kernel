#!/usr/bin/env python3
"""Adversarial identity tests, not kernel-acceptance tests.

The small NDJSON graphs below exercise the admission predicate's dependency
overapproximation. Some intentionally contain cycles or incomplete types. Real
kernel agreement, including parser rejection, belongs to the external harness.
"""
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import unittest

import engine


class Graph:
    def __init__(self):
        self.rows = [{'meta': {'format': {'version': '3.1.0'}}}]
        self.names = {'': 0}
        self.next_expr = 0

    def name(self, display):
        if display not in self.names:
            prefix, _, suffix = display.rpartition('.')
            parent = self.name(prefix)
            index = len(self.names)
            self.names[display] = index
            self.rows.append({'in': index, 'str': {'pre': parent, 'str': suffix}})
        return self.names[display]

    def expr(self, tag, value):
        index = self.next_expr
        self.next_expr += 1
        self.rows.append({'ie': index, tag: value})
        return index

    def const(self, name):
        return self.expr('const', {'name': self.name(name), 'us': []})

    def definition(self, name, ty, value):
        self.rows.append({'def': dict(name=self.name(name), levelParams=[],
                                     type=ty, value=value, hints='abbrev',
                                     safety='safe', all=[])})

    def itype(self, name, ty, family=None, constructors=()):
        return dict(name=self.name(name), levelParams=[], type=ty,
                    numParams=0, numIndices=0,
                    all=[self.name(n) for n in (family or [name])],
                    ctors=[self.name(n) for n in constructors], numNested=0,
                    isRec=False, isUnsafe=False, isReflexive=False)

    def block(self, types, constructors=(), recursors=()):
        self.rows.append({'inductive': {'types': types,
                                       'ctors': list(constructors),
                                       'recs': list(recursors)}})

    def index(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'graph.ndjson'
            path.write_text(''.join(json.dumps(row) + '\n' for row in self.rows))
            return engine.make_index(path)


def declarations(index):
    return {d['name']: d for d in index['declarations']}


def environment(changed=False, builtin=False):
    graph = Graph()
    prop = graph.expr('sort', 0)
    graph.rows.append({'il': 1, 'succ': 0})
    higher = graph.expr('sort', 1)
    graph.definition('early', prop, higher if changed else prop)
    early = graph.const('early')
    graph.definition('dependent', prop, early)
    graph.definition('unrelated', prop, prop)
    if builtin:
        graph.definition('String.ofList', prop, early)
    return graph.index()


class DependencyPredicateTests(unittest.TestCase):
    def test_unchanged_obligation_changes_with_its_environment(self):
        old, new = environment(), environment(changed=True)
        before, after = declarations(old), declarations(new)
        self.assertEqual(old['schedule'], new['schedule'])
        self.assertEqual(before['dependent']['own'], after['dependent']['own'])
        self.assertNotEqual(before['dependent']['closure'], after['dependent']['closure'])
        self.assertEqual(before['unrelated']['closure'], after['unrelated']['closure'])

    def test_builtin_presence_in_undeclared_names_changes_global_assumptions(self):
        graph = Graph()
        prop = graph.expr('sort', 0)
        graph.definition('unrelated', prop, prop)
        old = graph.index()
        graph.name('String.ofList')
        new = graph.index()
        self.assertEqual(old['declarations'], new['declarations'])
        self.assertNotEqual(old['builtins'], new['builtins'])
        self.assertIsNotNone(new['builtins']['String.ofList'][0])
        self.assertIsNone(new['builtins']['String.ofList'][1])

    def test_implicit_builtin_transitive_helper_revokes_global_reuse(self):
        old, new = environment(builtin=True), environment(changed=True, builtin=True)
        before, after = declarations(old), declarations(new)
        self.assertEqual(before['String.ofList']['own'], after['String.ofList']['own'])
        self.assertEqual(before['unrelated']['closure'], after['unrelated']['closure'])
        self.assertNotEqual(old['builtins'], new['builtins'])

    def metadata_graph(self, changed):
        graph = Graph()
        prop = graph.expr('sort', 0)
        graph.rows.append({'il': 1, 'succ': 0})
        higher = graph.expr('sort', 1)
        graph.definition('helper', prop, higher if changed else prop)
        helper = graph.const('helper')
        structure = graph.itype('Structure', prop, constructors=['Structure.mk'])
        ctor = dict(name=graph.name('Structure.mk'), levelParams=[], type=helper,
                    induct=graph.name('Structure'), cidx=0, numParams=0,
                    numFields=1, isUnsafe=False)
        graph.block([structure], [ctor])
        inhabitant = graph.const('inhabitant')
        projected = graph.expr('proj', {'typeName': graph.name('Structure'),
                                       'idx': 0, 'struct': inhabitant})
        graph.definition('projected', prop, projected)
        return graph.index()

    def test_constructor_metadata_reaches_transitive_type_dependencies(self):
        old, new = self.metadata_graph(False), self.metadata_graph(True)
        before, after = declarations(old), declarations(new)
        self.assertEqual(old['complex'], new['complex'])
        self.assertEqual(before['projected']['own'], after['projected']['own'])
        self.assertNotIn(before['helper']['key'], before['projected']['deps'])
        self.assertIn(before['Structure']['key'], before['projected']['deps'])
        self.assertNotEqual(before['projected']['closure'], after['projected']['closure'])

    def test_recursor_rhs_dependency_is_not_lost(self):
        def index(changed):
            graph = Graph()
            prop = graph.expr('sort', 0)
            variable = graph.expr('bvar', 0)
            graph.definition('helper', prop, variable if changed else prop)
            helper = graph.const('helper')
            ty = graph.itype('Family', prop, constructors=['Family.mk'])
            ctor = dict(name=graph.name('Family.mk'), levelParams=[], type=prop,
                        induct=graph.name('Family'), cidx=0, numParams=0,
                        numFields=0, isUnsafe=False)
            rec = dict(name=graph.name('Family.rec'), levelParams=[], type=prop,
                       all=[graph.name('Family')], numParams=0, numIndices=0,
                       numMotives=1, numMinors=1, k=False, isUnsafe=False,
                       rules=[dict(ctor=graph.name('Family.mk'), nfields=0, rhs=helper)])
            graph.block([ty], [ctor], [rec])
            recursor = graph.const('Family.rec')
            graph.definition('consumer', prop, recursor)
            return graph.index()
        old, new = index(False), index(True)
        before, after = declarations(old), declarations(new)
        self.assertEqual(old['complex'], new['complex'])
        self.assertEqual(before['consumer']['own'], after['consumer']['own'])
        self.assertNotEqual(before['consumer']['closure'], after['consumer']['closure'])

    def test_semantic_identity_survives_serialization_renumbering(self):
        def index(reverse):
            graph = Graph()
            for name in (['beta', 'alpha'] if reverse else ['alpha', 'beta']):
                graph.name(name)
            if reverse:
                graph.expr('bvar', 0)
                prop = graph.expr('sort', 0)
            else:
                prop = graph.expr('sort', 0)
                graph.expr('bvar', 0)
            graph.definition('alpha', prop, prop)
            alpha = graph.const('alpha')
            graph.definition('beta', prop, alpha)
            return graph.index()
        self.assertEqual(index(False), index(True))

    def test_cyclic_component_change_propagates_to_all_members_and_consumers(self):
        def index(changed):
            graph = Graph()
            prop = graph.expr('sort', 0)
            graph.name('a')
            graph.name('b')
            a, b = graph.const('a'), graph.const('b')
            value = graph.expr('app', {'fn': a, 'arg': prop}) if changed else a
            graph.definition('a', prop, b)
            graph.definition('b', prop, value)
            graph.definition('consumer', prop, a)
            return graph.index()
        old, new = index(False), index(True)
        before, after = declarations(old), declarations(new)
        self.assertEqual(before['a']['closure'], before['b']['closure'])
        self.assertEqual(after['a']['closure'], after['b']['closure'])
        self.assertEqual(before['a']['own'], after['a']['own'])
        self.assertEqual(before['consumer']['own'], after['consumer']['own'])
        for name in ('a', 'b', 'consumer'):
            self.assertNotEqual(before[name]['closure'], after[name]['closure'])

    def test_reordered_declarations_change_the_visibility_schedule(self):
        def index(reverse):
            graph = Graph()
            prop = graph.expr('sort', 0)
            for name in ['alpha', 'beta']:
                graph.name(name)
            for name in (['beta', 'alpha'] if reverse else ['alpha', 'beta']):
                graph.definition(name, prop, prop)
            return graph.index()
        old, new = index(False), index(True)
        before, after = declarations(old), declarations(new)
        self.assertNotEqual(old['schedule'], new['schedule'])
        for name in before:
            self.assertEqual(before[name]['own'], after[name]['own'])
            self.assertEqual(before[name]['closure'], after[name]['closure'])

    def test_inductive_record_regrouping_changes_global_block_identity(self):
        def index(split):
            graph = Graph()
            prop = graph.expr('sort', 0)
            first = graph.itype('First', prop, family=['First', 'Second'])
            second = graph.itype('Second', prop, family=['First', 'Second'])
            if split:
                graph.block([first])
                graph.block([second])
            else:
                graph.block([first, second])
            return graph.index()
        old, new = index(False), index(True)
        self.assertEqual(old['schedule'], new['schedule'])
        self.assertEqual(old['declarations'], new['declarations'])
        self.assertNotEqual(old['complex'], new['complex'])


class EvidenceAuthenticationTests(unittest.TestCase):
    def test_record_content_address_and_hmac_both_reject_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            key = bytes(range(32))
            snapshot = b'authenticated export bytes\n'
            export_hash = hashlib.sha256(snapshot).hexdigest()
            (cache / 'exports').mkdir()
            (cache / 'records').mkdir()
            (cache / 'exports' / (export_hash + '.ndjson')).write_bytes(snapshot)
            payload = dict(schema=engine.SCHEMA, status='VERIFIED',
                           export_sha256=export_hash)
            signed = dict(payload=payload,
                          hmac_sha256=hmac.new(key, engine.encoded(payload), hashlib.sha256).hexdigest())
            raw = engine.encoded(signed)
            evidence = hashlib.sha256(raw).hexdigest()
            record = cache / 'records' / (evidence + '.json')
            record.write_bytes(raw)
            self.assertEqual(engine.load_evidence(cache, evidence, key), payload)

            signed['payload']['export_sha256'] = '0' * 64
            altered = engine.encoded(signed)
            record.write_bytes(altered)
            with self.assertRaisesRegex(ValueError, 'content address'):
                engine.load_evidence(cache, evidence, key)

            changed_id = hashlib.sha256(altered).hexdigest()
            (cache / 'records' / (changed_id + '.json')).write_bytes(altered)
            with self.assertRaisesRegex(ValueError, 'authentication'):
                engine.load_evidence(cache, changed_id, key)


if __name__ == '__main__':
    unittest.main()
