import contextlib,io,json,pathlib,unittest
from reconcile_discovery_v17 import run
from reconcile_v16 import qualify
ROOT=pathlib.Path(__file__).resolve().parents[1]
class DiscoveryAdmissionTests(unittest.TestCase):
 def test_historical_v17_packet_reproduces_from_immutable_native_evidence(self):
  with contextlib.redirect_stdout(io.StringIO()):run(check=True,historical=True)
 def test_both_admitted_proofs_have_complete_native_authority(self):
  audit=json.loads((ROOT/'evidence/retained_exact_full_version_audit_20261015_v17.json').read_text())
  bank=[json.loads(x) for x in (ROOT/'experiments/source_native_closure_v3.jsonl').read_text().splitlines()]
  scores=[json.loads(x) for x in (ROOT/'evidence/native_closure_discovery_v3/results.jsonl').read_text().splitlines()]
  changed=audit['change_fingerprint']['changed_theorems'];self.assertEqual(len(changed),2)
  for name in changed:
   record=next(r for r in audit['records'] if r['name']==name)
   candidate=next(r for r in bank if r['name']==name and 'warranted_'+r['label']==record['label'])
   score=next(r for r in scores if r['name']==name and r['candidate_label']==candidate['label'])
   qualify(candidate,record['proof_sha256'],score,record['required_versions'])
if __name__=='__main__':unittest.main()
