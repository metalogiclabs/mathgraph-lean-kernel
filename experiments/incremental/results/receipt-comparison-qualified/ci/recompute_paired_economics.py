#!/usr/bin/env python3
"""Independent arithmetic from shared compact evidence; imports no project code."""
import hashlib,json,math,random,statistics
from pathlib import Path
root=Path('/workspace/kernel-audit/retained-admission-continuation/receipt-comparison-review/actual-ci/artifact')
path=root/'receipt-comparison/summary.json';report=json.loads(path.read_bytes())
assert report['source_sha']=='5dfe38b01ca7b1c67f70be4ffb2479978049239e' and report['completed'] and report['correctness_passed']
checks=[];cases=[]
def paired(candidate,control,published,label):
 assert len(candidate)==len(control)==5
 assert all(type(x) in (float,int) and math.isfinite(x) and x>0 for x in candidate+control)
 rng=random.Random(published['bootstrap_seed']);ratios=[]
 for _ in range(published['bootstrap_repetitions']):
  positions=[rng.randrange(5) for _ in range(5)]
  ratios.append(statistics.median(candidate[i] for i in positions)/statistics.median(control[i] for i in positions))
 ratios.sort();interval=[ratios[int(q*(len(ratios)-1))] for q in (.025,.975)]
 ratio=statistics.median(candidate)/statistics.median(control);wins=sum(a<b for a,b in zip(candidate,control))
 passed=ratio<1 and wins>2.5 and interval[1]<1
 observed={'apply_median_wall_seconds':statistics.median(candidate),'direct_median_wall_seconds':statistics.median(control),'median_ratio':ratio,'paired_wins':wins,'paired_count':5,'bootstrap_ratio_interval_95':interval,'passed':passed,'status':'SPEEDUP' if passed else 'NO_SPEEDUP'}
 for key,value in observed.items():assert published[key]==value,(label,key,published[key],value)
 checks.append({'case':label,'all_published_arithmetic_exact':True,'status':observed['status']})
 return observed
for profile in ('original','expanded'):
 for variant in ('early-definition','unrelated-definition'):
  c=report['profiles'][profile][variant];pairs=sorted(c['pairs'],key=lambda p:p['repetition'])
  assert len(pairs)==5 and [p['repetition'] for p in pairs]==list(range(5))
  control=[p['arms']['canonical_json'] for p in pairs];candidate=[p['arms']['shared_json'] for p in pairs]
  for a,b in zip(candidate,control):
   for key in ('checked','reused','decisions_sha256','export_sha256','policy_tool_sha256'):assert a[key]==b[key],(profile,variant,key)
  results={}
  for metric,field in [('warm_economics','wall_seconds'),('selected_kernel_economics','kernel_seconds'),('persistence_economics','persistence_seconds'),('setup_plus_one_apply_component_sum_economics','setup_plus_apply_component_sum_seconds')]:
   results[metric]=paired([a[field] for a in candidate],[a[field] for a in control],c[metric],profile+'/'+variant+'/'+metric)
  results['warm_cpu_economics']=paired([a['phases']['timings']['end_to_end_cpu_seconds'] for a in candidate],[a['phases']['timings']['end_to_end_cpu_seconds'] for a in control],c['warm_cpu_economics'],profile+'/'+variant+'/CPU')
  for mode,arms in [('canonical_json',control),('shared_json',candidate)]:
   paired([a['wall_seconds'] for a in arms],[a['direct_rust']['wall_seconds'] for a in arms],c['direct_full_rust_economics'][mode],profile+'/'+variant+'/direct/'+mode)
  phases={};memory={}
  for mode,arms in [('canonical_json',control),('shared_json',candidate)]:
   fields=set.intersection(*(set(a['phases']['timings']) for a in arms))
   phases[mode]={f:statistics.median(a['phases']['timings'][f] for a in arms) for f in sorted(fields) if f.endswith('_seconds')}
   phases[mode].update(setup_wall_seconds=statistics.median(a['setup_seconds'] for a in arms),setup_start_cpu_seconds=statistics.median(a['setup_report']['cpu_seconds'] for a in arms))
   memory[mode]={}
   for process in ('adapter','producer','index','retained_kernel'):
    values=[a['phases']['memory'].get('persistence',{}).get('processes',{}).get(process) for a in arms]
    memory[mode][process]={}
    for field in ('VmRSS','VmHWM'):
     valid=[v[field] for v in values if type(v) is dict and field in v]
     memory[mode][process][field]={'observations':len(valid),'median_kib':statistics.median(valid) if valid else None,'range_kib':[min(valid),max(valid)] if valid else None}
  cases.append({'profile':profile,'variant':variant,'checked':control[0]['checked'],'reused':control[0]['reused'],'independently_recomputed_economics':results,'median_phase_seconds':phases,'post_persistence_procfs_memory':memory})
output={'schema':'mathgraph.independent-receipt-comparison-economics.v1','source_sha':report['source_sha'],'summary_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'imports_project_code':False,'arithmetic_checks':checks,'all_28_published_comparisons_exact':len(checks)==28,'cases':cases,'memory_limits':['Raw process observations, not aggregate or phase peak memory.','Adapter measurements include the benchmark process and loaded oracle references.','VmHWM is cumulative across earlier setup/oracles/samples in the same process.','Missing/exited process observations remain absent, never zero.'],'lifecycle_limits':['Setup plus one apply is an observed component sum; close and harness oracles excluded.','Setup CPU field covers session.start, not constructor CPU.','No multi-update stream, amortization or break-even extrapolation is supported.'],'qualification_scope':'Independent economics arithmetic only; authority/source/witness replay checked by separate frozen reviewer.'}
out=Path('/workspace/kernel-audit/retained-admission-continuation/ci-39581949051/independent-economics.json');out.write_text(json.dumps(output,indent=2)+'\n')
print('exact published comparisons:',len(checks))
for c in cases:
 print(c['profile'],c['variant'],'wall medians canonical/shared ms',*[round(c['median_phase_seconds'][m]['end_to_end_seconds']*1000,3) for m in ('canonical_json','shared_json')],'persistence ms',*[round(c['median_phase_seconds'][m]['persistence_seconds']*1000,3) for m in ('canonical_json','shared_json')],'checking ms',*[round(c['median_phase_seconds'][m]['checking_seconds']*1000,3) for m in ('canonical_json','shared_json')])
