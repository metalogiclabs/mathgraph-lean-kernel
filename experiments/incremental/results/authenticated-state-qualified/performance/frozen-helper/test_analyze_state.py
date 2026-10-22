"""Independent arithmetic contracts; no checker/producer imports."""
import copy
from decimal import Decimal as D
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


HERE = Path(__file__).resolve().parent
SMOKE = Path('/workspace/kernel-audit/authenticated-state/benchmark-stable-original-v3/summary.json')


def module():
    spec = importlib.util.spec_from_file_location('analyze_state', HERE/'analyze_state.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class Contracts(unittest.TestCase):
    def test_independent_economics_ratio_of_medians_preserves_loss(self):
        a = module()
        out = a.paired([1.0, 100.0, 101.0], [1.0, 2.0, 100.0], 17, 100)
        self.assertEqual(out['median_ratio'], 50.0)
        self.assertEqual(out['candidate_values'], [1.0,100.0,101.0])
        self.assertEqual(out['control_values'], [1.0,2.0,100.0])
        self.assertEqual(out['paired_wins'], 0)
        self.assertEqual(out['status'], 'NO_SPEEDUP')
        self.assertLess(out['reduction_percent'], 0)

    def test_nested_promotion_never_double_counted_and_signed_gaps_retained(self):
        a = module()
        t = dict(producer_seconds=D('2'), baseline_validation_seconds=D('1'),
                 identity_update_seconds=D('1'), materialization_and_hash_seconds=D('1'),
                 checking_seconds=D('1'), persistence_seconds=D('3'),
                 consumer_seconds=D('8'), end_to_end_seconds=D('11'),
                 chain_promotion_seconds=D('2'), consumer_cpu_seconds=D('6'),
                 end_to_end_cpu_seconds=D('8'), baseline_validation_cpu_seconds=D('1'),
                 identity_update_cpu_seconds=D('1'), materialization_and_hash_cpu_seconds=D('1'),
                 checking_cpu_seconds=D('1'), persistence_cpu_seconds=D('3'),
                 chain_promotion_cpu_seconds=D('2'))
        out=a.partition(t)
        self.assertEqual(out['wall']['persistence_seconds'], D('3'))
        self.assertEqual(out['wall']['promotion_nested_seconds'], D('2'))
        self.assertEqual(out['wall']['consumer_gap_seconds'], D('1'))
        self.assertEqual(out['wall']['before_consumer_gap_seconds'], D('1'))
        self.assertEqual(out['wall']['disjoint_reconstruction_seconds'], D('11'))
        self.assertEqual(out['cpu']['consumer_gap_seconds'], D('-1'))
        self.assertTrue(out['cpu']['has_negative_residual'])

    def test_logical_cache_counts_small_raw_and_archived_original_not_gzip(self):
        a=module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);session=root/'primary/original/pair-0/state/session'
            session.mkdir(parents=True)
            (session/'small.json').write_bytes(b'12345')
            (session/'big.json.archive.json').write_text('{}')
            descriptor=dict(original_path='/historical/primary/original/pair-0/state/session/big.json',
                            uncompressed_bytes=1000, bytes=10)
            source=a.Source(local_summary=root/'summary.json')
            out=a.cache_size(source,'original',0,'state',[descriptor])
            self.assertEqual(out['logical_runtime_file_bytes'],1005)
            self.assertEqual(out['archive_restored_logical_bytes'],1000)
            self.assertEqual(out['surviving_raw_file_bytes'],5)
            self.assertEqual(out['logical_runtime_files'],2)
            self.assertTrue(out['namespace_complete'])

    def test_missing_session_namespace_is_explicit_partial_cache_lower_bound(self):
        a=module()
        with tempfile.TemporaryDirectory() as tmp:
            source=a.Source(local_summary=Path(tmp)/'summary.json')
            d=dict(original_path='/old/primary/original/pair-0/state/session/big.json',
                   uncompressed_bytes=1000, bytes=10)
            out=a.cache_size(source,'original',0,'state',[d])
            self.assertFalse(out['namespace_complete'])
            self.assertIsNone(out['logical_runtime_file_bytes'])
            self.assertEqual(out['archived_files_lower_bound_bytes'],1000)

    def test_duplicate_json_and_nonfinite_measurements_refused(self):
        a=module()
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):a.loads(raw)
        for x in (True,D('NaN'),D('Infinity')):
            with self.assertRaises(ValueError):a.num(x)

    def test_input_changed_after_loading_is_refused(self):
        a=module()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'summary.json';path.write_text('{"schema":"fixture"}')
            source=a.Source(local_summary=path);source.load()
            path.write_text('{"schema":"changed"}')
            with self.assertRaisesRegex(ValueError,'source bytes changed'):
                source.assert_stable()

    def test_zip_duplicate_names_and_traversal_refused_without_extraction(self):
        a=module()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('../escape','x')
                archive.writestr('authenticated-state/summary.json','{}')
            with self.assertRaisesRegex(ValueError,'unsafe ZIP'):
                a.Source(artifact=path)

    def test_explicit_zip_root_summary_resolves_runtime_namespace(self):
        a=module()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('summary.json','{}')
                archive.writestr('primary/original/pair-0/state/session/small.json','12345')
            source=a.Source(artifact=path,summary_member='summary.json')
            present,files=source.namespace('primary/original/pair-0/state/session')
            self.assertTrue(present)
            self.assertEqual(files,[('small.json',5)])

    def test_extracted_summary_with_artifact_root_resolves_namespace(self):
        a=module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);summary=root/'artifacts/authenticated-state/summary.json'
            summary.parent.mkdir(parents=True);summary.write_text('{}')
            session=summary.parent/'primary/original/pair-0/state/session';session.mkdir(parents=True)
            (session/'small.json').write_bytes(b'12345')
            source=a.Source(local_summary=summary,evidence_root=root)
            self.assertEqual(source.namespace('primary/original/pair-0/state/session'),(True,[('small.json',5)]))
            with self.assertRaisesRegex(ValueError,'outside evidence root'):
                a.Source(local_summary=summary,evidence_root=root/'elsewhere')

    def test_atomic_zip_replacement_cannot_pair_old_bytes_with_new_digest(self):
        a=module()
        with tempfile.TemporaryDirectory() as tmp:
            old=Path(tmp)/'artifact.zip';replacement=Path(tmp)/'replacement.zip'
            for path,identity in ((old,'old'),(replacement,'new')):
                with zipfile.ZipFile(path,'w') as archive:
                    archive.writestr('summary.json',json.dumps({'identity':identity}))
            source=a.Source(artifact=old,summary_member='summary.json')
            replacement.replace(old)
            with self.assertRaisesRegex(ValueError,'opened ZIP'):
                source.load()

    @unittest.skipUnless(SMOKE.exists(),'optional real development fixture unavailable')
    def test_real_stable_smoke_keeps_unqualified_status_and_all_three_arms(self):
        a=module();source=a.Source(local_summary=SMOKE);report=source.load()
        out=a.analyze(report,source,report['source_sha'])
        self.assertEqual(out['status'],'CONTEXTUAL_SMOKE_ONLY')
        self.assertFalse(out['qualification_claim'])
        p=out['profiles']['original']
        self.assertEqual(len(p['pairs']),1)
        self.assertEqual(set(p['pairs'][0]['arms']),{'state','full_export','direct'})
        self.assertEqual(p['economics']['state_vs_direct_wall_seconds']['status'],'NO_SPEEDUP')
        self.assertEqual(p['pairs'][0]['arms']['state']['warm_work']['full_export_bytes_materialized'],0)
        self.assertGreater(p['pairs'][0]['arms']['full_export']['warm_work']['full_export_bytes_materialized'],0)
        self.assertEqual(p['warm_edits']['early-definition']['updates_per_pair'],1)
        self.assertEqual(out['summary_sha256'],a.digest_file(SMOKE))
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'output';a.write_outputs(out,folder)
            markdown=(folder/'analysis.md').read_text()
            self.assertNotIn('(SPEEDUP)',markdown)
            self.assertIn('UNQUALIFIED_OBSERVATION',markdown)

    @unittest.skipUnless(SMOKE.exists(),'optional real development fixture unavailable')
    def test_forged_published_statistics_or_work_counters_fail_closed(self):
        a=module();source=a.Source(local_summary=SMOKE);report=source.load()
        wrong=copy.deepcopy(report)
        wrong['profiles']['original']['economics']['state_vs_direct_wall_seconds']['median_ratio']=D('0.001')
        with self.assertRaisesRegex(ValueError,'published economics mismatch'):
            a.analyze(wrong,source,report['source_sha'])
        wrong=copy.deepcopy(report)
        wrong['profiles']['original']['pairs'][0]['state']['steps'][0]['representation']['full_export_bytes_hashed']=1
        with self.assertRaisesRegex(ValueError,'state full-export work'):
            a.analyze(wrong,source,report['source_sha'])

    @unittest.skipUnless(SMOKE.exists(),'optional real development fixture unavailable')
    def test_forged_qualification_wrong_source_and_wrong_arm_order_refused(self):
        a=module();source=a.Source(local_summary=SMOKE);report=source.load()
        wrong=copy.deepcopy(report);wrong['correctness_qualified']=True;wrong['qualified']=True
        with self.assertRaisesRegex(ValueError,'qualification dimensions'):
            a.analyze(wrong,source,report['source_sha'])
        with self.assertRaisesRegex(ValueError,'source mismatch'):
            a.analyze(report,source,'0'*40)
        wrong=copy.deepcopy(report);wrong['profiles']['original']['pairs'][0]['order']=['direct','state','full_export']
        with self.assertRaisesRegex(ValueError,'arm order'):
            a.analyze(wrong,source,report['source_sha'])
        wrong=copy.deepcopy(report);wrong['economic_status']='QUALIFIED_SPEEDUP'
        with self.assertRaisesRegex(ValueError,'economic qualification status'):
            a.analyze(wrong,source,report['source_sha'])


if __name__=='__main__':unittest.main()
