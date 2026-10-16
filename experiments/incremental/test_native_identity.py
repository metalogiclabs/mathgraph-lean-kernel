#!/usr/bin/env python3
"""Independent Python/native identity falsifiers; no theorem acceptance claims.

Build ``cargo build --release --bin export-index`` first. Run this file with
``--indexer PATH`` or set MATHGRAPH_NATIVE_INDEXER. A missing binary is an error,
not a skipped qualification. Synthetic fixtures are parser-valid structures;
they are deliberately not claimed to be well-typed kernel declarations.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

import engine
from test_predicate import Graph, declarations

ROOT = Path(__file__).resolve().parents[2]
INDEXER = Path(os.environ.get('MATHGRAPH_NATIVE_INDEXER', ROOT / 'target/release/export-index'))
META = {'lean': {'version': '4.35.0', 'githash': 'independent-test'},
        'exporter': {'name': 'lean4export', 'version': 'independent-test'},
        'format': {'version': '3.1.0'}}


class Fixture(Graph):
    def __init__(self):
        super().__init__()
        self.rows[0]['meta'] = copy.deepcopy(META)

    def declaration(self, kind, name, ty, value=None, all_names=()):
        obj = dict(name=self.name(name), levelParams=[], type=ty)
        if kind == 'axiom':
            obj['isUnsafe'] = False
        else:
            obj.update(value=value, all=[self.name(n) for n in all_names])
            if kind == 'def':
                obj.update(hints='abbrev', safety='safe')
            elif kind == 'opaque':
                obj['isUnsafe'] = False
        self.rows.append({kind: obj})
        return obj


def raw_rows(rows, *, ascii=True, pretty=False):
    return ''.join(json.dumps(row, sort_keys=True, ensure_ascii=ascii,
                              separators=None if pretty else (',', ':')) + '\n'
                   for row in rows).encode()


def base():
    graph = Fixture()
    prop = graph.expr('sort', 0)
    graph.definition('sample', prop, prop)
    return graph


def inductive(*, reflexive=False, nested=0, split=False, empty=False):
    graph = Fixture()
    prop = graph.expr('sort', 0)
    first = graph.itype('First', prop, family=['First', 'Second'])
    second = graph.itype('Second', prop, family=['First', 'Second'])
    first.update(isReflexive=reflexive, numNested=nested)
    if empty:
        graph.block([])
    if split:
        graph.block([first])
        graph.block([second])
    else:
        graph.block([first, second])
    return graph


def renumber(rows):
    """Change every serialized index with independent sparse, injective maps."""
    names = {0: 0, **{row['in']: 11 + 3 * row['in'] for row in rows if 'in' in row}}
    levels = {0: 0, **{row['il']: 17 + 5 * row['il'] for row in rows if 'il' in row}}
    exprs = {row['ie']: 23 + 7 * row['ie'] for row in rows if 'ie' in row}

    def decl(obj):
        for key in ('name', 'induct', 'ctor'):
            if key in obj:
                obj[key] = names[obj[key]]
        for key in ('levelParams', 'all', 'ctors'):
            if key in obj:
                obj[key] = [names[i] for i in obj[key]]
        for key in ('type', 'value', 'rhs'):
            if key in obj:
                obj[key] = exprs[obj[key]]
        for rule in obj.get('rules', []):
            decl(rule)

    output = copy.deepcopy(rows)
    for row in output:
        tag = next(k for k in row if k not in ('in', 'il', 'ie'))
        value = row[tag]
        if 'in' in row:
            row['in'] = names[row['in']]
            value['pre'] = names[value['pre']]
        elif 'il' in row:
            row['il'] = levels[row['il']]
            row[tag] = (names[value] if tag == 'param' else
                        [levels[i] for i in value] if isinstance(value, list) else levels[value])
        elif 'ie' in row:
            row['ie'] = exprs[row['ie']]
            if tag == 'sort':
                row[tag] = levels[value]
            elif tag == 'const':
                value['name'] = names[value['name']]
                value['us'] = [levels[i] for i in value['us']]
            elif isinstance(value, dict):
                for key in ('name', 'typeName'):
                    if key in value:
                        value[key] = names[value[key]]
                for key in ('type', 'body', 'value', 'fn', 'arg', 'struct'):
                    if key in value:
                        value[key] = exprs[value[key]]
        elif tag == 'inductive':
            for group in ('types', 'ctors', 'recs'):
                for obj in value[group]:
                    decl(obj)
        elif tag != 'meta':
            decl(value)
    return output


class NativeIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.indexer = INDEXER.expanduser().resolve()
        if not cls.indexer.is_file() or not os.access(cls.indexer, os.X_OK):
            raise RuntimeError(f'native identity binary missing or not executable: {cls.indexer}; '
                               'build cargo build --release --bin export-index or pass --indexer')

    def run_indexers(self, rows=None, *, raw=None):
        raw = raw if raw is not None else raw_rows(rows)
        with tempfile.TemporaryDirectory(prefix='native-identity-test-') as directory:
            directory = Path(directory)
            export = directory / 'export.ndjson'
            export.write_bytes(raw)
            config = directory / 'config.json'
            config.write_bytes(engine.encoded(dict(
                export_file_path=str(export), nat_extension=True, string_extension=True,
                permitted_axioms=engine.STANDARD_AXIOMS, num_threads=1,
                unpermitted_axiom_hard_error=True)))
            try:
                oracle = engine.make_index(export)
                oracle_error = None
            except (ValueError, TypeError, KeyError, OverflowError) as error:
                oracle, oracle_error = None, error
            run = subprocess.run([str(self.indexer), str(config)], capture_output=True, timeout=30)
            try:
                result = json.loads(run.stdout, object_pairs_hook=engine.strict_object)
            except (ValueError, UnicodeDecodeError) as error:
                self.fail(f'indexer did not return one strict JSON result: {error}; '
                          f'code={run.returncode}, stdout={run.stdout!r}, stderr={run.stderr!r}')
            return oracle, oracle_error, run, result

    def parity(self, rows=None, *, raw=None):
        oracle, oracle_error, run, result = self.run_indexers(rows, raw=raw)
        self.assertIsNone(oracle_error, str(oracle_error))
        self.assertEqual(run.returncode, 0, f'{result}; stderr={run.stderr.decode(errors="replace")}')
        self.assertEqual(result, oracle)
        # Python dictionary equality alone conflates JSON booleans and numbers.
        self.assertEqual(engine.encoded(result), engine.encoded(oracle))
        return result

    def rejects(self, rows=None, *, raw=None, python_rejects=True, stage=None):
        oracle, oracle_error, run, result = self.run_indexers(rows, raw=raw)
        if python_rejects:
            self.assertIsNotNone(oracle_error, f'Python unexpectedly indexed rejected fixture: {oracle}')
        else:
            self.assertIsNone(oracle_error, str(oracle_error))
        self.assertNotEqual(run.returncode, 0, f'malformed input received an index: {result}')
        self.assertIsInstance(result, dict)
        self.assertIsInstance(result.get('error'), str)
        self.assertTrue(result['error'])
        self.assertIn(result.get('stage'), ('kernel_parse', 'identity'))
        self.assertIs(type(result.get('declined')), bool)
        self.assertNotIn('declarations', result)
        if stage is not None:
            self.assertEqual(result['stage'], stage)
        return result

    def assert_own_changes(self, before, after, name='sample'):
        left, right = self.parity(before.rows), self.parity(after.rows)
        self.assertNotEqual(declarations(left)[name]['own'], declarations(right)[name]['own'])
        return left, right

    def test_simple_full_index_and_empty_export(self):
        self.parity(base().rows)
        result = self.parity(Fixture().rows)
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['declarations'], [])

    def test_binder_names_and_plicity_are_identity_not_dependencies(self):
        for tag in ('lam', 'forallE'):
            for field in ('name', 'binderInfo'):
                with self.subTest(tag=tag, field=field):
                    graph = Fixture()
                    first, second = graph.name('first'), graph.name('second')
                    prop = graph.expr('sort', 0)
                    body = graph.expr('bvar', 0)
                    expr = graph.expr(tag, dict(name=first, type=prop, body=body, binderInfo='default'))
                    graph.definition('sample', prop, expr)
                    changed = copy.deepcopy(graph)
                    next(row[tag] for row in changed.rows if tag in row)[field] = second if field == 'name' else 'implicit'
                    left, right = self.assert_own_changes(graph, changed)
                    self.assertEqual(declarations(left)['sample']['deps'], declarations(right)['sample']['deps'])
                    self.assertEqual(declarations(left)['sample']['deps'], [])

    def test_let_name_and_nondep_are_hashed(self):
        for field in ('name', 'nondep'):
            with self.subTest(field=field):
                graph = Fixture()
                first, second = graph.name('first'), graph.name('second')
                prop = graph.expr('sort', 0)
                body = graph.expr('bvar', 0)
                expr = graph.expr('letE', dict(name=first, type=prop, value=prop, body=body, nondep=False))
                graph.definition('sample', prop, expr)
                changed = copy.deepcopy(graph)
                next(row['letE'] for row in changed.rows if 'letE' in row)[field] = second if field == 'name' else True
                self.assert_own_changes(graph, changed)

    def test_nat_literal_original_decimal_string_is_retained(self):
        indexes = []
        for spelling in ('1', '01', '+1', '0001', '9' * 300):
            with self.subTest(spelling=spelling[:30]):
                graph = Fixture()
                prop = graph.expr('sort', 0)
                literal = graph.expr('natVal', spelling)
                graph.definition('sample', prop, literal)
                indexes.append(self.parity(graph.rows))
        self.assertEqual(len({declarations(i)['sample']['own'] for i in indexes}), len(indexes))

    def test_simple_mutual_all_fields_are_hashed_and_dependencies(self):
        for kind in ('def', 'thm', 'opaque'):
            with self.subTest(kind=kind):
                graph = Fixture()
                dependency = graph.name('other')
                prop = graph.expr('sort', 0)
                graph.declaration(kind, 'sample', prop, prop)
                changed = copy.deepcopy(graph)
                next(row[kind] for row in changed.rows if kind in row)['all'] = [dependency]
                left, right = self.assert_own_changes(graph, changed)
                self.assertEqual(declarations(left)['sample']['deps'], [])
                self.assertEqual(len(declarations(right)['sample']['deps']), 1)

    def test_definition_hints_are_exact(self):
        indexes = []
        for hint in ('abbrev', 'opaque', {'regular': 0}, {'regular': 17}):
            graph = base()
            graph.rows[-1]['def']['hints'] = hint
            indexes.append(self.parity(graph.rows))
        self.assertEqual(len({declarations(i)['sample']['own'] for i in indexes}), len(indexes))

    def test_quotient_kind_survives_discard_by_kernel(self):
        indexes = []
        for kind in ('type', 'ctor', 'lift', 'ind'):
            graph = Fixture()
            prop = graph.expr('sort', 0)
            graph.rows.append({'quot': dict(name=graph.name('sample'), levelParams=[], type=prop, kind=kind)})
            indexes.append(self.parity(graph.rows))
        self.assertEqual(len({declarations(i)['sample']['own'] for i in indexes}), 4)

    def test_inductive_reflexivity_and_exact_nested_count_are_hashed(self):
        baseline = self.parity(inductive().rows)
        variants = [self.parity(inductive(reflexive=True).rows),
                    self.parity(inductive(nested=1).rows), self.parity(inductive(nested=2).rows)]
        all_indexes = [baseline, *variants]
        self.assertEqual(len({declarations(i)['First']['own'] for i in all_indexes}), 4)
        self.assertEqual(len({i['complex'] for i in all_indexes}), 4)

    def test_block_regrouping_and_empty_blocks_change_global_boundary(self):
        together = self.parity(inductive().rows)
        for changed in (inductive(split=True), inductive(empty=True)):
            with self.subTest(rows=changed.rows):
                other = self.parity(changed.rows)
                self.assertEqual(together['declarations'], other['declarations'])
                self.assertEqual(together['schedule'], other['schedule'])
                self.assertNotEqual(together['complex'], other['complex'])

    def test_constructor_recursor_and_projection_dependency_paths(self):
        def fixture(changed):
            graph = Fixture()
            prop = graph.expr('sort', 0)
            body = graph.expr('bvar', 0)
            graph.definition('helper', prop, body if changed else prop)
            helper = graph.const('helper')
            family = graph.itype('Family', prop, constructors=['Family.mk'])
            ctor = dict(name=graph.name('Family.mk'), levelParams=[], type=helper,
                        induct=graph.name('Family'), cidx=0, numParams=0, numFields=0, isUnsafe=False)
            rec = dict(name=graph.name('Family.rec'), levelParams=[], type=prop,
                       all=[graph.name('Family')], numParams=0, numIndices=0,
                       numMotives=1, numMinors=1, k=False, isUnsafe=False,
                       rules=[dict(ctor=graph.name('Family.mk'), nfields=0, rhs=helper)])
            graph.block([family], [ctor], [rec])
            value = graph.const('inhabitant')
            projection = graph.expr('proj', dict(typeName=graph.name('Family'), idx=0, struct=value))
            graph.definition('projected', prop, projection)
            graph.definition('consumer', prop, graph.const('Family.rec'))
            return graph
        before, after = self.parity(fixture(False).rows), self.parity(fixture(True).rows)
        for name in ('projected', 'consumer'):
            self.assertEqual(declarations(before)[name]['own'], declarations(after)[name]['own'])
            self.assertNotEqual(declarations(before)[name]['closure'], declarations(after)[name]['closure'])

    def test_unicode_control_and_astral_canonicalization(self):
        text = '\x00\x01\x08\x0c\n\r\t\x0b\x1f\x7f\x80é𝄞😀"\\/'
        graph = Fixture()
        name = graph.name('prefix.' + text)
        prop = graph.expr('sort', 0)
        literal = graph.expr('strVal', text)
        binder = graph.expr('lam', dict(name=name, type=prop, body=literal, binderInfo=text))
        graph.definition('sample', prop, binder)
        graph.rows[0]['meta']['extra'] = {'😀': 1, '\ue000': 2, 'é': 3, 'a': [text, True, False, None]}
        escaped = self.parity(graph.rows)
        literal = self.parity(raw=raw_rows(graph.rows, ascii=False))
        self.assertEqual(escaped, literal)
        self.assertEqual(escaped, self.parity(raw=raw_rows(graph.rows, pretty=True)))

    def test_metadata_unknown_fields_are_preserved_and_exact(self):
        graph = base()
        graph.rows[0]['meta'].update(extra={'n': -9223372036854775808, 'u': 18446744073709551615,
                                          'nested': [None, True, False, {'λ': '😀'}]})
        graph.rows[0]['meta']['lean']['extra'] = 'retain'
        graph.rows[0]['meta']['format']['extra'] = 7
        result = self.parity(graph.rows)
        self.assertEqual(result['meta'], graph.rows[0]['meta'])
        changed = copy.deepcopy(graph)
        changed.rows[0]['meta']['lean']['extra'] = 'changed'
        other = self.parity(changed.rows)
        self.assertNotEqual(result['meta'], other['meta'])
        self.assertEqual(result['declarations'], other['declarations'])

    def test_untyped_binder_metadata_is_preserved(self):
        for info in (None, True, 17, ['implicit', {'😀': '\x7f'}], {'nested': {'a': False}}):
            with self.subTest(info=info):
                graph = Fixture()
                prop = graph.expr('sort', 0)
                expr = graph.expr('forallE', dict(name=0, type=prop, body=prop, binderInfo=info))
                graph.definition('sample', prop, expr)
                self.parity(graph.rows)

    def test_sparse_index_renumbering_insertion_order_and_level_edges(self):
        graph = Fixture()
        universe = graph.name('u')
        graph.rows.extend([{'il': 1, 'param': universe}, {'il': 2, 'succ': 0},
                           {'il': 3, 'max': [1, 2]}, {'il': 4, 'imax': [3, 1]}])
        ty = graph.expr('sort', 4)
        value = graph.expr('const', dict(name=graph.name('external'), us=[1, 2, 3, 4]))
        graph.definition('sample', ty, value)
        graph.rows[-1]['def']['levelParams'] = [universe]
        self.assertEqual(self.parity(graph.rows), self.parity(renumber(graph.rows)))
        indexes = []
        for reverse in (False, True):
            fixture = Fixture()
            for name in (['beta', 'alpha'] if reverse else ['alpha', 'beta']):
                fixture.name(name)
            if reverse:
                fixture.expr('bvar', 0)
            prop = fixture.expr('sort', 0)
            if not reverse:
                fixture.expr('bvar', 0)
            fixture.definition('alpha', prop, prop)
            fixture.definition('beta', prop, fixture.const('alpha'))
            indexes.append(self.parity(fixture.rows))
        self.assertEqual(*indexes)

    def test_name_component_kind_and_path_are_typed(self):
        graph = Fixture()
        prop = graph.expr('sort', 0)
        named = graph.name('1')
        numeric = max(row.get('in', 0) for row in graph.rows) + 1
        graph.rows.append({'in': numeric, 'num': {'pre': 0, 'i': 1}})
        for name in (named, numeric):
            graph.rows.append({'def': dict(name=name, levelParams=[], type=prop, value=prop,
                                          hints='abbrev', safety='safe', all=[])})
        result = self.parity(graph.rows)
        self.assertEqual([d['name'] for d in result['declarations']], ['1', '1'])
        self.assertEqual(len({d['key'] for d in result['declarations']}), 2)

    def test_scc_cycles_outgoing_roots_and_negative_dependencies(self):
        def fixture(changed):
            graph = Fixture()
            prop, variable = graph.expr('sort', 0), graph.expr('bvar', 0)
            for name in ('a', 'b', 'missing'):
                graph.name(name)
            a, b = graph.const('a'), graph.const('b')
            missing = graph.const('missing')
            graph.definition('leaf', prop, variable if changed else prop)
            leaf = graph.const('leaf')
            graph.definition('a', prop, graph.expr('app', {'fn': b, 'arg': missing}))
            graph.definition('b', prop, graph.expr('app', {'fn': a, 'arg': leaf}))
            graph.definition('consumer', prop, a)
            graph.definition('unrelated', prop, prop)
            return graph
        before, after = self.parity(fixture(False).rows), self.parity(fixture(True).rows)
        for result in (before, after):
            ds = declarations(result)
            self.assertEqual(ds['a']['closure'], ds['b']['closure'])
        for name in ('a', 'b', 'consumer'):
            self.assertEqual(declarations(before)[name]['own'], declarations(after)[name]['own'])
            self.assertNotEqual(declarations(before)[name]['closure'], declarations(after)[name]['closure'])
        self.assertEqual(declarations(before)['unrelated']['closure'], declarations(after)['unrelated']['closure'])

    def test_seeded_typed_dags_and_general_path_match_independent_oracle(self):
        # The generator does not share native hashing, merging, or SCC code.
        for seed in range(8):
            randomizer = random.Random(20261016 + seed)
            graph = Fixture()
            named = [graph.name(f'n{i}') for i in range(16)]
            graph.name('absent')
            prop = graph.expr('sort', 0)
            expressions = [prop, graph.expr('bvar', 0)]
            expressions.extend(graph.const(f'n{i}') for i in range(16))
            expressions.append(graph.const('absent'))
            for _ in range(45):
                first, second = randomizer.choices(expressions, k=2)
                tag = randomizer.choice(('app', 'lam', 'forallE', 'letE', 'proj'))
                if tag == 'app':
                    value = dict(fn=first, arg=second)
                elif tag == 'letE':
                    value = dict(name=randomizer.choice(named), type=prop, value=first,
                                 body=second, nondep=randomizer.choice((True, False)))
                elif tag == 'proj':
                    value = dict(typeName=randomizer.choice(named), idx=randomizer.randrange(5), struct=first)
                else:
                    value = dict(name=randomizer.choice(named), type=first, body=second,
                                 binderInfo=randomizer.choice(('default', 'implicit', 'instImplicit', 'strictImplicit')))
                expressions.append(graph.expr(tag, value))
            for i in range(16):
                graph.declaration(randomizer.choice(('def', 'thm', 'opaque')), f'n{i}', prop,
                                  randomizer.choice(expressions),
                                  all_names=[f'n{j}' for j in randomizer.sample(range(16), randomizer.randrange(4))])
            with self.subTest(seed=seed):
                compact = self.parity(graph.rows)
                self.assertEqual(compact, self.parity(renumber(graph.rows)))

                def shuffled(value):
                    if isinstance(value, dict):
                        items = list(value.items())
                        randomizer.shuffle(items)
                        return {key: shuffled(item) for key, item in items}
                    if isinstance(value, list):
                        return [shuffled(item) for item in value]
                    return value
                general = ''.join(json.dumps(shuffled(row), ensure_ascii=False) + '\n'
                                  for row in graph.rows).encode()
                self.assertEqual(compact, self.parity(raw=general))

    def test_schedule_and_missing_dependency_resolution(self):
        graph = Fixture()
        for name in ('first', 'second', 'missing'):
            graph.name(name)
        prop = graph.expr('sort', 0)
        graph.definition('first', prop, graph.const('missing'))
        graph.definition('second', prop, prop)
        before = self.parity(graph.rows)
        reordered = copy.deepcopy(graph)
        positions = [i for i, row in enumerate(reordered.rows) if 'def' in row]
        # Keep name/expression rows in place and exchange only declarations.
        reordered.rows[positions[0]], reordered.rows[positions[1]] = reordered.rows[positions[1]], reordered.rows[positions[0]]
        changed = self.parity(reordered.rows)
        self.assertNotEqual(before['schedule'], changed['schedule'])
        for name in ('first', 'second'):
            self.assertEqual(declarations(before)[name]['closure'], declarations(changed)[name]['closure'])
        graph.definition('missing', prop, prop)
        resolved = self.parity(graph.rows)
        self.assertEqual(declarations(before)['first']['own'], declarations(resolved)['first']['own'])
        self.assertNotEqual(declarations(before)['first']['closure'], declarations(resolved)['first']['closure'])

    def test_builtin_presence_and_transitive_helper_change_global_pin(self):
        old = base()
        new = copy.deepcopy(old)
        new.name('String.ofList')
        before, after = self.parity(old.rows), self.parity(new.rows)
        self.assertEqual(before['declarations'], after['declarations'])
        self.assertNotEqual(before['builtins'], after['builtins'])
        self.assertIsNone(after['builtins']['String.ofList'][1])
        indexes = []
        for changed in (False, True):
            graph = Fixture()
            prop, variable = graph.expr('sort', 0), graph.expr('bvar', 0)
            graph.definition('helper', prop, variable if changed else prop)
            graph.definition('String.ofList', prop, graph.const('helper'))
            graph.definition('unrelated', prop, prop)
            indexes.append(self.parity(graph.rows))
        self.assertNotEqual(indexes[0]['builtins'], indexes[1]['builtins'])
        self.assertEqual(declarations(indexes[0])['unrelated']['closure'], declarations(indexes[1])['unrelated']['closure'])

    def test_ambiguous_builtin_display_fails_closed(self):
        graph = base()
        graph.name('Nat.add')
        index = max(row.get('in', 0) for row in graph.rows) + 1
        graph.rows.append({'in': index, 'str': {'pre': 0, 'str': 'Nat.add'}})
        self.rejects(graph.rows, stage='identity')

    def test_duplicate_json_keys_fail_at_every_depth_and_after_unescaping(self):
        raw = raw_rows(base().rows)
        cases = [raw.replace(b'"sort":0', b'"sort":0,"sort":0'),
                 raw.replace(b'"value":0', b'"value":0,"value":0'),
                 raw.replace(b'"name":1', b'"name":1,"\\u006eame":1'),
                 raw.replace(b'"format":{"version":"3.1.0"}', b'"format":{"version":"3.1.0","version":"3.1.0"}'),
                 raw.replace(b'"githash":"independent-test"', b'"githash":"independent-test","extra":{"x":1,"x":2}')]
        for altered in cases:
            with self.subTest(raw=altered):
                self.assertNotEqual(altered, raw)
                self.rejects(raw=altered)

    def test_unknown_fields_are_rejected_except_inside_metadata(self):
        for scope in ('row', 'name', 'expression', 'declaration', 'inductive', 'rec_rule'):
            graph = base()
            if scope == 'row':
                graph.rows[1]['extra'] = 0
            elif scope == 'name':
                next(row['str'] for row in graph.rows if 'str' in row)['extra'] = 0
            elif scope == 'expression':
                prop = 0
                graph.expr('app', {'fn': prop, 'arg': prop, 'extra': 0})
            elif scope == 'declaration':
                graph.rows[-1]['def']['extra'] = 0
            elif scope == 'inductive':
                graph = inductive()
                graph.rows[-1]['inductive']['extra'] = 0
            else:
                graph = inductive()
                block = next(row for row in graph.rows if 'inductive' in row)
                rec_name = graph.name('First.rec')
                block['inductive']['recs'] = [dict(name=rec_name, levelParams=[], type=0,
                    all=[], numParams=0, numIndices=0, numMotives=0, numMinors=0, k=False, isUnsafe=False,
                    rules=[dict(ctor=graph.name('First'), nfields=0, rhs=0, extra=0)])]
                # Move generated name rows before the inductive record.
                block = next(row for row in graph.rows if 'inductive' in row)
                graph.rows.remove(block)
                graph.rows.append(block)
            with self.subTest(scope=scope):
                self.rejects(graph.rows)

    def test_invalid_json_fast_path_control_bytes_and_leading_zeros(self):
        graph = base()
        graph.expr('strVal', 'marker')
        original = raw_rows(graph.rows)
        for byte in (0, 1, 9, 13, 31):
            with self.subTest(control=byte):
                self.rejects(raw=original.replace(b'marker', b'bad' + bytes([byte]) + b'text'))
        for token in (b'00', b'01', b'00000000'):
            with self.subTest(integer=token):
                self.rejects(raw=original.replace(b'"sort":0', b'"sort":' + token))
        self.rejects(raw=original + b'{"ie":07,"bvar":0}\n')

    def test_bad_dag_indices_and_references_fail_closed(self):
        graph = base()
        for extra in ({'ie': 0, 'bvar': 0}, {'ie': True, 'bvar': 0}, {'ie': -1, 'bvar': 0},
                      {'ie': 50, 'app': {'fn': 49, 'arg': 0}},
                      {'ie': 50, 'sort': True}, {'il': 0, 'succ': 0},
                      {'ie': 50, 'const': {'name': True, 'us': []}},
                      {'ie': 50, 'bvar': 0, 'in': 50}):
            with self.subTest(extra=extra):
                self.rejects([*graph.rows, extra])
        duplicate = copy.deepcopy(graph.rows)
        duplicate.append(copy.deepcopy(duplicate[-1]))
        self.rejects(duplicate)

    def test_missing_binder_metadata_is_identity_refusal_not_kernel_regression(self):
        for tag in ('lam', 'forallE', 'letE'):
            graph = Fixture()
            prop = graph.expr('sort', 0)
            fields = {'type': prop, 'body': prop}
            if tag == 'letE':
                fields.update(value=prop, nondep=False)
            graph.expr(tag, fields)
            with self.subTest(tag=tag):
                self.rejects(graph.rows, stage='identity')

    def test_unsafe_partial_and_nonstandard_axiom_cannot_receive_index(self):
        for kind, flag, value in (('def', 'safety', 'unsafe'), ('def', 'safety', 'partial'),
                                  ('opaque', 'isUnsafe', True), ('axiom', 'isUnsafe', True)):
            graph = Fixture()
            prop = graph.expr('sort', 0)
            obj = graph.declaration(kind, 'propext' if kind == 'axiom' else 'sample', prop, prop)
            obj[flag] = value
            with self.subTest(kind=kind, value=value):
                self.rejects(graph.rows)
        graph = Fixture()
        prop = graph.expr('sort', 0)
        graph.declaration('axiom', 'notAllowed', prop)
        self.rejects(graph.rows)

    def test_metadata_order_uniqueness_and_exact_format_version(self):
        graph = base()
        cases = [graph.rows[1:], [*graph.rows, graph.rows[0]],
                 [graph.rows[1], graph.rows[0], *graph.rows[2:]]]
        for rows in cases:
            with self.subTest(rows=rows):
                self.rejects(rows)
        for version in ('3.1.1', '3.2.0', '3.0.9'):
            changed = copy.deepcopy(graph.rows)
            changed[0]['meta']['format']['version'] = version
            with self.subTest(version=version):
                self.rejects(changed)

    def test_python_index_success_is_not_kernel_parser_acceptance(self):
        # This is the original malformed-unused-typed-node trust-boundary case.
        graph = base()
        graph.rows.append({'ie': 10, 'bvar': 'not-an-integer'})
        self.rejects(graph.rows, python_rejects=False, stage='kernel_parse')
        minimal = base().rows
        minimal[0] = {'meta': {'format': {'version': '3.1.0'}}}
        self.rejects(minimal, python_rejects=False, stage='kernel_parse')

    def test_python_only_numeric_metadata_is_explicitly_unsupported(self):
        for value in (1.0, -0.0, 1e30, 18446744073709551616, -9223372036854775809):
            graph = base()
            graph.rows[0]['meta']['extra'] = value
            with self.subTest(value=value):
                error = self.rejects(graph.rows, python_rejects=False, stage='identity')
                self.assertTrue(error['declined'])

    def test_lone_surrogates_and_nonfinite_numbers_never_silently_normalize(self):
        for value in ('\ud800', '\udfff', float('nan'), float('inf'), -float('inf')):
            graph = base()
            graph.rows[0]['meta']['extra'] = value
            with self.subTest(value=repr(value)):
                self.rejects(graph.rows, python_rejects=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--indexer', type=Path)
    selected, remaining = parser.parse_known_args()
    if selected.indexer is not None:
        INDEXER = selected.indexer
    unittest.main(argv=[sys.argv[0], *remaining])
