#!/usr/bin/env python3
"""Fail-closed tests for transporting a typed-index patch against an authenticated base."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from producer_delta import reconstruct_index_patch

HEX_A = 'a' * 64
HEX_B = 'b' * 64
HEX_C = 'c' * 64
HEX_D = 'd' * 64

def baseline():
    decl = lambda i, key, own, closure, deps: dict(
        index=i, key=key, name='D'+str(i), kind='def',
        own=own, closure=closure, deps=deps)
    return dict(meta={'format': {'version': '3.1.0'}},
                declarations=[decl(0,HEX_A,HEX_B,HEX_C,[]),
                              decl(1,HEX_B,HEX_C,HEX_D,[HEX_A])],
                count=2, builtins={'Nat': [HEX_A, HEX_C]},
                complex=HEX_D, schedule=HEX_B)

def sparse_patch():
    b=baseline()
    row0=copy.deepcopy(b['declarations'][0])
    row1=copy.deepcopy(b['declarations'][1])
    row0['own']=HEX_D; row0['closure']=HEX_B
    row1['closure']=HEX_A
    return dict(schema='mathgraph.export-identity-baseline-patch.v1',
                count=2, declarations=[row0,row1],
                builtins={'Nat':[HEX_A,HEX_B]})

class SparseTransportTests(unittest.TestCase):
    def test_patch_exact_round_trip_without_mutating_baseline(self):
        before=baseline(); b=copy.deepcopy(before)
        actual=reconstruct_index_patch(b,sparse_patch())
        self.assertEqual(b,before)
        self.assertEqual(actual['declarations'][0]['own'],HEX_D)
        self.assertEqual(actual['declarations'][1]['closure'],HEX_A)
        self.assertEqual(actual['builtins']['Nat'],[HEX_A,HEX_B])
        self.assertEqual(actual['schedule'],before['schedule'])
    def test_empty_patch_is_identity(self):
        p=sparse_patch();p['declarations']=[];p['builtins']={}
        self.assertEqual(reconstruct_index_patch(baseline(),p),baseline())
    def test_refuse_duplicate_out_of_order_and_out_of_bounds(self):
        for rows in ([sparse_patch()['declarations'][0]]*2,
                     list(reversed(sparse_patch()['declarations'])),
                     [dict(sparse_patch()['declarations'][0],index=2)],
                     [dict(sparse_patch()['declarations'][0],index=True)]):
            p=sparse_patch();p['declarations']=rows
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                reconstruct_index_patch(baseline(),p)
    def test_refuse_modified_names_keys_kinds_deps_and_schema(self):
        for field, bad in [('name','different'),('key',HEX_B),('kind','thm'),
                           ('deps',[HEX_C]),('extra','untrusted')]:
            p=sparse_patch();p['declarations'][0][field]=bad
            with self.subTest(field=field),self.assertRaises(ValueError):
                reconstruct_index_patch(baseline(),p)
        for mutation in [lambda p:p.update(schema='other'),
                         lambda p:p.update(count=1),
                         lambda p:p.update(forged_authority=True),
                         lambda p:p.update(builtins={'Unknown':[HEX_A,HEX_B]})]:
            p=sparse_patch();mutation(p)
            with self.assertRaises(ValueError):
                reconstruct_index_patch(baseline(),p)
    def test_refuse_malformed_fingerprints_and_builtin_changes(self):
        for col,bad in [('own','wat'),('closure',None),('closure','f'*65)]:
            p=sparse_patch();p['declarations'][0][col]=bad
            with self.subTest(col=col),self.assertRaises(ValueError):
                reconstruct_index_patch(baseline(),p)
        for val in ([HEX_B,HEX_C], ['bad',HEX_A],[HEX_A,True]):
            p=sparse_patch();p['builtins']={'Nat':val}
            with self.assertRaises(ValueError):
                reconstruct_index_patch(baseline(),p)

if __name__=='__main__':
    unittest.main()
