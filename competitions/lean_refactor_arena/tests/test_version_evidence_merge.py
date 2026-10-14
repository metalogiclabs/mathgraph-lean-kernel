import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from version_evidence_merge import merge_versions
class VersionEvidenceMergeTests(unittest.TestCase):
 def setUp(self):
  self.p=dict(name='sample',candidate_label='winner',proof_sha256='proof',public_harness_sha='pin',compat={'v1':True},per_version=[dict(version='v1',ok=True,tested=True,heartbeats=100)],heartbeats=100,compiled=True,eligible=True,survival_pct=100)
  self.other=dict(self.p,compat={'v0':True},per_version=[dict(version='v0',ok=True,tested=True,heartbeats=200)],heartbeats=200)
 def test_preserves_primary_cost_and_adds_native_compatibility(self):
  r=merge_versions(self.p,[self.other],['v1','v0']);self.assertEqual(r['heartbeats'],100);self.assertEqual(r['compat'],{'v1':True,'v0':True});self.assertTrue(r['all_versions'])
 def test_wrong_source_cannot_supply_version_coverage(self):
  self.other['proof_sha256']='wrong'
  with self.assertRaises(ValueError):merge_versions(self.p,[self.other],['v1','v0'])
 def test_missing_or_duplicate_versions_fail_closed(self):
  for others in ([],[self.other,self.other]):
   with self.assertRaises(ValueError):merge_versions(self.p,others,['v1','v0'])
 def test_native_rejection_is_preserved(self):
  self.other['compat']['v0']=False;self.other['per_version'][0]['ok']=False
  r=merge_versions(self.p,[self.other],['v1','v0']);self.assertFalse(r['eligible']);self.assertFalse(r['compat']['v0']);self.assertEqual(r['survival_pct'],50)

 def test_declaration_rejection_cannot_be_lost_in_merge(self):
  self.other['statement_ok']=False
  with self.assertRaises(ValueError):merge_versions(self.p,[self.other],['v1','v0'])
