#!/usr/bin/env python3
"""Independent compact retained-index review; no runtime/controller imports.

Only pinned independent review helpers are reused. No kernel is run, omitted
full witnesses are not read, and historical private HMACs are not authenticated.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import random
import re
import stat
import statistics
import subprocess
import tempfile
import zipfile

BASE='4496042c75368f6c35675a9b131c960080afa518'
HELPERS={'review-compact-ci.py':'0a71217ca636697b4861b664a8ced1584285337a7f1605891c58e27497fc7c47',
         'review-evidence.py':'ee46a394b83190677a76c8735ec423b292864efcc23a308cf66932283bbd3bb9'}
PROFILES=('original','expanded'); VARIANTS=('early-definition','unrelated-definition'); ARMS=('qualified449','full','retained')
COUNT={'original':3436,'expanded':11653}
KERNEL={('original','early-definition'):413,('original','unrelated-definition'):1,
        ('expanded','early-definition'):672,('expanded','unrelated-definition'):260}
STORAGE_CAUSES={'forged_capsule_hmac':'issuer authentication failed',
 'corrupt_capsule':'storage capsule content address mismatch','corrupt_base':'evidence content address mismatch',
 'wrong_key':'issuer authentication failed','validly_resigned_bad_patch':'evidence content address mismatch',
 'validly_resigned_bad_patch_new_content_id':'evidence issuer authentication failed',
 'validly_resigned_version':'wrong authority domain','validly_resigned_duplicate_patch':'patch positions',
 'validly_resigned_baseline_guard':'baseline patch guard','fresh_interpreter_full':None,'fresh_interpreter_sparse':None}


def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def strict(raw):
 def pairs(rows):
  result={}
  for k,v in rows:
   if k in result:raise ValueError('duplicate JSON key:'+k)
   result[k]=v
  return result
 def constant(x):raise ValueError('nonfinite JSON:'+x)
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)


class C:
 def __init__(self):self.count=0
 def need(self,name,value):
  self.count+=1
  if not value:raise ValueError(name)
 def eq(self,name,a,b):
  if type(a) is set:a=sorted(a)
  if type(b) is set:b=sorted(b)
  self.need(name,canonical(a)==canonical(b))
 def num(self,name,x):self.need(name,type(x) in (int,float) and math.isfinite(x) and x>=0)
 def integer(self,name,x):self.need(name,type(x) is int and x>=0)
 def near(self,name,a,b):
  self.num(name+':recorded',a);self.num(name+':recomputed',b)
  self.need(name,math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12))
 def hex(self,name,x):self.need(name,type(x) is str and re.fullmatch('[0-9a-f]{64}',x) is not None)


def paired(numerator,denominator,storage=False):
 if any(x==0 for x in numerator+denominator):
  return dict(status='UNRESOLVED_CLOCK_GRANULARITY',passed=False)
 med=statistics.median;ratio=med(numerator)/med(denominator)
 rng=random.Random(20261016);draws=[];n=len(numerator)
 for _ in range(10000):
  ids=[rng.randrange(n) for _ in range(n)]
  draws.append(med([numerator[i] for i in ids])/med([denominator[i] for i in ids]))
 draws.sort();bounds=[draws[249],draws[9749]];wins=sum(a<b for a,b in zip(numerator,denominator))
 passed=ratio<1 and (wins>=4 if storage else 2*wins>n) and bounds[1]<1 and n>=5
 return dict(apply_median_wall_seconds=med(numerator),direct_median_wall_seconds=med(denominator),
  median_ratio=ratio,paired_count=n,paired_wins=wins,bootstrap_ratio_interval_95=bounds,
  bootstrap_repetitions=10000,bootstrap_seed=20261016,passed=passed,status='SPEEDUP' if passed else 'NO_SPEEDUP')


def economic_check(c,label,record,numerator,denominator,storage=False,incomplete=False):
 for x in numerator+denominator:c.num(label+':sample',x)
 expected=paired(numerator,denominator,storage)
 if incomplete and len(numerator)<5 and expected['status']!='UNRESOLVED_CLOCK_GRANULARITY':
  expected.update(status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS',passed=False)
 if expected['status']=='UNRESOLVED_CLOCK_GRANULARITY':
  c.eq(label+':status',record.get('status'),expected['status']);c.need(label+':no-promotion',record.get('passed') is False)
  return expected
 aliases={'apply_median_wall_seconds':'sparse_median_wall_seconds','direct_median_wall_seconds':'full_median_wall_seconds',
          'median_ratio':'sparse_over_full_median_ratio'} if storage else {}
 for f,v in expected.items():
  actual=record.get(aliases.get(f,f))
  if type(v) is float:c.near(label+':'+f,actual,v)
  else:c.eq(label+':'+f,actual,v)
 return expected


def stats_review(c,label,s,cone,total,retained):
 for field in ('compute_wall_seconds','compute_cpu_seconds','finish_wall_seconds','finish_cpu_seconds'):
  c.num(label+':'+field,s.get(field))
 c.need(label+':whole-contains-core',s['finish_wall_seconds']>=s['compute_wall_seconds'])
 for f in ('changed_sccs','affected_sccs','changed_declarations','affected_declarations','touched_declarations',
           'total_declarations','total_sccs','closure_hashes','dependency_edges_touched'):
  c.integer(label+':'+f,s.get(f))
 c.eq(label+':N',s['total_declarations'],total)
 for f in ('affected_keys','recomputed_sccs'):
  c.need(label+':unique:'+f,type(s.get(f)) is list and len(s[f])==len(set(s[f])))
 c.need(label+':scc-bound',0<s['total_sccs']<=total)
 if retained:
  c.eq(label+':mode',s.get('mode'),'retained');c.eq(label+':reason',s.get('reason'),None)
  c.eq(label+':cone',sorted(s['affected_keys']),sorted(cone))
  for f in ('affected_declarations','touched_declarations'):c.eq(label+':'+f,s[f],len(cone))
  c.eq(label+':recomputed-count',s['affected_sccs'],len(s['recomputed_sccs']))
  c.eq(label+':hash-count',s['closure_hashes'],len(s['recomputed_sccs']))
  c.need(label+':bounded-sccs',len(s['recomputed_sccs'])<=len(cone))
  c.eq(label+':single-own-change',s['changed_declarations'],1)
 else:
  c.eq(label+':mode',s.get('mode'),'full');c.eq(label+':reason',s.get('reason'),'forced_full_finish')
  c.eq(label+':full-touch',s['touched_declarations'],total)
  c.eq(label+':full-hashes',s['closure_hashes'],s['total_sccs'])
 return {f:s[f] for f in ('affected_declarations','affected_sccs','closure_hashes','touched_declarations','dependency_edges_touched')}


def retained_review(report,c,source,source_hash=None,current=None,baseline=None,diagnostic=False):
 c.eq('retained:schema',report.get('schema'),'mathgraph.retained-index-qualification.v1')
 c.eq('retained:source',report.get('source_sha'),source);c.eq('retained:baseline',report.get('baseline_source'),BASE)
 c.need('retained:complete',report.get('run_completed') is True)
 reps=report.get('repetitions');c.integer('retained:repetitions',reps)
 if not diagnostic:
  c.eq('retained:five',reps,5);c.need('retained:qualified',report.get('correctness_passed') is True and report.get('qualification_status')=='PASS')
  c.need('retained:clean',report.get('source_worktree_tracked_clean') is True)
 c.eq('retained:required-pairs',report.get('required_pairs'),[[p,v] for p in PROFILES for v in VARIANTS])
 controls=[p+':mode-boundary' for p in PROFILES];c.eq('retained:required-controls',report.get('required_controls'),controls)
 gates=report.get('gates',[]);c.need('retained:gates',bool(gates) and all(g.get('passed') is True and g.get('required') is True for g in gates))
 c.need('retained:unique-gates',len(gates)==len({g['name'] for g in gates}))
 expected_gates={'qualified449_exact_source:'+f for f in ('producer_delta.py','engine.py','build_workloads.py','process.py','pins.json','delta-pins.json','expanded-roots.json')}
 expected_gates|={'independent_python_native_exact:'+p+':'+v for p in PROFILES for v in ('baseline',)+VARIANTS}
 expected_gates|={'mode_boundary_control_process:'+p for p in PROFILES}
 expected_gates|={prefix+':'+v for prefix in ('same_identity_cone','same_retained_operation_counts') for v in VARIANTS}
 expected_gates|={'measured_source_stable','measured_tool_bytes_stable'}
 for p in PROFILES:
  for v in VARIANTS:
   for i in range(reps):
    suffix=p+':'+v+':'+str(i)
    expected_gates|={prefix+':'+suffix+':'+arm for prefix in ('worker_completed','full_identity_exact') for arm in ARMS}
    expected_gates|={'exact_pair_delta_and_export:'+suffix,'partition_and_kernel_verdict_parity:'+suffix}
 c.eq('retained:complete-required-gate-set',{g['name'] for g in gates},expected_gates)
 for name in controls:
  r=report['controls'][name];c.need(name+':pass',r.get('passed') is True and r.get('no_new_accepted_record') is True)
  for f,v in {'signed_mode_flip_refusal':'transition environment/version/base mismatch',
              'failed_attempt_poison_refusal':'one baseline-anchored transaction per session',
              'cross_mode_restart_refusal':'source-owner genesis provenance mismatch'}.items():c.eq(name+':'+f,r.get(f),v)
 if source_hash:
  c.eq('retained:harness',report['harness_sha256'],source_hash('experiments/incremental/qualify_retained_index.py'))
  for path,digest in report['measured_source_sha256'].items():c.eq('retained:source:'+path,digest,source_hash(path))
  for filename,digest in report['baseline_package'].items():c.eq('retained:baseline-source:'+filename,digest,source_hash('experiments/incremental/'+filename,BASE))
 if current:
  for field,tool in {'producer':'delta-producer','checker':'check-selected','indexer':'export-index','index_session':'index-session','full_checker':'sokonanoda'}.items():
   c.eq('retained:tool:'+field,report['tools'][field]['sha256'],current[tool])
  for tool in ('index-session','export-index','check-selected','sokonanoda'):
   c.eq('retained:old-tool:'+tool,report['tools']['qualified449_'+tool]['sha256'],baseline[tool])
 expected={(p,v,i) for p in PROFILES for v in VARIANTS for i in range(reps)}
 samples=report.get('samples',[]);observed=[(s.get('profile'),s.get('variant'),s.get('repetition')) for s in samples]
 c.need('retained:complete-unique-samples',len(observed)==len(expected)==len(set(observed)) and set(observed)==expected)
 recomputed={};memory_values={}
 for s in samples:
  p,v,i=s['profile'],s['variant'],s['repetition'];name=f'{p}:{v}:{i}';total=COUNT[p];selected=KERNEL[p,v]
  c.need(name+':passed',s.get('passed') is True)
  cone=s['cone_keys'];c.need(name+':unique-cone',len(cone)==len(set(cone)))
  c.eq(name+':cone-size',s.get('cone_count'),3 if v=='early-definition' else 1)
  c.eq(name+':cone-count',len(cone),s['cone_count'])
  c.eq(name+':arms',sorted(s['arms']),sorted(ARMS));c.eq(name+':standalone',sorted(s['standalone']),['full','retained'])
  c.eq(name+':order',s.get('arm_order'),list(ARMS) if i%2==0 else list(reversed(ARMS)))
  arm_parity=[]
  for arm,r in s['arms'].items():
   label=name+':'+arm;c.eq(label+':status',r.get('result_status'),'VERIFIED')
   for f in ('apply_wall_seconds','constructor_wall_seconds','start_wall_seconds','constructor_through_apply_wall_seconds',
             'constructor_through_apply_cpu_seconds','close_wall_seconds','close_cpu_seconds',
             'one_update_api_component_sum_wall_seconds','one_update_api_component_sum_cpu_seconds',
             'observed_constructor_through_close_wall_seconds'):c.num(label+':'+f,r.get(f))
   c.near(label+':api-wall-sum',r['one_update_api_component_sum_wall_seconds'],r['constructor_through_apply_wall_seconds']+r['close_wall_seconds'])
   c.near(label+':api-cpu-sum',r['one_update_api_component_sum_cpu_seconds'],r['constructor_through_apply_cpu_seconds']+r['close_cpu_seconds'])
   c.need(label+':lifecycle-contains-api',r['observed_constructor_through_close_wall_seconds']>=r['one_update_api_component_sum_wall_seconds'])
   c.need(label+':api-contains-setup-apply',r['constructor_through_apply_wall_seconds']+1e-6>=r['constructor_wall_seconds']+r['start_wall_seconds']+r['apply_wall_seconds'])
   c.need(label+':close-scope','SIGTERM does not promise clean Rust EOF/destructor execution' in r.get('close_scope',''))
   c.need(label+':sum-scope','component sum excludes' in r.get('lifecycle_scope',''))
   direct=r['direct_rust'];c.need(label+':raw-success',type(direct.get('returncode')) is int and direct['returncode']==0 and direct.get('timed_out') is False)
   for f in ('wall_seconds','completed_child_cpu_seconds'):c.num(label+':direct:'+f,direct[f])
   c.eq(label+':raw-binary',Path(direct['command'][0]).name,'sokonanoda')
   for f in ('stdout_sha256','stderr_sha256'):c.hex(label+':direct:'+f,direct[f])
   snap=r['sealed_snapshot'];c.eq(label+':seals',snap['seals'],15);c.eq(label+':required-seals',snap['required_seals'],15)
   c.hex(label+':snapshot',snap['sha256']);c.need(label+':live-memfd',re.fullmatch('/proc/[0-9]+/fd/[0-9]+',snap['path']) is not None)
   c.eq(label+':full-index',r['index_sha256'],report['references'][p][v]['index_sha256'])
   partition=r['partition'];checked=partition['checked_indices'];reused=partition['reused_indices']
   c.need(label+':typed-partition',all(type(x) is int and 0<=x<total for x in checked+reused))
   c.need(label+':complete-disjoint',len(set(checked))==len(checked)==selected and len(set(reused))==len(reused)==total-selected and not set(checked)&set(reused) and set(checked+reused)==set(range(total)))
   c.eq(label+':actual-check-count',partition['actual_kernel_checked'],selected);c.eq(label+':actual-total',partition['actual_kernel_total'],total)
   c.eq(label+':witness-count',partition['identity_witnesses_checked'],total);c.eq(label+':reuse-count',partition['independently_replayed_reused'],total-selected)
   c.eq(label+':counts',r['counts'],dict(total=total,scheduled=selected,rechecked=selected,reused=total-selected,invalidated=selected))
   receipt=r['receipt_audit'];c.need(label+':HMAC-audit',all(receipt.get(f) is True for f in ('issuer_hmac_valid','all_content_addresses_valid','contains_complete_index')))
   for f in ('receipt_bytes','delta_bytes'):c.integer(label+':'+f,receipt[f])
   arm_parity.append((snap['sha256'],snap['bytes'],r['index_sha256'],checked,reused))
   provenance=r['setup']['delta_provenance'];c.eq(label+':adapter',provenance['adapter_sha256'],source_hash('experiments/incremental/producer_delta.py',BASE if arm=='qualified449' else source) if source_hash else provenance['adapter_sha256'])
   if arm!='qualified449':
    c.eq(label+':authenticated-finish-mode',provenance.get('identity_finish'),arm)
    stats_review(c,label+':update',r['typed_update']['finish_stats'],cone,total,arm=='retained')
   for f,x in r['timings'].items():c.num(label+':timing:'+f,x)
   c.need(label+':apply-contains-reported',r['apply_wall_seconds']+1e-6>=r['timings']['end_to_end_seconds'])
   for stage,mem in r['memory'].items():
    c.need(label+':memory-scope:'+stage,'cumulative since process startup' in mem.get('scope',''))
    for process,values in mem['processes'].items():
     for metric,value in values.items():c.integer(label+':memory:'+process+':'+metric,value)
     if 'VmRSS' in values and 'VmHWM' in values:c.need(label+':HWM>=RSS',values['VmHWM']>=values['VmRSS'])
     for metric in ('VmRSS','VmHWM'):
      if metric in values:memory_values.setdefault((p,v,arm,process,metric),[]).append(values[metric])
  c.need(name+':identical-composite-and-partition',all(x==arm_parity[0] for x in arm_parity))
  c.need(name+':identical-producer-delta',len({r['delta_sha256'] for r in s['arms'].values()})==1)
  for mode,r in s['standalone'].items():
   label=name+':standalone:'+mode;stats_review(c,label,r['finish_stats'],cone,total,mode=='retained')
   c.eq(label+':index',r['update_index_sha256'],report['references'][p][v]['index_sha256'])
   c.eq(label+':baseline',r['ready_index_sha256'],report['references'][p]['baseline']['index_sha256'])
   c.eq(label+':ready-mode',r['ready_identity_mode'],mode)
   for f in ('setup_wall_seconds','baseline_prepare_wall_seconds','roundtrip_wall_seconds','roundtrip_minus_compute_wall_seconds','roundtrip_minus_finish_wall_seconds'):c.num(label+':'+f,r[f])
   c.near(label+':roundtrip-minus-core',r['roundtrip_minus_compute_wall_seconds'],r['roundtrip_wall_seconds']-r['finish_stats']['compute_wall_seconds'])
   c.near(label+':roundtrip-minus-finish',r['roundtrip_minus_finish_wall_seconds'],r['roundtrip_wall_seconds']-r['finish_stats']['finish_wall_seconds'])
 for p in PROFILES:
  recomputed[p]={}
  for v in VARIANTS:
   rows=[s for s in samples if s['profile']==p and s['variant']==v];record=report['economics'][p][v];computed={}
   comparisons={}
   for arm in ('full','qualified449'):
    for phase in ('apply_wall_seconds','constructor_through_apply_wall_seconds','constructor_through_apply_cpu_seconds','close_wall_seconds','one_update_api_component_sum_wall_seconds','one_update_api_component_sum_cpu_seconds'):
     comparisons['retained_vs_'+arm+':'+phase]=([s['arms']['retained'][phase] for s in rows],[s['arms'][arm][phase] for s in rows])
   comparisons['retained_vs_direct_fresh_rust']=([s['arms']['retained']['apply_wall_seconds'] for s in rows],[s['arms']['retained']['direct_rust']['wall_seconds'] for s in rows])
   for f in ('compute_wall_seconds','compute_cpu_seconds','finish_wall_seconds','finish_cpu_seconds'):
    comparisons['retained_vs_full:'+f]=([s['standalone']['retained']['finish_stats'][f] for s in rows],[s['standalone']['full']['finish_stats'][f] for s in rows])
   comparisons['retained_vs_full:index_roundtrip']=([s['standalone']['retained']['roundtrip_wall_seconds'] for s in rows],[s['standalone']['full']['roundtrip_wall_seconds'] for s in rows])
   c.eq(p+':'+v+':economic-key-set',set(record),set(comparisons)|{'phase_medians'})
   for label,(num,den) in comparisons.items():computed[label]=economic_check(c,p+':'+v+':'+label,record[label],num,den,incomplete=diagnostic)
   for arm in ARMS:
    timing=[s['arms'][arm]['timings'] for s in rows];fields=set.intersection(*(set(t) for t in timing));phases={f:statistics.median(t[f] for t in timing) for f in fields}
    for f in ('constructor_wall_seconds','start_wall_seconds','close_wall_seconds','close_cpu_seconds','constructor_through_apply_wall_seconds','constructor_through_apply_cpu_seconds','one_update_api_component_sum_wall_seconds','one_update_api_component_sum_cpu_seconds'):
     phases[f]=statistics.median(s['arms'][arm][f] for s in rows)
    c.eq(p+':'+v+':phase-medians:'+arm,record['phase_medians'][arm],phases)
   computed['phase_medians']=record['phase_medians'];recomputed[p][v]=computed
 for v in VARIANTS:
  scaling=report['same_cone_scaling'][v];counts={};medians={};finish={};cones=[]
  for p in PROFILES:
   rows=[s for s in samples if s['profile']==p and s['variant']==v];cones.extend(tuple(s['cone_keys']) for s in rows)
   counts[p]=[{f:s['standalone']['retained']['finish_stats'][f] for f in ('affected_declarations','affected_sccs','closure_hashes','touched_declarations','dependency_edges_touched')} for s in rows]
   medians[p]=statistics.median(s['standalone']['retained']['finish_stats']['compute_wall_seconds'] for s in rows)
   finish[p]=statistics.median(s['standalone']['retained']['finish_stats']['finish_wall_seconds'] for s in rows)
  c.need(v+':same-exact-cone',len(set(cones))==1);c.need(v+':same-operations',len({canonical(x) for values in counts.values() for x in values})==1)
  c.eq(v+':operation-counts',scaling['operation_counts'],counts);c.eq(v+':compute-medians',scaling['compute_wall_medians'],medians)
  c.eq(v+':finish-medians',scaling['finish_wall_medians'],finish)
  c.near(v+':scaling-compute-ratio',scaling['expanded_over_original_compute_wall_ratio'],medians['expanded']/medians['original'])
  c.near(v+':scaling-finish-ratio',scaling['expanded_over_original_finish_wall_ratio'],finish['expanded']/finish['original'])
 return dict(economics=recomputed,same_cone_scaling=report['same_cone_scaling'],memory_KiB={'|'.join(k):[min(v),max(v)] for k,v in memory_values.items()},
  limits=['Compact report projects live full-index/partition/HMAC audits; omitted raw witnesses/private keys were not read.',
          'Core compute excludes full index output; whole finish includes reached cleanup; roundtrip additionally includes complete JSON/IPC/decoding.',
          'SIGTERM adapter close is timed but does not establish graceful Rust destructor execution.',
          'One-update API lifecycle component sum excludes later oracle work; observed whole interval includes that work.',
          'Only one baseline-anchored update per session; no measured continuing-revision amortization.'])


def storage_review(r,c,source,source_hash=None,retained_raw=None,delta_raw=None,diagnostic=False):
 c.eq('storage:schema',r.get('schema'),'mathgraph.sparse-storage-benchmark.v1');c.eq('storage:scope',r.get('scope'),'storage_only_not_acceptance')
 c.need('storage:complete',r.get('run_completed') is True and r.get('correctness_passed') is True and r.get('qualification_status')=='PASS')
 if not diagnostic:
  c.eq('storage:source',r['source_sha'],source);c.need('storage:strict-parity',r['parity_gate']['incomplete_smoke_allowed'] is False and r['parity_gate']['qualification_status']=='PASS')
 if source_hash:
  for field,path in [('helper_sha256','benchmark_sparse_receipts.py'),('engine_sha256','engine.py')]:c.eq('storage:source:'+field,r[field],source_hash('experiments/incremental/'+path))
 if retained_raw:c.eq('storage:parity-binding',r['parity_gate']['sha256'],sha(retained_raw))
 cases={p+':'+v for p in PROFILES for v in VARIANTS};c.eq('storage:control-cases',set(r['controls']),cases)
 c.eq('storage:input-count',len(r['inputs']),4);c.eq('storage:input-cases',{x['profile']+':'+x['variant'] for x in r['inputs']},cases)
 for x in r['inputs']:
  if not diagnostic:c.eq('storage:kernel-source',x['kernel_source'],source)
  if delta_raw:c.eq('storage:kernel-summary',x['summary_sha256'],sha(delta_raw[x['profile']]))
  for f in ('base_sha256','accepted_sha256'):c.hex('storage:input:'+f,x[f])
 for name,controls in r['controls'].items():
  c.eq(name+':control-count',len(controls),11);c.eq(name+':control-set',{x['name'] for x in controls},set(STORAGE_CAUSES))
  for row in controls:
   c.need(name+':control:'+row['name'],row.get('passed') is True)
   reason=STORAGE_CAUSES[row['name']]
   if reason:c.need(name+':intended-cause:'+row['name'],reason in row.get('observed','') and row.get('expected')==reason)
 samples=r['samples'];c.eq('storage:repetitions',r['repetitions'],5)
 ids=[(s['profile'],s['variant'],s['repetition']) for s in samples]
 c.need('storage:complete-pairs',len(ids)==len(set(ids))==20 and set(ids)=={(p,v,i) for p in PROFILES for v in VARIANTS for i in range(5)})
 findings={}
 for sample in samples:
  c.eq('storage:alternating-order',sample['order'],['full','sparse'] if sample['repetition']%2==0 else ['sparse','full'])
  for arm in ('full','sparse'):
   row=sample[arm];c.need('storage:fair-original-mint',row.get('includes_original_acceptance_mint') is True)
   c.integer('storage:size',row['bytes']);c.hex('storage:contentid',row['record_id'])
   for phase in ('write','read'):
    for f in ('wall_seconds','cpu_seconds'):c.num('storage:phase:'+f,row[phase][f])
    for f,v in row[phase]['postphase_memory'].items():c.integer('storage:memory:'+f,v)
 for name in cases:
  rows=[s for s in samples if s['profile']+':'+s['variant']==name];findings[name]={}
  for phase in ('write','read'):
   actual=r['economics'][name][phase];num=[s['sparse'][phase]['wall_seconds'] for s in rows];den=[s['full'][phase]['wall_seconds'] for s in rows]
   findings[name][phase]=economic_check(c,name+':'+phase,actual,num,den,storage=True)
   for arm in ('full','sparse'):c.near(name+':'+phase+':'+arm+'-cpu',actual[arm+'_median_cpu_seconds'],statistics.median(s[arm][phase]['cpu_seconds'] for s in rows))
  findings[name]['bytes']={arm:rows[0][arm]['bytes'] for arm in ('full','sparse')}
 return findings


def pinned_helper(repo,name,override=None):
 sibling=Path(__file__).resolve().with_name(name)
 path=Path(override) if override else sibling if sibling.is_file() else repo/'experiments/incremental/results/producer-delta-qualified'/name
 if sha(path.read_bytes())!=HELPERS[name]:raise ValueError('independent helper bytes drift:'+name)
 spec=importlib.util.spec_from_file_location(name.replace('-','_'),path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def archive_review(args):
 legacy=pinned_helper(args.repo,'review-compact-ci.py',args.legacy_helper);delta=pinned_helper(args.repo,'review-evidence.py',args.delta_helper)
 c=C();findings={};rawzip=args.zip.read_bytes();meta=strict(args.metadata.read_bytes())
 if 'artifact' in meta:meta=meta['artifact']
 if 'artifacts' in meta:
  candidates=[x for x in meta['artifacts'] if x.get('name')=='incremental-retained-index-summaries-'+args.source]
  c.eq('archive:one-provider-compact',len(candidates),1);meta=candidates[0]
 c.eq('archive:provider-name',meta['name'],'incremental-retained-index-summaries-'+args.source)
 c.eq('archive:provider-source',meta['workflow_run']['head_sha'],args.source)
 c.eq('archive:provider-run',meta['workflow_run']['id'],args.run)
 if args.run_json:
  run=strict(args.run_json.read_bytes())
  for field,value in [('id',args.run),('head_sha',args.source),('status','completed'),('conclusion','success')]:c.eq('execution:run:'+field,run.get(field),value)
 if args.jobs_json:
  jobs=strict(args.jobs_json.read_bytes());jobs=jobs.get('jobs',[jobs]) if type(jobs) is dict else jobs
  selected=[job for job in jobs if job.get('id')==args.job];c.eq('execution:one-job',len(selected),1);job=selected[0]
  for field,value in [('status','completed'),('conclusion','success')]:c.eq('execution:job:'+field,job.get(field),value)
  if 'run_id' in job:c.eq('execution:job:run',job['run_id'],args.run)
  workflow=subprocess.check_output(['git','show',args.source+':.github/workflows/incremental-retained-index.yml'],cwd=args.repo,text=True)
  expected_steps=re.findall(r'^      - name: (.+)$',workflow,re.MULTILINE);steps={row['name']:row for row in job['steps']}
  for name in expected_steps:c.need('execution:required-step:'+name,name in steps and steps[name].get('conclusion')=='success' and steps[name].get('status')=='completed')
 c.eq('archive:provider-size',meta['size_in_bytes'],len(rawzip));c.eq('archive:provider-digest',meta['digest'],'sha256:'+sha(rawzip))
 findings['archive']=dict(bytes=len(rawzip),sha256=sha(rawzip),artifact_id=meta.get('id'),workflow_run=meta['workflow_run'].get('id'))
 with zipfile.ZipFile(args.zip) as z, tempfile.TemporaryDirectory(prefix='retained-independent-review-') as td:
  names=[]
  for info in z.infolist():
   p=PurePosixPath(info.filename);c.need('archive:safe-path',not p.is_absolute() and '..' not in p.parts and '\\' not in info.filename)
   c.need('archive:no-secret-or-symlink',p.suffix!='.key' and not stat.S_ISLNK(info.external_attr>>16) and not info.flag_bits&1)
   if not info.is_dir():names.append(info.filename)
  c.need('archive:unique',len(names)==len(set(names)));c.need('archive:CRC',z.testzip() is None)
  a=legacy.ArchiveReview(args);a.archive=z;a.names=names
  def member(suffix):
   exact=[name for name in names if name in (suffix,'artifacts/'+suffix)]
   found=exact or [name for name in names if name.endswith('/'+suffix)]
   c.need('archive:unique-member:'+suffix,len(found)==1)
   return z.read(found[0])
  a.member=member
  obs=a.load('observations','ci-observations.json');a.check_sources();c.count+=a.checks.count
  captured=a.mapping(a.member('source-SHA256SUMS'))
  tracked=subprocess.check_output(['git','ls-tree','-r','--name-only',args.source,'--','src','Cargo.toml','Cargo.lock','experiments/incremental','.github/workflows/incremental-retained-index.yml'],cwd=args.repo,text=True).splitlines()
  c.eq('source:complete-tracked-universe',set(captured),set(tracked))
  findings.update(a.findings);source_cache={}
  def source_hash(path,source=None):
   key=(source or args.source,path)
   if key not in source_cache:source_cache[key]=sha(subprocess.check_output(['git','show',key[0]+':'+path],cwd=args.repo))
   return source_cache[key]
  old=a.mapping(a.member('qualified449/SHA256SUMS'));old={Path(p).name:h for p,h in old.items()}
  c.eq('old:source',a.member('qualified449/source-ref.txt').decode().strip(),BASE)
  c.eq('old:binary-universe',set(old),{'index-session','export-index','check-selected','sokonanoda'})
  verified=a.member('qualified449-binaries-verified.log').decode().splitlines();sums=a.mapping(a.member('qualified449/SHA256SUMS'))
  c.eq('old:binary-stability-log',sorted(verified),sorted(p+': OK' for p in sums))
  findings['current_binary_sha256']=a.binaries;findings['qualified449_binary_sha256']=old
  findings['independent_review_dependencies']=dict(HELPERS)
  findings['execution_metadata_checked']=dict(run=bool(args.run_json),job=bool(args.jobs_json))
  delta_raw={};findings['delta_reviews']={};findings['delta_phases']={}
  for profile,directory in [('original','delta-qualification'),('expanded','delta-expanded-qualification')]:
   raw=a.member(directory+'/summary.json');delta_raw[profile]=raw;p=Path(td)/directory/'summary.json';p.parent.mkdir();p.write_bytes(raw)
   result=delta.Reviewer(p,args.source,args.repo,False).audit();c.need(profile+':independent-delta-review',result['passed'] is True)
   result['current_scope_note']='The frozen reviewer protocol/arithmetic checks apply here. Its historical generic SCC residual sentence is superseded by the retained-core section: graph-stable closure computation is retained; complete-index JSON, baseline authentication/hash, materialization/parsing and receipts still scale with total input, and edge-changing updates fall back to the full path.'
   findings['delta_reviews'][profile]=result
   phase=legacy.strict_json(a.member(directory+'/compact-phases.json'));sub=legacy.Checks()
   findings['delta_phases'][profile]=legacy.phase_review(phase,strict(raw),args.source,raw,sub);c.count+=sub.count
  retained_raw=a.member('retained-qualification/summary.json');retained=strict(retained_raw)
  c.eq('observed:retained-sha',obs['reports']['retained-index']['summary_sha256'],sha(retained_raw))
  c.need('observed:retained-pass',obs['reports']['retained-index']['report_passed'] is True)
  findings['retained']=retained_review(retained,c,args.source,source_hash,a.binaries,old)
  c.eq('observed:retained-economics',obs['reports']['retained-index']['economics'],retained['economics'])
  sparse_raw=a.member('sparse-receipt-benchmark/summary.json');sparse=strict(sparse_raw)
  c.eq('observed:storage-sha',obs['reports']['sparse-storage']['summary_sha256'],sha(sparse_raw));c.need('observed:storage-pass',obs['reports']['sparse-storage']['report_passed'] is True)
  findings['storage']=storage_review(sparse,c,args.source,source_hash,retained_raw,delta_raw)
  fixture_raw=a.member('retained-independent-fixtures/summary.json');f=strict(fixture_raw)
  c.need('fixtures:complete',f.get('passed') is True and f.get('complete') is True and f.get('status')=='PASS_INDEPENDENT_RETAINED_SCC_FIXTURES')
  c.eq('fixtures:count',f['fixture_count'],26);c.eq('fixtures:cases',len(f['cases']),26)
  c.need('fixtures:unique',len({x['name'] for x in f['cases']})==26)
  c.eq('fixtures:source',f['oracle_source'],BASE);c.eq('fixtures:oracle-bytes',f['oracle_source_sha256'],source_hash('experiments/incremental/engine.py',BASE))
  c.eq('fixtures:helper',f['helper_sha256'],source_hash('experiments/incremental/replay_retained_index.py'))
  c.eq('fixtures:binary',f['tools']['index-session']['sha256'],a.binaries['index-session'])
  for case in f['cases']:
   c.need('fixture:status:'+case['name'],case['status'] in ('FULL_INDEX_PARITY','REFUSED_NO_INDEX_SESSION_TERMINATED','REFUSED_UNTRUSTED_CACHE_INPUT'))
   c.need('fixture:actual-commands',bool(case['commands']))
   for cmd in case['commands']:
    c.eq('fixture:actual-verdict',cmd['returncode'],cmd['expected'])
    for field in ('stdout_sha256','stderr_sha256'):c.hex('fixture:raw-hash',cmd[field])
  c.eq('observed:fixtures-sha',obs['reports']['retained-independent-fixtures']['summary_sha256'],sha(fixture_raw))
  findings['fixtures']=dict(count=26,status=f['status']);findings['isolated_microbenchmarks']={}
  for p in PROFILES:
   for v in VARIANTS:
    name=p+':'+v;log=a.member('retained-microbenchmark-'+p+'-'+v+'.log');records=[]
    for line in log.decode().splitlines():
     if 'RETAINED_BENCH ' in line:
      text=line.split('RETAINED_BENCH ',1)[1];record,end=json.JSONDecoder().raw_decode(text)
      c.need('micro:output-suffix',text[end:].strip() in ('','ok'));records.append(record)
    c.eq('micro:one-record',len(records),1);r=records[0]
    c.eq('micro:schema',r['schema'],'mathgraph.retained-finish-microbenchmark.v1');c.eq('micro:repetitions',r['repetitions'],7)
    c.eq('micro:scope',r.get('scope'),'same parsed mutation; baseline graph clones outside timers; complete output parity')
    rows=r['samples'];c.need('micro:complete',len(rows)==7 and {x['repetition'] for x in rows}==set(range(7)) and all(x['parity'] is True for x in rows))
    c.eq('micro:log-binding',obs['isolated_finish_microbenchmarks'][name]['log_sha256'],sha(log));c.eq('micro:projection',obs['isolated_finish_microbenchmarks'][name]['report'],r)
    results={}
    for x in rows:
     cone=next(s['cone_keys'] for s in retained['samples'] if s['profile']==p and s['variant']==v)
     stats_review(c,'micro:'+name,x['retained'],cone,COUNT[p],True)
     for field in ('compute_wall_seconds','compute_cpu_seconds','finish_wall_seconds','finish_cpu_seconds'):c.num('micro:full:'+field,x['full_'+field])
     c.need('micro:full-whole-core',x['full_finish_wall_seconds']>=x['full_compute_wall_seconds'])
    for field in ('compute_wall_seconds','compute_cpu_seconds','finish_wall_seconds','finish_cpu_seconds'):
     results[field]=paired([x['retained'][field] for x in rows],[x['full_'+field] for x in rows])
    findings['isolated_microbenchmarks'][name]=dict(comparisons=results,prepare_wall_seconds=r['prepare_wall_seconds'],prepare_cpu_seconds=r['prepare_cpu_seconds'],scope=r['scope'])
  if args.falsifiers:findings['falsifiers']=falsifiers(retained,sparse,args.source)
 return dict(passed=True,status='PASS_WITH_STATED_LIMITS',check_count=c.count,findings=findings,
  limits=['No runtime/controller code was imported; only two hash-pinned independent review helpers were reused.',
          'No kernels were rerun. Live HMAC audit flags are checked but old private signatures were not reauthenticated.',
          'Compact archives omit full samples/index witnesses/caches; report projections and integrity are checked, not invented raw reads.',
          'Fixed arm order alternates across repetitions; direct raw command follows each apply on identical live sealed bytes; OS cache warm.',
          'Local and CI hosts/profiles are separate; core compute, whole finish, IPC and one-update lifecycle have distinct scopes.',
          'Sparse storage capsules remain subordinate; their storage savings imply neither new acceptance nor end-to-end speedup.'])


def falsifiers(retained,sparse,source):
 rows=[]
 def fail(name,kind,mutate):
  value=copy.deepcopy(retained if kind=='retained' else sparse);mutate(value);c=C()
  try:
   if kind=='retained':retained_review(value,c,source,diagnostic=value['repetitions']<5)
   else:storage_review(value,c,source,diagnostic=True)
  except (ValueError,KeyError,TypeError,IndexError) as error:rows.append(dict(name=name,passed=True,refusal=str(error)))
  else:rows.append(dict(name=name,passed=False,refusal='unexpected promotion'))
 fail('partial-run','retained',lambda r:r.update(run_completed=False))
 fail('missing-sample','retained',lambda r:r['samples'].pop())
 fail('false-gate','retained',lambda r:r['gates'][0].update(passed=False))
 fail('missing-required-gate','retained',lambda r:r['gates'].pop())
 fail('wrong-source','retained',lambda r:r.update(source_sha='0'*40))
 fail('changed-direct-timing','retained',lambda r:r['samples'][0]['arms']['retained']['direct_rust'].update(wall_seconds=99))
 fail('forged-work-counter','retained',lambda r:r['samples'][0]['standalone']['retained']['finish_stats'].update(touched_declarations=99))
 fail('false-HMAC-audit','retained',lambda r:r['samples'][0]['arms']['retained']['receipt_audit'].update(issuer_hmac_valid=False))
 fail('core-exceeds-whole','retained',lambda r:r['samples'][0]['standalone']['retained']['finish_stats'].update(compute_wall_seconds=99))
 fail('unpaid-close','retained',lambda r:r['samples'][0]['arms']['retained'].update(one_update_api_component_sum_wall_seconds=0))
 fail('storage-wrong-cause','storage',lambda r:r['controls']['original:early-definition'][0].update(observed='timeout'))
 fail('storage-free-original-signature','storage',lambda r:r['samples'][0]['sparse'].update(includes_original_acceptance_mint=False))
 fail('storage-altered-duration','storage',lambda r:r['samples'][0]['sparse']['read'].update(wall_seconds=99))
 fail('storage-missing-pair','storage',lambda r:r['samples'].pop())
 if not all(x['passed'] for x in rows):raise ValueError('independent reviewer falsifier unexpectedly promoted malformed evidence')
 return dict(status='PASS_FALSIFIERS',cases=rows)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path.cwd())
 p.add_argument('--legacy-helper',type=Path);p.add_argument('--delta-helper',type=Path)
 p.add_argument('--run',type=int,default=38961520032);p.add_argument('--job',type=int,default=117177490277)
 p.add_argument('--run-json',type=Path);p.add_argument('--jobs-json',type=Path)
 p.add_argument('--source',default='ef434eb2477fb64d7fd90fdf23f55bd0b35a0243');p.add_argument('--zip',type=Path);p.add_argument('--metadata',type=Path)
 p.add_argument('--falsifiers',action='store_true');p.add_argument('--diagnostic-retained',type=Path);p.add_argument('--diagnostic-storage',type=Path)
 p.add_argument('--out',type=Path,required=True);args=p.parse_args()
 try:
  if args.diagnostic_retained:
   r=strict(args.diagnostic_retained.read_bytes());s=strict(args.diagnostic_storage.read_bytes());c=C()
   a=retained_review(r,c,r['source_sha'],diagnostic=True);b=storage_review(s,c,s['source_sha'],diagnostic=True)
   result=dict(passed=False,status='DIAGNOSTIC_ONLY_NOT_QUALIFICATION',structural_checks_passed=True,check_count=c.count,retained=a,storage=b)
   if args.falsifiers:result['falsifiers']=falsifiers(r,s,r['source_sha'])
  else:
   if not args.zip or not args.metadata:p.error('actual downloaded ZIP and provider metadata are required')
   result=archive_review(args)
 except Exception as error:result=dict(passed=False,status='FAIL_CLOSED',error=repr(error))
 result.update(reviewer_sha256=sha(Path(__file__).read_bytes()),expected_source=args.source)
 args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 print(json.dumps({k:result[k] for k in ('status','passed','check_count','error') if k in result}))
 return 0 if result.get('passed') or result.get('structural_checks_passed') else 1


if __name__=='__main__':raise SystemExit(main())
