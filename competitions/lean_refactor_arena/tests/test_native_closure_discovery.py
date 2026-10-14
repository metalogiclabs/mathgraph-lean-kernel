import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('closure',Path(__file__).resolve().parents[1]/'native_closure_discovery.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ClosureTests(unittest.TestCase):
 def test_native_error_maps_to_nested_proof_scope(self):
  proof='theorem t : True := by\n  have h : x = x := by\n    simp only []\n  exact True.intro\n'
  log='Arena/T.lean:102:22: error: unsolved goals\n⊢ x = x\n'
  row=m.repair({'name':'t','proof':proof,'operator':'local_expression_sharing'},log,100)
  self.assertIn('    simp only []\n    all_goals rfl\n  exact',row['proof'])
  self.assertEqual(row['discovered']['proof_scope_line'],2)
 def test_rejects_wrong_mapping_and_non_goal_errors(self):
  row={'name':'t','proof':'theorem t : True := by\n  exact h\n'}
  self.assertIsNone(m.repair(row,'Arena/T.lean:99:2: error: unsolved goals',100))
  self.assertIsNone(m.repair(row,'Arena/T.lean:101:2: error: Application type mismatch',100))
 def test_top_scope_repair_preserves_statement(self):
  p='theorem t : x = x := by\n  field_simp\n'
  r=m.repair({'name':'t','proof':p},'Arena/T.lean:101:25: error: unsolved goals',100)
  self.assertTrue(r['proof'].endswith('  all_goals rfl\n'))
  self.assertEqual(r['proof'].split(':= by')[0],p.split(':= by')[0])
if __name__=='__main__':unittest.main()
