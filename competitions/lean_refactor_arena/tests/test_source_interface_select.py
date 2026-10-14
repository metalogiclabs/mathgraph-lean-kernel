import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('selector',Path(__file__).resolve().parents[1]/'source_interface_select.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(label,score=100):
 return dict(name='t',candidate_label=label,objective_sum_pct=score,length=50,heartbeats=100,
  compiled=True,statement_ok=True,eligible=True,compat={'v4.32.0':True},
  per_version=[dict(version='v4.32.0',tested=True,ok=True)])
class SelectionTests(unittest.TestCase):
 def test_rejects_cheap_uncompiled_and_preserves_tie(self):
  bad=row('bad',200);bad['compiled']=False
  result=m.select([row('v16_control'),row('tie'),bad])['results'][0]
  self.assertEqual(result['selected_label'],'v16_control')
 def test_requires_actual_version_test(self):
  for changes in [dict(per_version=[]),dict(untested=['v4.32.0']),dict(compat={'v4.32.0':False}),dict(forbidden=['sorry'])]:
   r=row('candidate',101);r.update(changes)
   self.assertFalse(m.lawful(r))
 def test_control_failure_stops_selection(self):
  r=row('v16_control');r['statement_ok']=False
  with self.assertRaises(ValueError):m.select([r,row('candidate',101)])
 def test_native_joint_objective_selects_improvement(self):
  result=m.select([row('v16_control'),row('gain',101)])
  self.assertEqual(result['results'][0]['objective_gain'],1)
  self.assertFalse(result['portfolio_changed'])
if __name__=='__main__':unittest.main()

class TransferTests(unittest.TestCase):
 def test_transfer_never_selects_using_target_cost(self):
  source=[row('v16_control'),row('source_gain',101)]
  target=[row('v16_control'),row('target_gain',150)]
  for r in source:r['name']='source';r['operator']='control' if r['candidate_label']=='v16_control' else 'fuse'
  for r in target:r['name']='target';r['operator']='control' if r['candidate_label']=='v16_control' else 'infer'
  result=m.transfer(source+target,'source','target')
  self.assertEqual(result['frozen_operator'],'fuse')
  self.assertEqual(result['status'],'NO_APPLICABLE_TRANSFER')
 def test_same_operator_gain_transfers_and_control_is_ablation(self):
  rows=[]
  for name in ['source','target']:
   a=row('v16_control');b=row(name+'_gain',101)
   a.update(name=name,operator='control');b.update(name=name,operator='infer');rows.extend([a,b])
  result=m.transfer(rows,'source','target')
  self.assertEqual(result['status'],'MEASURED_OPERATOR_TRANSFER')
  self.assertEqual(result['target_objective_gain'],1)
 def test_no_source_gain_means_no_learned_policy(self):
  a=row('v16_control');a['operator']='control'
  b=row('tie');b['operator']='infer'
  self.assertEqual(m.transfer([a,b],'t','other')['status'],'NO_SOURCE_GAIN')
