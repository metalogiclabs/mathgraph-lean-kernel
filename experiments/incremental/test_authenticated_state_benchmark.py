#!/usr/bin/env python3
"""Fail-closed measurement-record contracts, not simulated kernel verdicts."""
import copy
import unittest

from benchmark_authenticated_state import compact_result


class MeasurementContract(unittest.TestCase):
    def setUp(self):
        self.expected = dict(source_root='a'*64, counts=dict(total=3, scheduled=1,
            rechecked=1, reused=2, invalidated=1), snapshot=dict(bytes=100, sha256='b'*64))
        self.actual = dict(status='VERIFIED', evidence_id='c'*64, previous_evidence='d'*64,
            export_sha256=None, state_id='e'*64, revision_chain={},
            counts=copy.deepcopy(self.expected['counts']),
            native_kernel_report=dict(status='checked', code=0, checked=1, total_declarations=3),
            producer_provenance={}, representation=dict(export_bytes=100,
                full_export_bytes_materialized=0, full_export_bytes_hashed=0,
                full_successor_bytes_read=0, full_export_disk_bytes_written=0), timings={})

    def compact(self):
        return compact_result(self.actual, self.expected, 'a'*64, 'state')

    def test_compaction_preserves_real_identity_and_counts_without_complete_decisions(self):
        self.actual['decisions']=['large observation is intentionally discarded']
        result=self.compact()
        self.assertEqual(result['state_id'],'e'*64)
        self.assertNotIn('decisions',result)
        self.assertIsNone(result['export_sha256'])

    def test_state_record_refuses_full_export_work_or_counterfeit_export_sha(self):
        for field in ('full_export_bytes_materialized','full_export_bytes_hashed',
                      'full_successor_bytes_read','full_export_disk_bytes_written'):
            original=self.actual['representation'][field]
            self.actual['representation'][field]=1
            with self.subTest(field=field),self.assertRaises(ValueError):self.compact()
            self.actual['representation'][field]=original
        self.actual['export_sha256']='e'*64
        with self.assertRaises(ValueError):self.compact()

    def test_boolean_measurements_cannot_masquerade_as_integer_counts(self):
        self.actual['counts']['scheduled']=True
        with self.assertRaises(ValueError):self.compact()

    def test_boolean_zero_does_not_establish_observed_byte_count(self):
        self.actual['representation']['full_successor_bytes_read']=False
        with self.assertRaises(ValueError):self.compact()

    def test_missing_or_inconsistent_observed_kernel_work_is_refused(self):
        self.actual['native_kernel_report']['checked']=0
        with self.assertRaises(ValueError):self.compact()


if __name__=='__main__':unittest.main()
