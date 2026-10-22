#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).with_name('controls.py')
if path.exists():
 spec=importlib.util.spec_from_file_location('controls',path)
 controls=importlib.util.module_from_spec(spec);spec.loader.exec_module(controls)
else:controls=None

class ControlsContracts(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(controls,'independent controls helper must exist')
 def test_exact_required_control_names_cannot_be_self_declared(self):
  expected=tuple('control-'+str(i) for i in range(32))
  report=dict(schema='mathgraph.revision-chain-controls.v1',source_sha='a'*40,
              profile='original-v1',passed=True,required_controls=list(expected),
              controls=[dict(name=n,passed=True) for n in expected])
  self.assertEqual(set(controls.validate_header(report,expected,'a'*40,'original')),set(expected))
  report['required_controls']=report['required_controls'][:-4]
  report['controls']=report['controls'][:-4]
  with self.assertRaises(ValueError):controls.validate_header(report,expected,'a'*40,'original')
 def test_wrong_source_duplicate_and_false_control_refuse(self):
  expected=tuple('control-'+str(i) for i in range(32))
  def valid():return dict(schema='mathgraph.revision-chain-controls.v1',source_sha='a'*40,
              profile='original-v1',passed=True,required_controls=list(expected),
              controls=[dict(name=n,passed=True) for n in expected])
  for mutate in [lambda r:r.__setitem__('source_sha','b'*40),
                 lambda r:r['controls'][0].__setitem__('passed',False),
                 lambda r:r['controls'][0].__setitem__('name',expected[1]),
                 lambda r:r.__setitem__('profile','std-hashmap-expanded-v1')]:
   report=valid();mutate(report)
   with self.assertRaises(ValueError):controls.validate_header(report,expected,'a'*40,'original')

 def test_profile_result_substitution_refuses(self):
  fn=getattr(controls,'validate_result_profile',None)
  self.assertTrue(callable(fn),'result workload profile must be independently bound')
  result=dict(producer_provenance={'profile':'original-v1'},counts={'total':3436})
  fn(result,'original',3436)
  with self.assertRaises(ValueError):fn(result,'expanded',11653)
  with self.assertRaises(ValueError):fn(result,'original',True)

 def test_zero_selected_negative_cannot_hide_checked_or_foreign_evidence(self):
  fn=getattr(controls,'validate_zero_selected_rejection',None)
  self.assertTrue(callable(fn),'zero-selected negative must carry every parent witness')
  row=dict(name='A',index=0,own='c'*64,closure='d'*64,deps=[])
  result=dict(previous_evidence='a'*64,counts=dict(total=1,scheduled=0,reused=1,invalidated=0,rechecked=None),
    decisions=[dict(name='A',index=0,status='VERIFIED_REUSED',evidence_id='a'*64,dependency_witness=dict(own='c'*64,closure='d'*64,direct=[]))])
  fn(result,dict(count=1,declarations=[row]),'a'*64)
  result['decisions'][0]['evidence_id']='b'*64
  with self.assertRaises(ValueError):fn(result,dict(count=1,declarations=[row]),'a'*64)

if __name__=='__main__':unittest.main(verbosity=2)
