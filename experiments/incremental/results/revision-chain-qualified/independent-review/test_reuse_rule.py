#!/usr/bin/env python3
"""Independent synthetic controls for typed SCCs and conservative reuse."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name('reuse_rule.py')
if MODULE_PATH.exists():
    spec = importlib.util.spec_from_file_location('reuse_rule', MODULE_PATH)
    rule = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rule)
else:
    rule = None


def enc(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def h(value):
    return hashlib.sha256(enc(value)).hexdigest()


def index(changed=False, complex_last=False):
    keys = {s: h(['key', s]) for s in 'ABCD'}
    rows = [dict(key=keys[n], name=n, kind='quot' if complex_last and n == 'D' else 'def',
                 index=i, own=h(['own', n, changed and n == 'A']),
                 deps=sorted({'A':[keys['B']], 'B':[keys['A']], 'C':[keys['A']], 'D':[]}[n]))
            for i,n in enumerate('ABCD')]
    ab = h(['scc', sorted([[r['key'], r['own']] for r in rows[:2]]), [], []])
    rows[0]['closure'] = rows[1]['closure'] = ab
    rows[2]['closure'] = h(['scc', [[rows[2]['key'], rows[2]['own']]], [ab], []])
    rows[3]['closure'] = h(['scc', [[rows[3]['key'], rows[3]['own']]], [], []])
    return dict(meta={'format':{'version':'3.1.0'}}, count=4, declarations=rows,
                builtins={n:[None,None] for n in rule.BUILTINS},
                complex=h(['synthetic-complex', complex_last]),
                schedule=h([r['key'] for r in rows]))


def result(old, current, parent='a'*64):
    selected = [0,1,2] if old['declarations'][0]['own'] != current['declarations'][0]['own'] else []
    if selected and current['declarations'][-1]['kind'] == 'quot':
        selected.append(3)
    rows=[]
    for row in current['declarations']:
        checked=row['index'] in selected
        rows.append(dict(name=row['name'], index=row['index'],
                         status='VERIFIED_NEW' if checked else 'VERIFIED_REUSED',
                         reason=('complex_outside_verified_prefix' if row['kind']=='quot' else
                                 'content_or_transitive_dependency_changed') if checked else
                                ('exact_verified_prefix' if not selected else 'dependency_closure_unchanged'),
                         evidence_id='b'*64 if checked else parent,
                         dependency_witness=dict(own=row['own'],closure=row['closure'],direct=row['deps'])))
    return dict(schema='mathgraph.incremental-lean.v1', status='VERIFIED',
                previous_evidence=parent,evidence_id='b'*64,provenance={'policy':'pinned'},
                decisions=rows, counts=dict(total=4,rechecked=len(selected),scheduled=len(selected),
                                           invalidated=len(selected),reused=4-len(selected)),
                checker_result=dict(code=0,stdout=json.dumps(dict(checked=len(selected),total_declarations=4,
                      scope='selected_obligations_under_caller_trusted_environment'))),
                action_authorization='NONE')


class IndependentRuleTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(rule, 'independent reuse_rule.py must exist')

    def test_cycle_closure_and_unchanged_outside_cone(self):
        old,current=index(),index(True)
        rule.validate_index(old)
        rule.validate_index(current)
        proof=rule.validate_partition(result(old,current),old,current,'a'*64,
                                      parent_provenance={'policy':'pinned'})
        self.assertEqual(proof['checked_indices'],[0,1,2])
        self.assertEqual(proof['reused_indices'],[3])

    def test_complex_outside_prefix_cannot_use_local_rule(self):
        old,current=index(complex_last=True),index(True,True)
        proof=rule.validate_partition(result(old,current),old,current,'a'*64)
        self.assertEqual(proof['checked_indices'],[0,1,2,3])

    def test_full_unchanged_prefix_and_zero_selected(self):
        old=index()
        proof=rule.validate_partition(result(old,old),old,old,'a'*64)
        self.assertEqual(proof['checked_indices'],[])
        self.assertEqual(proof['reused_indices'],[0,1,2,3])

    def test_index_corruption_and_typed_aliases_refuse(self):
        for mutate in [lambda i:i.__setitem__('count',True),
                       lambda i:i['declarations'][0].__setitem__('index',False),
                       lambda i:i['declarations'][0].__setitem__('closure','f'*64),
                       lambda i:i.__setitem__('schedule','f'*64),
                       lambda i:i['declarations'][0].__setitem__('deps',[i['declarations'][1]['key']]*2),
                       lambda i:i['declarations'][0].__setitem__('key',i['declarations'][1]['key']),
                       lambda i:i['declarations'][0].__setitem__('own','NOT-HEX'),
                       lambda i:i['builtins'].__setitem__('extra',[None,None])]:
            invalid=index();mutate(invalid)
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                rule.validate_index(invalid)

    def test_parent_witness_status_count_and_reason_substitution_refuse(self):
        old,current=index(),index(True)
        valid=result(old,current)
        for mutate in [lambda r:r.__setitem__('previous_evidence','c'*64),
                       lambda r:r['decisions'][3].__setitem__('evidence_id','c'*64),
                       lambda r:r['decisions'][0].__setitem__('evidence_id','a'*64),
                       lambda r:r['decisions'][0].__setitem__('status','VERIFIED_REUSED'),
                       lambda r:r['decisions'][0].__setitem__('reason','dependency_closure_unchanged'),
                       lambda r:r['decisions'][0]['dependency_witness'].__setitem__('closure','f'*64),
                       lambda r:r['counts'].__setitem__('scheduled',True),
                       lambda r:r['checker_result'].__setitem__('stdout','{"checked":0,"total_declarations":4,"scope":"selected_obligations_under_caller_trusted_environment"}'),
                       lambda r:r.__setitem__('provenance',{'policy':'foreign'})]:
            invalid=copy.deepcopy(valid);mutate(invalid)
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                rule.validate_partition(invalid,old,current,'a'*64,
                                        parent_provenance={'policy':'pinned'})


if __name__=='__main__':
    unittest.main(verbosity=2)
