#!/usr/bin/env python3
"""Synthetic falsifiers for report comparison; no actual CI result is fabricated."""
import copy,json,unittest
from pathlib import Path
import compare_inputs as helper
HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local-replay-summary.json'
def fixtures():
 local=json.loads(LOCAL.read_bytes());roles={(x['profile'],x['name']):dict(sha256=x['sha256'],bytes=x['bytes'])for x in local['full_case_inputs']}
 for x in local['retained_case_inputs']:roles[x['profile'],x['name']]=dict(sha256=x['complete_input_sha256'],bytes=x['complete_input_bytes'])
 def arm(profile,role,mode):return dict(snapshot=copy.deepcopy(roles[profile,role]),export_sha256=roles[profile,role]['sha256'],signed_comparison_policy=mode,kernel_report=dict(code=0),direct_rust=dict(returncode=0,timed_out=False))
 protected={};comparison=dict(schema='mathgraph.retained-receipt-index-comparison.v1',source_sha=local['source'],completed=True,correctness_passed=True,qualified=True,profiles={})
 for profile in['original','expanded']:
  q=dict(source_git_commit=local['source'],source_git_status='',run_completed=True,correctness_passed=True,qualification_status='PASS',samples=[],controls={},gates=[])
  for role in helper.POSITIVES:
   for n in range(5):q['samples'].append(dict(variant=role,repetition=n,cold_replay=False,evidence_id='e'*64,direct_rust=dict(returncode=0,timed_out=False),snapshot=copy.deepcopy(roles[profile,role])))
   if role=='early-definition':q['samples'].append(dict(variant=role,repetition='cold-restart',cold_replay=True,evidence_id='e'*64,direct_rust=dict(returncode=0,timed_out=False),snapshot=copy.deepcopy(roles[profile,role])))
  for role in helper.NEGATIVES:
   q['controls'][role]=dict(snapshot=copy.deepcopy(roles[profile,role]),result=dict(status='REJECTED',checker_result=dict(code=1),evidence_id=None,counts=dict(scheduled=0)),independent_kernel_rejections={k:dict(returncode=1,timed_out=False)for k in ['rust','normal','paranoid']},independent_zero_selected_parser=dict(returncode=1,timed_out=False))
   q['gates'].append(dict(name='no_new_persisted_acceptance:'+role,passed=True))
  protected[profile]=q;p={}
  for role in helper.POSITIVES:p[role]=dict(complete=True,pairs=[dict(repetition=n,arms={mode:arm(profile,role,mode)for mode in helper.MODES})for n in range(5)])
  p['cold_restart']={mode:dict(passed=True,arm=arm(profile,'early-definition',mode))for mode in helper.MODES};comparison['profiles'][profile]=p
 return local,protected,comparison
class ParityTests(unittest.TestCase):
 def run_report(self,mutation=None):
  x=fixtures()
  if mutation:mutation(*x)
  return helper.compare(*x)
 def test_complete_synthetic_shapes_pass_and_overwrite_is_separate(self):
  r=self.run_report();self.assertEqual(r['status'],'PASS_EXACT_REPORTED_CI_INPUT_PARITY');self.assertEqual(r['counts']['matched_snapshots'],74);self.assertEqual(r['counts']['covered_role_keys'],12);self.assertEqual(len(r['extra_local_overwrite_roles']),2)
 def test_matching_filename_and_count_cannot_hide_hash_mismatch(self):
  r=self.run_report(lambda l,p,c:p['original']['samples'][0]['snapshot'].update(sha256='f'*64));self.assertEqual(len(r['mismatched']),1);self.assertFalse(r['missing']);self.assertNotEqual(r['status'],'PASS_EXACT_REPORTED_CI_INPUT_PARITY')
 def test_byte_size_mismatch_with_equal_sha_fails(self):
  r=self.run_report(lambda l,p,c:c['profiles']['expanded']['early-definition']['pairs'][0]['arms']['shared_json']['snapshot'].update(bytes=123));self.assertEqual(len(r['mismatched']),1)
 def test_missing_snapshot_fields_are_distinct_from_mismatch(self):
  r=self.run_report(lambda l,p,c:p['expanded']['controls']['signed-invalid-proof']['snapshot'].pop('sha256'));self.assertEqual(len(r['missing']),1);self.assertFalse(r['mismatched'])
 def test_missing_control_and_report_fail_explicitly(self):
  r=self.run_report(lambda l,p,c:p['original']['controls'].pop('signed-invalid-axiom'));self.assertTrue(r['missing']);self.assertFalse(r['mismatched'])
  l,p,c=fixtures();p['expanded']=None;r=helper.compare(l,p,c);self.assertTrue(r['missing']);self.assertNotEqual(r['status'],'PASS_EXACT_REPORTED_CI_INPUT_PARITY')
 def test_bool_size_is_malformed_not_equal_integer(self):
  r=self.run_report(lambda l,p,c:p['original']['samples'][0]['snapshot'].update(bytes=True));self.assertEqual(r['mismatched'][0]['reason'],'Malformed reported snapshot hash/size')
 def test_source_drift_fails_even_when_all_hashes_match(self):
  r=self.run_report(lambda l,p,c:c.update(source_sha='0'*40));self.assertFalse(r['mismatched']);self.assertTrue(r['metadata_errors'])
 def test_accepted_negative_or_missing_zero_parser_fails(self):
  r=self.run_report(lambda l,p,c:p['original']['controls']['signed-invalid-proof']['result'].update(evidence_id='a'*64));self.assertTrue(r['metadata_errors'])
  r=self.run_report(lambda l,p,c:p['expanded']['controls']['unused-invalid-node-zero-selection-parser'].pop('independent_zero_selected_parser'));self.assertTrue(r['metadata_errors'])
 def test_cold_snapshot_is_compared_and_policy_checked(self):
  r=self.run_report(lambda l,p,c:c['profiles']['original']['cold_restart']['shared_json']['arm']['snapshot'].update(sha256='a'*64));self.assertEqual(len(r['mismatched']),1)
  r=self.run_report(lambda l,p,c:c['profiles']['original']['cold_restart']['shared_json']['arm'].update(signed_comparison_policy='foreign'));self.assertTrue(r['metadata_errors'])
 def test_local_repeated_role_inconsistency_fails(self):
  r=self.run_report(lambda l,p,c:l['retained_case_inputs'][0].update(complete_input_sha256='b'*64));self.assertTrue(r['metadata_errors'])
 def test_missing_pair_arm_or_duplicate_repetition_fails(self):
  r=self.run_report(lambda l,p,c:c['profiles']['original']['early-definition']['pairs'][0]['arms'].pop('canonical_json'));self.assertTrue(r['missing'])
  r=self.run_report(lambda l,p,c:c['profiles']['original']['early-definition']['pairs'][0].update(repetition=1));self.assertTrue(r['metadata_errors'])
if __name__=='__main__':unittest.main()
