#!/usr/bin/env python3
"""Synthetic reviewer-contract tests; never an execution/qualification report."""
import copy, importlib.util, json, tempfile, unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('audit',HERE/'review_receipt_comparison.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def synthetic_report():
 binary={k:'1'*64 for k in ('producer','checker','retained_checker','indexer','index_session','full_checker')}
 def arm(profile,variant,mode):
  n=m.TOTAL[profile];k=m.CHECKED[profile][variant]
  cmd=dict(command=['/tool','/config'],returncode=0,timed_out=False,wall_seconds=2.,completed_child_cpu_seconds=1.,stdout_sha256='1'*64,stderr_sha256='1'*64)
  timings=dict(end_to_end_seconds=1.,end_to_end_cpu_seconds=.9,checking_seconds=.2,identity_update_seconds=.1,producer_seconds=.1,persistence_seconds=.2)
  kernel=dict(kernel='sokonanoda_real_selected_declaration_check',status='checked',code=0,checked=k,total_declarations=n,scope='selected_obligations_under_caller_trusted_environment',delta_parse_and_finish_seconds=.001,selected_check_seconds=.199)
  return dict(wall_seconds=1.01,kernel_seconds=.2,identity_seconds=.1,producer_seconds=.1,persistence_seconds=.2,setup_seconds=4.,constructor_seconds=.1,start_seconds=3.8,setup_plus_apply_component_sum_seconds=5.01,
   checked=k,reused=n-k,signed_comparison_policy=mode,export_sha256='1'*64,decisions_sha256='1'*64,receipt_sha256='1'*64,result_sha256='1'*64,baseline_result_sha256='1'*64,
   snapshot=dict(sha256='1'*64,seals=15,required_seals=15),policy_tool_sha256={x:v for x,v in binary.items() if x!='full_checker'},kernel_report=kernel,
   receipt_audit=dict(issuer_hmac_valid=True,all_content_addresses_valid=True,receipt_schema=m.SPARSE,contains_complete_index=False,receipt_bytes=100),sparse_receipt_bytes=100,
   direct_rust=copy.deepcopy(cmd),full_index_oracle=copy.deepcopy(cmd),partition_audit=dict(actual_kernel_total=n,actual_kernel_checked=k,independently_replayed_reused=n-k,checked_indices=list(range(k)),reused_indices=list(range(k,n))),
   phases=dict(timings=timings,memory={phase:dict(scope='Post-phase; cumulative startup HWM; not exact phase peaks',processes={'adapter':{'VmRSS':1}}) for phase in ('producer','validation','identity','materialization','checking','persistence')},counts=dict(total=n,rechecked=k,reused=n-k),representation=dict(immutable_memfd=True,full_export_disk_bytes_written=0),producer_report={},typed_update={},native_kernel_report=kernel),
   setup_report=dict(base_evidence_id='2'*64),
   baseline_result=dict(status='VERIFIED',evidence_id='2'*64,scope=None,counts=dict(total=n,rechecked=n,scheduled=n,reused=0),checker_result=dict(code=0,stdout=json.dumps(dict(checked=n,total_declarations=n)),stderr='')),
   cpp_oracles={'leanchecker':0,'leanchecker-paranoid':0},representative_witness=[{'synthetic_only':True}])
 r=dict(schema=m.SCHEMA,source_sha='a'*40,scope=m.SCOPE,qualified=True,completed=True,correctness_passed=True,arms=list(m.MODES),control=m.MODES[0],candidate=m.MODES[1],profiles={},binary_sha256=binary)
 def eco(num,den,seed,scope,measurement,candidate='shared_json',control='canonical_json',setup=False):
  return dict(m.economics(num,den,seed),scope=scope,measurement=measurement,candidate_arm=candidate,control_arm=control,setup_in_timed_update=setup)
 for profile in m.TOTAL:
  p=dict(cross_mode_controls=[dict(source_mode=a,target_mode=b,passed=True,expected_refusal='source-owner genesis provenance mismatch',observed_refusal='source-owner genesis provenance mismatch',accepted_records_before={'a':'1'*64},accepted_records_after={'a':'1'*64}) for a,b in (m.MODES,m.MODES[::-1])],cold_restart={mode:dict(passed=True,evidence_id='1'*64,source_sha256='1'*64,arm=arm(profile,'early-definition',mode)) for mode in m.MODES})
  for cold in p['cold_restart'].values():
   cold['arm']['baseline_result']=dict(status='VERIFIED',evidence_id='2'*64,scope='authenticated_prior_baseline_not_a_new_full_check',counts=None,checker_result=None)
   cold['arm']['phases']['memory']['producer']=None
  for variant in m.VARIANTS:
   pairs=[dict(repetition=i,variant=variant,order=list(m.MODES if (i+(variant=='unrelated-definition'))%2==0 else m.MODES[::-1]),arms={mode:arm(profile,variant,mode) for mode in m.MODES}) for i in range(5)]
   case=dict(pairs=pairs,complete=True)
   for key,field,seed in [('warm_economics','wall_seconds',20261017),('selected_kernel_economics','kernel_seconds',20261027),('persistence_economics','persistence_seconds',20261030),('setup_plus_one_apply_component_sum_economics','setup_plus_apply_component_sum_seconds',20261031)]:
    vals=[x['arms']['shared_json'][field] for x in pairs]
    case[key]=eco(vals,vals,seed,m.SCOPE+' Observed '+field+'.',field,setup=field=='setup_plus_apply_component_sum_seconds')
   case['warm_cpu_economics']=eco([.9]*5,[.9]*5,20261028,m.SCOPE+' Complete apply CPU.','cpu_seconds')
   case['direct_full_rust_economics']={mode:eco([1.01]*5,[2.]*5,20261029,'Complete warm '+mode+' apply versus fresh full Rust check of the same live sealed snapshot; distinct from receipt comparison.','wall_seconds',candidate=mode,control='same_snapshot_fresh_full_rust') for mode in m.MODES}
   case['median_startup_s']={mode:4. for mode in m.MODES};p[variant]=case
  r['profiles'][profile]=p
 return r

class Contracts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.r=synthetic_report()
 def test_complete_synthetic_contract(self):
  c=m.Checks();v=m.comparison_check(self.r,'a'*40,c);self.assertEqual(set(v),set(m.TOTAL));self.assertGreater(c.count,2000)
 def test_actual_cold_baseline_projection_is_prior_authentication(self):
  # Exact projection from DeltaSession.start() and Qualification.sample(): no
  # fresh baseline kernel count/checker claim is present on authenticated restart.
  r=copy.deepcopy(self.r);m.comparison_check(r,'a'*40,m.Checks())
  for profile in m.TOTAL:
   for mode in m.MODES:
    self.assertIsNone(r['profiles'][profile]['cold_restart'][mode]['arm']['baseline_result']['counts'])
 def test_actual_cold_producer_memory_is_missing(self):
  # Exact field in all four cold arms of the actual 5dfe CI artifact.
  r=copy.deepcopy(self.r);m.comparison_check(r,'a'*40,m.Checks())
  for profile in m.TOTAL:
   for mode in m.MODES:
    self.assertIsNone(r['profiles'][profile]['cold_restart'][mode]['arm']['phases']['memory']['producer'])
 def test_missing_exited_process_observation_is_not_zero(self):
  r=copy.deepcopy(self.r)
  a=r['profiles']['original']['early-definition']['pairs'][0]['arms']['shared_json']
  a['phases']['memory']['persistence']['processes']['retained_kernel']=None
  m.arm_check(m.Checks(),a,'original','early-definition','shared_json',r['binary_sha256'])
 def test_thirty_two_intended_failures(self):
  failures=m.falsifiers(self.r,'a'*40);self.assertEqual(len(failures),32);self.assertTrue(all(x['passed'] for x in failures))
  (HERE/'reviewer-falsifier-tests.json').write_text(json.dumps(dict(scope='Synthetic independent reviewer contract tests, not qualification evidence',qualification_claim=False,passed=True,falsifiers=failures),indent=2)+'\n')
 def test_bool_is_not_integer(self):
  with self.assertRaises(ValueError):m.Checks().eq('typed equality',True,1)
 def test_duplicate_json_keys_rejected(self):
  with self.assertRaises(ValueError):m.parse('{"a":1,"a":2}')
 def test_protected_actual_cause_enforcement(self):
  r=dict(source_git_commit='a'*40,run_completed=True,correctness_passed=True,qualification_status='PASS',
   gates=[dict(name=str(i),required=True,passed=True) for i in range(246)],samples=[],controls={})
  for variant in ('baseline','theorem-leaf')+m.VARIANTS:
   for rep in range(5):
    a=copy.deepcopy(self.r['profiles']['original']['early-definition']['pairs'][0]['arms']['shared_json'])
    k=m.CHECKED['original'][variant];n=m.TOTAL['original'];p=dict(actual_kernel_total=n,actual_kernel_checked=k,independently_replayed_reused=n-k,checked_indices=list(range(k)),reused_indices=list(range(k,n)))
    r['samples'].append(dict(variant=variant,repetition=rep,cold_replay=False,partition_audit=p,direct_rust=a['direct_rust'],setup_report=dict(delta_provenance=dict(selected_kernel_backend='sha-pinned-retained-parser-v1',receipt_index_comparison='shared_json')),persisted_acceptance_audit=a['receipt_audit']))
  s=copy.deepcopy(r['samples'][0]);s.update(cold_replay=True,repetition='cold-restart');r['samples'].append(s)
  r['controls']={name:dict(observed_refusal=cause) for name,cause in m.CAUSES.items()}
  for name in m.KERNEL_NEG:
   cause='selected declaration checker thread panicked' if name=='signed-invalid-proof' else 'unrecognized or repeated simple declaration replacement' if name=='signed-invalid-axiom' else 'expected u16'
   r['controls'][name]=dict(result=dict(status='REJECTED',evidence_id=None,checker_result=dict(code=1,stderr=cause),counts=dict(scheduled=0)),independent_kernel_rejections={k:dict(returncode=1,timed_out=False) for k in ('rust','leanchecker','leanchecker-paranoid')},independent_zero_selected_parser=dict(returncode=1,timed_out=False))
  m.protected_check(m.Checks(),r,'original','a'*40)
  for name in ('forged-attestation','signed-invalid-proof'):
   value=copy.deepcopy(r)
   if name=='forged-attestation':value['controls'][name]['observed_refusal']='producer request timeout'
   else:value['controls'][name]['result']['checker_result']['stderr']='unrelated process fault'
   with self.assertRaises(ValueError):m.protected_check(m.Checks(),value,'original','a'*40)
 def test_negative_measurement(self):
  with self.assertRaises(ValueError):m.Checks().num('duration',-1)
 def test_patch_changes_cannot_modify_topology(self):
  row=dict(index=0,key='k',name='a',kind='def',deps=[],own='1'*64,closure='2'*64)
  old=dict(count=1,declarations=[row],builtins={});new=dict(row,name='b')
  patch=dict(schema='mathgraph.export-identity-baseline-patch.v1',count=1,declarations=[new],builtins={})
  with self.assertRaises(ValueError):m.independent_index(old,patch,m.Checks())
 def test_composite_reconstruction_preserves_schedule(self):
  base=b'{"meta":{}}\n{"in":1,"str":{"pre":0,"str":"a"}}\n{"ie":0,"natVal":"1"}\n{"def":{"name":1,"value":0}}\n'
  delta=b'{"ie":1,"natVal":"2"}\n{"def":{"name":1,"value":1}}\n'
  expected=b'{"meta":{}}\n{"in":1,"str":{"pre":0,"str":"a"}}\n{"ie":0,"natVal":"1"}\n'+delta
  actual=m.composite_digest(m.baseline_layout(base,m.Checks()),delta,['a'],m.Checks())
  self.assertEqual(actual,(m.sha(expected),len(expected)))
if __name__=='__main__':unittest.main(verbosity=2)
