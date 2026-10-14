import sys,unittest,subprocess,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_transfer_runner import acquire_repair,assert_pinned_clean
from native_closure_discovery import digest

class NativeTransferRunnerTests(unittest.TestCase):
 def setUp(self):
  self.row=dict(name='Binius.sample',label='parent',proof='theorem sample : True := by\n  trivial\n',operator='local_expression_sharing')
  self.result=dict(compiled=False,proof_sha256=digest(self.row['proof']),per_version=[dict(errors=['unsolved goals'])])
  self.log='Arena/Binius_sample.lean:101:1: error: unsolved goals\n⊢ True'
 def test_supported_source_bound_failure_proposes_closure(self):
  r=acquire_repair(self.row,self.result,dict(status='completed',returncode=1,output=self.log),100)
  self.assertIn('all_goals rfl',r['proof']);self.assertEqual(r['parent_sha256'],digest(self.row['proof']))
 def test_other_errors_are_not_repaired(self):
  self.result['per_version'][0]['errors']=['type mismatch']
  self.assertIsNone(acquire_repair(self.row,self.result,dict(status='completed',returncode=1,output=self.log),100))
 def test_partial_diagnostics_are_not_repair_authority(self):
  self.assertIsNone(acquire_repair(self.row,self.result,dict(status='timeout',output=self.log),100))
 def test_wrong_parent_source_fails_closed(self):
  self.result['proof_sha256']='wrong'
  with self.assertRaises(ValueError):acquire_repair(self.row,self.result,dict(status='completed',returncode=1,output=self.log),100)

class HarnessProvenanceTests(unittest.TestCase):
 def test_modified_tracked_harness_is_rejected_even_at_correct_head(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   def git(*args):return subprocess.check_output(['git',*args],cwd=p,text=True,stderr=subprocess.DEVNULL).strip()
   git('init');(p/'arena.py').write_text('original')
   git('add','arena.py');git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','fixture')
   pin=git('rev-parse','HEAD');assert_pinned_clean(p,pin)
   (p/'arena.py').write_text('modified')
   with self.assertRaises(ValueError):assert_pinned_clean(p,pin)
 def test_wrong_revision_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   subprocess.run(['git','init'],cwd=p,check=True,capture_output=True)
   with self.assertRaises(ValueError):assert_pinned_clean(p,'wrong')
