#!/usr/bin/env python3
"""Representation/authority guards; these unit fixtures are not kernel verdicts."""
import copy
import hashlib
import json
import unittest

import engine
from producer_delta import authenticate_sparse_acceptance, reconstruct_index_patch, seal
from test_sparse_acceptance import example as legacy_example
from test_sparse_index_wire import baseline, sparse_patch, HEX_A, HEX_B, HEX_C, HEX_D
try:
    import authenticated_state as state
except ModuleNotFoundError as error:
    if error.name != 'authenticated_state':raise
    state=None

KEY=bytes(range(32))


def line(row):return engine.encoded(row)+b'\n'


class RepresentationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(state,'authenticated state representation is missing')
        self.rows=[{'meta':{'format':'model-only'}},
            {'in':1,'str':{'pre':0,'str':'a'}},{'ie':0,'nat':17},
            {'def':{'name':1,'type':0,'value':0}},
            {'in':2,'str':{'pre':0,'str':'b'}},{'ie':1,'nat':3},
            {'def':{'name':2,'type':0,'value':1}}]
        self.raw=b''.join(map(line,self.rows))
        self.recipe=state.ExportRecipe.from_baseline(self.raw)

    def test_changed_only_composition_preserves_complete_exact_export_and_parent(self):
        new={'def':{'name':1,'type':0,'value':2}}
        delta=line({'ie':2,'nat':23})+line(new)
        changed=self.recipe.append(delta,['a'])
        expected=b''.join(map(line,[self.rows[0],self.rows[1],self.rows[2],self.rows[4],self.rows[5],{'ie':2,'nat':23},new,self.rows[6]]))
        self.assertEqual(b''.join(changed.iter_chunks()),expected)
        self.assertEqual(changed.byte_count,len(expected))
        self.assertEqual(b''.join(self.recipe.iter_chunks()),self.raw)
        restored=changed.append(line(self.rows[3]),['a'])
        restored_bytes=b''.join(restored.iter_chunks())
        self.assertIn(line({'ie':2,'nat':23}),restored_bytes)
        self.assertTrue(restored_bytes.endswith(line(self.rows[3])+line(self.rows[6])))

    def test_noop_and_new_name_layer_do_not_change_unchanged_declaration_bytes(self):
        delta=line({'in':3,'str':{'pre':1,'str':'extra'}})
        changed=self.recipe.append(delta,[])
        self.assertIn(delta,b''.join(changed.iter_chunks()))
        self.assertEqual(changed.byte_count,len(self.raw)+len(delta))
        next_delta=line({'in':4,'str':{'pre':3,'str':'next'}})
        second=changed.append(next_delta,[])
        self.assertIn(next_delta,b''.join(second.iter_chunks()))

    def test_unsupported_or_ambiguous_delta_refuses_without_mutating_parent(self):
        bad=[(line({'meta':{}}),[]),(line({'quot':{}}),[]),(line({'inductive':{}}),[]),
             (line(self.rows[1]),[]),
             (line({'def':{'name':1}}),[]),
             (line({'def':{'name':1}})*2,['a']),
             (line({'thm':{'name':1}}),['a']),
             (line({'in':3,'str':{'pre':0,'str':'new'}})+line({'def':{'name':3}}),['new']),
             (b'{"def":{"name":1},"def":{"name":1}}\n',['a'])]
        for delta,names in bad:
            with self.subTest(delta=delta),self.assertRaises((ValueError,KeyError)):
                self.recipe.append(delta,names)
            self.assertEqual(b''.join(self.recipe.iter_chunks()),self.raw)

    def test_eof_terminated_rows_cannot_break_export_framing(self):
        for delta,names in [(engine.encoded(self.rows[3]),['a']),
                            (engine.encoded({'ie':2,'nat':23}),[])]:
            with self.subTest(delta=delta),self.assertRaises(ValueError):
                self.recipe.append(delta,names)


class StateAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(state,'authenticated state acceptance is missing')
        self.old=dict(status='VERIFIED',export_sha256=HEX_D,index=baseline(),provenance=dict(checker='pinned'))
        current=reconstruct_index_patch(self.old['index'],sparse_patch())
        selected,_=engine.reuse_decisions(self.old,current,self.old['provenance'],HEX_A)
        self.payload=dict(schema=state.STATE_ACCEPTANCE,status='VERIFIED',state_id=HEX_B,
            parent_state_id=HEX_C,previous_evidence=HEX_A,producer_provenance=dict(mode='state'),
            identity=dict(wire='baseline_patch_v1',value=sparse_patch()),
            obligation_count=current['count'],checked_indices=selected)

    def authenticate(self,payload=None,key=KEY,parent=HEX_C):
        raw=engine.encoded(seal(self.payload if payload is None else payload,KEY))
        return state.authenticate_state_acceptance(raw,hashlib.sha256(raw).hexdigest(),key,self.old,parent)

    def test_state_receipt_reestablishes_existing_predicate_without_file_sha(self):
        accepted=self.authenticate()
        self.assertNotIn('export_sha256',accepted)
        self.assertEqual(accepted['state_id'],HEX_B)
        self.assertEqual(accepted['checked_indices'],self.payload['checked_indices'])
        full=copy.deepcopy(self.payload)
        full['identity']=dict(wire='full_index_v1',value=accepted['index'])
        self.assertEqual(self.authenticate(full)['index'],accepted['index'])

    def test_wrong_parent_forgery_and_invalid_applicability_fail_closed(self):
        with self.assertRaises(ValueError):self.authenticate(parent=HEX_D)
        with self.assertRaises(ValueError):self.authenticate(key=b'X'*32)
        for altered in [dict(self.payload,checked_indices=[]),dict(self.payload,checked_indices=[True]),
                        dict(self.payload,state_id='bad'),dict(self.payload,obligation_count=True),
                        dict(self.payload,export_sha256=HEX_B),dict(self.payload,status='UNKNOWN'),
                        dict(self.payload,schema='wrong-domain')]:
            with self.subTest(altered=altered),self.assertRaises(ValueError):self.authenticate(altered)

    def test_state_and_full_export_acceptance_domains_are_not_interchangeable(self):
        raw=engine.encoded(seal(self.payload,KEY));identity=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):authenticate_sparse_acceptance(raw,identity,KEY,self.old)
        old,payload,raw,identity,current=legacy_example()
        with self.assertRaises(ValueError):state.authenticate_state_acceptance(raw,identity,KEY,old,HEX_C)


if __name__=='__main__':unittest.main()
