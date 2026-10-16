#!/usr/bin/env python3
"""Adversarial issuer-bound sparse acceptance tests (no counterfeit kernel claims)."""
import copy
import hashlib
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine
from producer_delta import (SPARSE_ACCEPTANCE, authenticate_sparse_acceptance,
                            reconstruct_index_patch, seal)
from test_sparse_index_wire import baseline, sparse_patch, HEX_A, HEX_B, HEX_C, HEX_D

KEY = bytes(range(32))
FOREIGN = b'\x23'*32

def example():
    original = dict(status='VERIFIED',export_sha256=HEX_D,
                    index=baseline(),provenance=dict(policy='frozen',checker='pinned'))
    changed = reconstruct_index_patch(original['index'], sparse_patch())
    checked,_ = engine.reuse_decisions(original,changed,original['provenance'],HEX_A)
    receipt = dict(schema=SPARSE_ACCEPTANCE,status='VERIFIED',
                   export_sha256=HEX_B,previous_evidence=HEX_A,
                   delta_representation=HEX_C,
                   producer_provenance=dict(source_root=HEX_A,issuer='local'),
                   index_patch=sparse_patch(),obligation_count=changed['count'],
                   checked_indices=checked)
    raw=engine.encoded(seal(receipt,KEY))
    return original,receipt,raw,hashlib.sha256(raw).hexdigest(),changed

class SparseAcceptanceTests(unittest.TestCase):
    def test_authenticate_reconstruct_and_exact_partition(self):
        old,receipt,raw,ident,current=example()
        result=authenticate_sparse_acceptance(raw,ident,KEY,old)
        self.assertEqual(result['index'],current)
        self.assertEqual(result['checked_indices'],receipt['checked_indices'])
        self.assertEqual(result['reused_indices'],
                         [i for i in range(current['count']) if i not in receipt['checked_indices']])
        self.assertNotIn('index',receipt)
        self.assertNotIn('reused_indices',receipt)
    def test_tampered_receipt_wrong_hash_or_foreign_issuer_fail_closed(self):
        old,receipt,raw,ident,_=example()
        for data,key,digest in [(raw,FOREIGN,ident),(raw,KEY,HEX_A),
                                (raw+b' ',KEY,ident)]:
            with self.subTest(key=key,digest=digest),self.assertRaises(ValueError):
                authenticate_sparse_acceptance(data,digest,key,old)
    def test_signed_but_invalid_applicability_is_rejected(self):
        old,receipt,raw,ident,_=example()
        for altered in [
            dict(receipt,checked_indices=[]),
            dict(receipt,checked_indices=[0,0]),
            dict(receipt,checked_indices=[True]),
            dict(receipt,checked_indices=[100]),
            dict(receipt,obligation_count=1),
            dict(receipt,obligation_count=True),
            dict(receipt,schema='mathgraph.incremental-lean.v1'),
            dict(receipt,status='UNKNOWN'),
            dict(receipt,unexpected_authority='all'),
            dict(receipt,index_patch=dict(sparse_patch(),count=4)),
            dict(receipt,index_patch=dict(sparse_patch(),declarations=[])),
        ]:
            payload=engine.encoded(seal(altered,KEY))
            with self.subTest(altered=altered),self.assertRaises(ValueError):
                authenticate_sparse_acceptance(payload,hashlib.sha256(payload).hexdigest(),KEY,old)
    def test_malformed_hashes_missing_verified_baseline_and_duplicate_keys_refuse(self):
        old,receipt,_,_,_=example()
        for field,bad in [('export_sha256','not-a-hash'),
                          ('previous_evidence','wrong'),
                          ('delta_representation',0)]:
            malformed=dict(receipt,**{field:bad})
            raw=engine.encoded(seal(malformed,KEY))
            with self.subTest(field=field),self.assertRaises(ValueError):
                authenticate_sparse_acceptance(raw,hashlib.sha256(raw).hexdigest(),KEY,old)
        wrong=copy.deepcopy(old);wrong['status']='UNKNOWN'
        raw=engine.encoded(seal(receipt,KEY))
        with self.assertRaisesRegex(ValueError,'verified baseline'):
            authenticate_sparse_acceptance(raw,hashlib.sha256(raw).hexdigest(),KEY,wrong)
        forged=b'{"payload":{"schema":"first","schema":"second"},"hmac_sha256":"bad"}'
        with self.assertRaises(ValueError):
            authenticate_sparse_acceptance(forged,hashlib.sha256(forged).hexdigest(),KEY,old)

if __name__=='__main__':
    unittest.main()
