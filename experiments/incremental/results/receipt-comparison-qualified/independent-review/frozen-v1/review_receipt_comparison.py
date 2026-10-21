#!/usr/bin/env python3
"""Independent compact-artifact review. Standard library only; no runtime imports.

This verifies archived observations/content and recomputes arithmetic. It does
not execute a kernel or authenticate historical HMACs without the issuer key.
"""
import argparse, copy, gzip, hashlib, json, math, random, statistics, subprocess
import sys, zipfile
from pathlib import Path, PurePosixPath

MODES=('canonical_json','shared_json')
VARIANTS=('early-definition','unrelated-definition')
TOTAL={'original':3436,'expanded':11653}
CHECKED={'original':{'early-definition':413,'unrelated-definition':1,'theorem-leaf':1,'baseline':0},
         'expanded':{'early-definition':672,'unrelated-definition':260,'theorem-leaf':260,'baseline':0}}
SCOPE='Same-source retained-kernel receipt issuance: shared JSON comparison versus canonical JSON comparison.'
SCHEMA='mathgraph.retained-receipt-index-comparison.v1'
SPARSE='mathgraph.incremental-lean.sparse-accepted.v1'
CAUSES={'forged-attestation':'issuer authentication failed',
 'authenticated-attestation-version-drift':'wrong authority domain',
 'authenticated-baseline-environment-drift':'transition environment/version/base mismatch',
 'authenticated-base-export-drift':'transition environment/version/base mismatch',
 'authenticated-producer-version-drift':'transition environment/version/base mismatch',
 'unannounced-source-change':'source modifications outside the reported patch',
 'outside-announced-region':'source modifications outside the reported patch',
 'import-environment-drift':'source modifications outside the reported patch',
 'false-announced-name':'expected_changed_names differs from complete local comparison',
 'corrupt-baseline-receipt':'evidence content address mismatch',
 'corrupt-baseline-export':'baseline storage corruption',
 'corrupt-genesis':'delta storage corruption: genesis',
 'corrupt-accepted-delta-receipt':'delta storage corruption: records',
 'corrupt-persisted-delta-bytes':'delta storage corruption: deltas',
 'corrupt-persisted-transition':'delta storage corruption: transitions',
 'corrupt-persisted-representation':'delta storage corruption: representations',
 'foreign-issuer-authority':'evidence issuer authentication failed'}
KERNEL_NEG={'signed-invalid-proof','signed-invalid-axiom',
 'unused-invalid-node-zero-selection-parser','unused-invalid-node-dag-only-zero-selection-parser'}

def strict(pairs):
 out={}
 for k,v in pairs:
  if k in out:raise ValueError('duplicate JSON key: '+k)
  out[k]=v
 return out
def read(p):return json.loads(Path(p).read_bytes(),object_pairs_hook=strict)
def parse(raw):return json.loads(raw,object_pairs_hook=strict)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def file_sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
 return h.hexdigest()
class Checks:
 def __init__(self):self.count=0
 def need(self,name,value):
  self.count+=1
  if not value:raise ValueError(name)
 def eq(self,name,a,b):
  if type(a) in (set,bytes) or type(b) in (set,bytes):self.need(name,type(a) is type(b) and a==b)
  else:self.need(name,canonical(a)==canonical(b))
 def num(self,name,v):self.need(name,type(v) in (int,float) and math.isfinite(v) and v>=0)
 def near(self,name,a,b):self.need(name,type(a) in (int,float) and math.isfinite(a) and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12))
 def hex(self,name,v,n=64):self.need(name,type(v) is str and len(v)==n and set(v)<=set('0123456789abcdef'))

def economics(num,den,seed):
 med=statistics.median;n=len(num);ratio=med(num)/med(den);rng=random.Random(seed);draws=[]
 for _ in range(10000):
  ids=[rng.randrange(n) for _ in range(n)]
  draws.append(med([num[i] for i in ids])/med([den[i] for i in ids]))
 draws.sort();ci=[draws[249],draws[9749]];wins=sum(a<b for a,b in zip(num,den))
 passed=ratio<1 and wins*2>n and ci[1]<1
 return dict(apply_median_wall_seconds=med(num),direct_median_wall_seconds=med(den),median_ratio=ratio,
  paired_wins=wins,paired_count=n,bootstrap_ratio_interval_95=ci,bootstrap_repetitions=10000,
  bootstrap_seed=seed,passed=passed,status='SPEEDUP' if passed else 'NO_SPEEDUP')
def economic_check(c,name,r,num,den,seed,scope,metric,candidate='shared_json',control='canonical_json',setup=False):
 for x in num+den:c.num(name+':finite duration',x)
 c.need(name+':positive timings',all(x>0 for x in num+den))
 v=economics(num,den,seed)
 for k,x in v.items():
  if type(x) is float:c.near(name+':'+k,r[k],x)
  elif type(x) is list:
   c.eq(name+':CI length',len(r[k]),2)
   for a,b in zip(r[k],x):c.near(name+':CI',a,b)
  else:c.eq(name+':'+k,r[k],x)
 for k,x in dict(scope=scope,measurement=metric,candidate_arm=candidate,control_arm=control,setup_in_timed_update=setup).items():c.eq(name+':scope:'+k,r[k],x)
 return dict(v,saving_percent=(1-v['median_ratio'])*100,scope=scope,measurement=metric)

def command(c,name,r):
 c.eq(name+':success',r['returncode'],0);c.eq(name+':timeout',r['timed_out'],False)
 c.need(name+':actual command',type(r['command']) is list and len(r['command'])>=2)
 c.num(name+':wall',r['wall_seconds'])
 c.num(name+':CPU',r['completed_child_cpu_seconds'])
 for stream in ('stdout','stderr'):c.hex(name+':'+stream,r[stream+'_sha256'])

def arm_check(c,a,profile,variant,mode,binary):
 n=TOTAL[profile];k=CHECKED[profile][variant]
 for f in ('wall_seconds','kernel_seconds','identity_seconds','producer_seconds','persistence_seconds','setup_seconds','constructor_seconds','start_seconds','setup_plus_apply_component_sum_seconds'):c.num('arm:duration:'+f,a[f])
 c.near('arm:setup+apply',a['setup_plus_apply_component_sum_seconds'],a['setup_seconds']+a['wall_seconds'])
 c.need('arm:setup contains constructor+start',a['setup_seconds']+1e-6>=a['constructor_seconds']+a['start_seconds'])
 c.eq('arm:checked',a['checked'],k);c.eq('arm:reused',a['reused'],n-k)
 c.eq('arm:comparison policy',a['signed_comparison_policy'],mode)
 for f in ('export_sha256','decisions_sha256','receipt_sha256','result_sha256','baseline_result_sha256'):c.hex('arm:'+f,a[f])
 c.eq('arm:sealed export',a['export_sha256'],a['snapshot']['sha256'])
 c.eq('arm:seals',a['snapshot']['seals']&15,15);c.eq('arm:required seals',a['snapshot']['required_seals'],15)
 for name,digest in a['policy_tool_sha256'].items():c.eq('arm:pinned tool:'+name,digest,binary[name])
 c.eq('arm:all tool names',set(a['policy_tool_sha256']),set(binary)-{'full_checker'})
 r=a['kernel_report'];c.eq('arm:kernel kind',r['kernel'],'sokonanoda_real_selected_declaration_check')
 for f,x in dict(status='checked',code=0,checked=k,total_declarations=n,scope='selected_obligations_under_caller_trusted_environment').items():c.eq('arm:kernel:'+f,r[f],x)
 for f in ('delta_parse_and_finish_seconds','selected_check_seconds'):c.num('arm:kernel duration',r[f])
 audit=a['receipt_audit']
 for f in ('issuer_hmac_valid','all_content_addresses_valid'):c.eq('arm:observed audit:'+f,audit[f],True)
 c.eq('arm:sparse schema',audit['receipt_schema'],SPARSE);c.eq('arm:no full index',audit['contains_complete_index'],False)
 c.eq('arm:receipt bytes',a['sparse_receipt_bytes'],audit['receipt_bytes'])
 for name in ('direct_rust','full_index_oracle'):command(c,'arm:'+name,a[name])
 p=a['partition_audit'];checked,reused=p['checked_indices'],p['reused_indices']
 c.eq('arm:actual total',p['actual_kernel_total'],n);c.eq('arm:actual checked',p['actual_kernel_checked'],k)
 c.eq('arm:actual reused',p['independently_replayed_reused'],n-k)
 c.need('arm:exact partition',len(set(checked))==len(checked)==k and len(set(reused))==len(reused)==n-k and not set(checked)&set(reused) and set(checked+reused)==set(range(n)))
 p=a['phases'];t=p['timings']
 c.eq('arm:phase keys',set(p),{'timings','memory','counts','representation','producer_report','typed_update','native_kernel_report'})
 for f,v in t.items():
  if f.endswith('_seconds'):c.num('arm:phase finite:'+f,v)
 for f,field in [('kernel_seconds','checking_seconds'),('identity_seconds','identity_update_seconds'),('producer_seconds','producer_seconds'),('persistence_seconds','persistence_seconds')]:c.eq('arm:projected phase',a[f],t[field])
 c.need('arm:complete apply contains reported API interval',a['wall_seconds']+1e-6>=t['end_to_end_seconds'])
 c.eq('arm:phase kernel',p['native_kernel_report'],r)
 for f,x in dict(total=n,rechecked=k,reused=n-k).items():c.eq('arm:phase counts',p['counts'][f],x)
 c.need('arm:actual memory observations',bool(p['memory']))
 for phase,m in p['memory'].items():
  c.need('arm:honest memory scope','cumulative' in m['scope'] and 'not exact phase peaks' in m['scope'])
  c.need('arm:memory process map',type(m['processes']) is dict)
  for proc,fields in m['processes'].items():
   for key,value in fields.items():c.need('arm:procfs numeric',type(value) is int and value>=0)
 c.eq('arm:immutable snapshot',p['representation']['immutable_memfd'],True)
 c.eq('arm:no full export write',p['representation']['full_export_disk_bytes_written'],0)
 b=a['baseline_result'];c.eq('arm:baseline verified',b['status'],'VERIFIED');c.eq('arm:baseline full check',b['counts']['rechecked'],n)

def comparison_check(report,source,c):
 c.eq('comparison:schema',report['schema'],SCHEMA);c.eq('comparison:source',report['source_sha'],source)
 c.eq('comparison:scope',report['scope'],SCOPE)
 for f in ('qualified','completed','correctness_passed'):c.eq('comparison:'+f,report.get(f),True)
 c.eq('comparison:arms',report['arms'],list(MODES));c.eq('comparison:control',report['control'],MODES[0]);c.eq('comparison:candidate',report['candidate'],MODES[1])
 c.eq('comparison:profiles',set(report['profiles']),set(TOTAL))
 c.eq('comparison:binary names',set(report['binary_sha256']),{'producer','checker','retained_checker','indexer','index_session','full_checker'})
 for value in report['binary_sha256'].values():c.hex('comparison:binary digest',value)
 out={}
 for profile,p in report['profiles'].items():
  controls=p['cross_mode_controls'];c.eq('comparison:cross modes',len(controls),2)
  c.eq('comparison:cross directions',{(x['source_mode'],x['target_mode']) for x in controls},{MODES,MODES[::-1]})
  for x in controls:
   c.eq('comparison:control passed',x['passed'],True)
   c.eq('comparison:control expected cause',x['expected_refusal'],'source-owner genesis provenance mismatch')
   c.eq('comparison:control actual cause',x['observed_refusal'],x['expected_refusal'])
   c.need('comparison:control existing records',bool(x['accepted_records_before']))
   c.eq('comparison:control no new acceptance',x['accepted_records_before'],x['accepted_records_after'])
  c.eq('comparison:cold both policies',set(p['cold_restart']),set(MODES))
  for mode,cold in p['cold_restart'].items():
   c.eq('comparison:cold passed',cold['passed'],True);arm_check(c,cold['arm'],profile,'early-definition',mode,report['binary_sha256'])
   c.eq('comparison:cold same export',cold['source_sha256'],cold['arm']['export_sha256'])
   warm=p['early-definition']['pairs'][0]['arms'][mode]
   c.eq('comparison:cold original accepted ID',cold['evidence_id'],warm['receipt_sha256'])
   for field in ('export_sha256','decisions_sha256'):c.eq('comparison:cold original decision',cold['arm'][field],warm[field])
  out[profile]={}
  for variant in VARIANTS:
   r=p[variant];pairs=r['pairs'];c.eq('comparison:complete case',r['complete'],True)
   c.eq('comparison:five pairs',len(pairs),5);c.eq('comparison:repetitions',sorted(x['repetition'] for x in pairs),list(range(5)))
   for pair in pairs:
    i=pair['repetition'];c.eq('comparison:variant',pair['variant'],variant)
    c.eq('comparison:alternating order',pair['order'],list(MODES if (i+(variant=='unrelated-definition'))%2==0 else MODES[::-1]))
    c.eq('comparison:two arms',set(pair['arms']),set(MODES))
    for mode,a in pair['arms'].items():
     arm_check(c,a,profile,variant,mode,report['binary_sha256'])
     if i==0:
      c.eq('comparison:Cpp+paranoid',a['cpp_oracles'],{'leanchecker':0,'leanchecker-paranoid':0})
      c.need('comparison:representative witnesses',bool(a['representative_witness']))
    for key in ('checked','reused','export_sha256','decisions_sha256','policy_tool_sha256'):
     c.eq('comparison:pair parity:'+key,pair['arms'][MODES[0]][key],pair['arms'][MODES[1]][key])
   result={}
   for key,field,seed in [('warm_economics','wall_seconds',20261017),('selected_kernel_economics','kernel_seconds',20261027),('persistence_economics','persistence_seconds',20261030),('setup_plus_one_apply_component_sum_economics','setup_plus_apply_component_sum_seconds',20261031)]:
    num=[x['arms'][MODES[1]][field] for x in pairs];den=[x['arms'][MODES[0]][field] for x in pairs]
    result[key]=economic_check(c,key,r[key],num,den,seed,SCOPE+' Observed '+field+'.',field,setup=field=='setup_plus_apply_component_sum_seconds')
   result['warm_cpu_economics']=economic_check(c,'CPU',r['warm_cpu_economics'],[x['arms'][MODES[1]]['phases']['timings']['end_to_end_cpu_seconds'] for x in pairs],[x['arms'][MODES[0]]['phases']['timings']['end_to_end_cpu_seconds'] for x in pairs],20261028,SCOPE+' Complete apply CPU.','cpu_seconds')
   result['direct_full_rust_economics']={}
   result['arms']={}
   for mode in MODES:
    aa=[x['arms'][mode] for x in pairs]
    result['direct_full_rust_economics'][mode]=economic_check(c,'direct Rust',r['direct_full_rust_economics'][mode],[x['wall_seconds'] for x in aa],[x['direct_rust']['wall_seconds'] for x in aa],20261029,'Complete warm '+mode+' apply versus fresh full Rust check of the same live sealed snapshot; distinct from receipt comparison.','wall_seconds',candidate=mode,control='same_snapshot_fresh_full_rust')
    result['arms'][mode]=dict(phase_medians={f:statistics.median(x['phases']['timings'][f] for x in aa) for f in aa[0]['phases']['timings'] if f.endswith('_seconds')},
     warm_wall_seconds=statistics.median(x['wall_seconds'] for x in aa),setup_wall_seconds=statistics.median(x['setup_seconds'] for x in aa),
     direct_wall_seconds=statistics.median(x['direct_rust']['wall_seconds'] for x in aa),direct_cpu_seconds=statistics.median(x['direct_rust']['completed_child_cpu_seconds'] for x in aa),
     memory_observations=[x['phases']['memory'] for x in aa],
     setup_plus_apply_component_sum_seconds=statistics.median(x['setup_plus_apply_component_sum_seconds'] for x in aa))
    c.near('comparison:startup median',r['median_startup_s'][mode],result['arms'][mode]['setup_wall_seconds'])
   out[profile][variant]=result
 return out

def protected_check(c,r,profile,source):
 c.eq('protected:source',r['source_git_commit'],source)
 for f in ('run_completed','correctness_passed'):c.eq('protected:'+f,r[f],True)
 c.eq('protected:status',r['qualification_status'],'PASS')
 gates=[g for g in r['gates'] if g['required']]
 c.need('protected:minimum required gates',len(gates)>=(246 if profile=='original' else 229))
 c.need('protected:all gates',all(g['passed'] is True for g in gates))
 c.eq('protected:unique gates',len(r['gates']),len({g['name'] for g in r['gates']}))
 samples=r['samples'];c.eq('protected:21 samples',len(samples),21)
 warm=[s for s in samples if not s['cold_replay']]
 c.eq('protected:one cold',len(samples)-len(warm),1)
 c.eq('protected:four by five',{(s['variant'],s['repetition']) for s in warm},{(v,i) for v in ('baseline','theorem-leaf')+VARIANTS for i in range(5)})
 for s in samples:
  c.need('protected:no execution failure','error' not in s)
  a=s['partition_audit'];k=CHECKED[profile][s['variant']];n=TOTAL[profile]
  c.eq('protected:actual checked',a['actual_kernel_checked'],k);c.eq('protected:actual total',a['actual_kernel_total'],n)
  c.eq('protected:replayed reused',a['independently_replayed_reused'],n-k)
  ch,re=a['checked_indices'],a['reused_indices']
  c.need('protected:exact partition',len(ch)==len(set(ch))==k and len(re)==len(set(re))==n-k and not set(ch)&set(re) and set(ch+re)==set(range(n)))
  command(c,'protected:direct',s['direct_rust'])
  policy=s['setup_report']['delta_provenance'];c.eq('protected:retained checker',policy['selected_kernel_backend'],'sha-pinned-retained-parser-v1');c.eq('protected:default mode',policy['receipt_index_comparison'],'shared_json')
  for f in ('issuer_hmac_valid','all_content_addresses_valid'):c.eq('protected:audit',s['persisted_acceptance_audit'][f],True)
 c.eq('protected:complete negative set',set(r['controls']),set(CAUSES)|KERNEL_NEG)
 for name,x in r['controls'].items():
  c.need('protected:no negative execution failure','execution_error' not in x)
  if name in CAUSES:
   observed=x.get('observed_refusal',x.get('exception_refusal',x.get('result',{}).get('reason','')))
   c.need('protected:intended cause:'+name,CAUSES[name] in observed and 'timeout' not in observed.lower())
  if 'result' in x:
   v=x['result'];c.need('protected:no minted negative',not v.get('evidence_id') and not v.get('receipt_id') and v.get('status') in ('UNKNOWN','REJECTED'))
  if name in KERNEL_NEG:
   v=x['result'];c.eq('protected:kernel rejected',v['status'],'REJECTED');c.eq('protected:kernel code',v['checker_result']['code'],1)
   cause=('selected declaration checker thread panicked' if name=='signed-invalid-proof' else
          'unrecognized or repeated simple declaration replacement' if name=='signed-invalid-axiom' else 'expected u16')
   c.need('protected:intended kernel rejection cause:'+name,cause in v['checker_result']['stderr'])
   c.eq('protected:three rejection oracles',set(x['independent_kernel_rejections']),{'rust','leanchecker','leanchecker-paranoid'})
   for y in x['independent_kernel_rejections'].values():c.need('protected:actual full rejection',y['returncode']==1 and y['timed_out'] is False)
   if name.startswith('unused-invalid'):
    c.eq('protected:zero selected',v['counts']['scheduled'],0);c.need('protected:zero selected parser refusal',x['independent_zero_selected_parser']['returncode']==1 and x['independent_zero_selected_parser']['timed_out'] is False)
 return dict(required_gates=len(gates),controls=len(r['controls']),samples=len(samples))

def independent_index(old,patch,c):
 c.eq('index:patch schema',patch['schema'],'mathgraph.export-identity-baseline-patch.v1')
 c.eq('index:patch fields',set(patch),{'schema','count','declarations','builtins'});c.eq('index:count',patch['count'],old['count'])
 rows=list(old['declarations']);previous=-1
 for row in patch['declarations']:
  i=row['index'];c.need('index:ordered patch',type(i) is int and previous<i<len(rows));before=rows[i]
  c.eq('index:row fields',set(row),set(before))
  for f in ('key','name','kind','deps','index'):c.eq('index:fixed topology:'+f,row[f],before[f])
  for f in ('own','closure'):c.hex('index:crypto identity',row[f])
  rows[i]=row;previous=i
 b=dict(old['builtins'])
 for name,v in patch['builtins'].items():
  c.need('index:known builtin',name in b);c.eq('index:builtin key',v[0],b[name][0]);b[name]=v
 return dict(old,declarations=rows,builtins=b)

def independent_decisions(old,new,c):
 same=all(canonical(old[f])==canonical(new[f]) for f in ('meta','builtins','complex'))
 schedule=same and old['schedule']==new['schedule'];before={d['key']:d for d in old['declarations']};prefix=True;out=[]
 for d in new['declarations']:
  prior=before.get(d['key']);prefix=prefix and same and prior is not None and prior['index']==d['index'] and prior['own']==d['own']
  local=schedule and d['kind'] in {'axiom','def','thm','opaque'} and prior is not None and prior['own']==d['own'] and prior['closure']==d['closure']
  reuse=prefix or local
  reason='exact_verified_prefix' if prefix else 'dependency_closure_unchanged' if local else 'complex_outside_verified_prefix' if d['kind'] not in {'axiom','def','thm','opaque'} else 'content_or_transitive_dependency_changed'
  out.append(dict(name=d['name'],index=d['index'],status='VERIFIED_REUSED' if reuse else 'VERIFIED_NEW',reason=reason,dependency_witness=dict(own=d['own'],closure=d['closure'],direct=d['deps'])))
 return out

def baseline_layout(raw,c):
 h=hashlib.sha256();names={0:''};decls=[];nbytes=0
 for line in raw.splitlines(keepends=True):
  row=parse(line)
  if 'in' in row:
   part=row.get('str',row.get('num'));prefix=names[part['pre']];names[row['in']]=(prefix+'.' if prefix else '')+str(part.get('str',part.get('i')))
  tag=next((k for k in row if k in {'axiom','def','thm','opaque','quot','inductive'}),None)
  if tag:decls.append((names[row[tag]['name']] if tag!='inductive' else None,tag,line))
  else:h.update(line);nbytes+=len(line)
 return names,h,decls,nbytes
def composite_digest(layout,delta,changed,c):
 names,h,decls,nbytes=layout;names=dict(names);h=h.copy();replacements={}
 for line in delta.splitlines(keepends=True):
  row=parse(line)
  if 'in' in row:
   part=row.get('str',row.get('num'));prefix=names[part['pre']]
   c.need('composite:append name',row['in'] not in names)
   names[row['in']]=(prefix+'.' if prefix else '')+str(part.get('str',part.get('i')))
  kind=next((k for k in row if k in {'axiom','def','thm','opaque'}),None)
  if kind:
   name=names[row[kind]['name']];c.need('composite:unique replacement',name not in replacements);replacements[name]=(kind,line)
  else:h.update(line);nbytes+=len(line)
 c.eq('composite:announced changes',set(replacements),set(changed));seen=set()
 for name,kind,line in decls:
  if name in replacements:
   k,line=replacements[name];c.eq('composite:declaration kind',kind,k);seen.add(name)
  h.update(line);nbytes+=len(line)
 c.eq('composite:all replacements used',seen,set(replacements))
 return h.hexdigest(),nbytes

class Artifact:
 def __init__(self,root):self.root=Path(root)
 def path(self,p):
  # Archive root is artifacts/, with absolute recorded runner paths retained.
  parts=PurePosixPath(p).parts
  if 'artifacts' in parts:p=Path(*parts[parts.index('artifacts')+1:])
  else:p=Path(p)
  q=(self.root/p).resolve()
  if not q.is_relative_to(self.root.resolve()):raise ValueError('artifact path escape')
  return q
 def load(self,p):return read(self.path(p))

def witness_check(c,a,art,layouts,sources):
 records=a['representative_witness'];roles={}
 for w in records:
  c.need('witness:unique role',w['role'] not in roles);p=art.path(w['path'])
  c.eq('witness:bytes',p.stat().st_size,w['bytes']);c.eq('witness:content SHA',file_sha(p),w['sha256'])
  raw=gzip.decompress(p.read_bytes()) if w.get('encoding')=='gzip' else p.read_bytes()
  if w.get('encoding')=='gzip':c.eq('witness:raw SHA',sha(raw),w['uncompressed_sha256']);c.eq('witness:raw size',len(raw),w['uncompressed_bytes'])
  roles[w['role']]=(raw,w)
 required={'baseline_record','baseline_export','result','accepted_record','representation','delta','transition','direct_rust_stdout','direct_rust_stderr','fresh_native_index_stdout','fresh_native_index_stderr','direct_rust_config','fresh_native_index_config','leanchecker_stdout','leanchecker_stderr','leanchecker-paranoid_stdout','leanchecker-paranoid_stderr'}
 c.need('witness:complete independent reconstruction witnesses',required<=set(roles))
 raw,resultw=roles['result'];c.eq('witness:result SHA',sha(raw),a['result_sha256']);r=parse(raw)
 c.eq('witness:result verified',r['status'],'VERIFIED');c.eq('witness:phase timings',r['timings'],a['phases']['timings']);c.eq('witness:phase memory',r['memory'],a['phases']['memory'])
 for f in ('counts','representation','producer_report','typed_update','native_kernel_report'):c.eq('witness:actual phase projection:'+f,r[f],a['phases'][f])
 raw,_=roles['accepted_record'];c.eq('witness:acceptance ID',sha(raw),a['receipt_sha256']);c.eq('witness:result evidence ID',r['evidence_id'],sha(raw));accepted=parse(raw)['payload']
 c.eq('witness:receipt actual bytes',len(raw),a['sparse_receipt_bytes']);c.eq('witness:canonical receipt envelope',canonical(parse(raw)),raw)
 c.eq('witness:accepted status',accepted['status'],'VERIFIED');c.eq('witness:accepted schema',accepted['schema'],SPARSE);c.need('witness:no full index','index' not in accepted)
 c.eq('witness:signed policy',accepted['producer_provenance'],r['producer_provenance']);c.eq('witness:comparison policy',accepted['producer_provenance']['receipt_index_comparison'],a['signed_comparison_policy'])
 policy=accepted['producer_provenance'];c.eq('witness:signed tool pins',policy['tools'],a['policy_tool_sha256'])
 c.eq('witness:signed adapter source',policy['adapter_sha256'],sources['experiments/incremental/producer_delta.py']);c.eq('witness:signed engine source',policy['engine_sha256'],sources['experiments/incremental/engine.py'])
 base_raw,_=roles['baseline_record'];base_id=sha(base_raw);base=parse(base_raw)['payload'];c.eq('witness:previous evidence',accepted['previous_evidence'],base_id)
 c.eq('witness:baseline acceptance',base['status'],'VERIFIED');c.eq('witness:result previous evidence',r['previous_evidence'],base_id)
 c.eq('witness:baseline result identity',a['baseline_result']['evidence_id'],base_id);c.eq('witness:baseline all actually checked',base['checked_indices'],list(range(base['index']['count'])));c.eq('witness:baseline no reused',base['reused_indices'],[])
 representation_raw,_=roles['representation'];representation=parse(representation_raw);c.eq('witness:representation ID',sha(representation_raw),accepted['delta_representation']);c.eq('witness:representation base',representation['base_evidence_id'],base_id)
 transition_raw,_=roles['transition'];transition=parse(transition_raw)['payload'];c.eq('witness:transition ID',sha(transition_raw),representation['transition_id'])
 delta,_=roles['delta'];c.eq('witness:delta SHA',sha(delta),representation['delta_sha256']);c.eq('witness:transition delta',transition['delta_sha256'],sha(delta));c.eq('witness:transition base',transition['base_evidence_id'],base_id)
 export,_=roles['baseline_export'];c.eq('witness:baseline export bytes',sha(export),base['export_sha256']);c.eq('witness:transition baseline export',transition['base_export_sha256'],sha(export))
 cachekey=sha(export)
 if cachekey not in layouts:layouts[cachekey]=baseline_layout(export,c)
 digest,nbytes=composite_digest(layouts[cachekey],delta,transition['changed_names'],c)
 for value in (accepted['export_sha256'],representation['export_sha256'],r['export_sha256'],a['snapshot']['sha256']):c.eq('witness:exact reconstructed composite',digest,value)
 c.eq('witness:composite size',nbytes,a['snapshot']['bytes'])
 new=independent_index(base['index'],accepted['index_patch'],c);native=parse(roles['fresh_native_index_stdout'][0]);c.eq('witness:fresh native typed index',new,native)
 expected=independent_decisions(base['index'],native,c)
 actual=[{k:d[k] for k in ('name','index','status','reason','dependency_witness')} for d in r['decisions']]
 c.eq('witness:independent complete decision replay',actual,expected);c.eq('witness:decision digest',sha(canonical(expected)),a['decisions_sha256'])
 c.eq('witness:checked indices',accepted['checked_indices'],[d['index'] for d in expected if d['status']=='VERIFIED_NEW'])
 for label in ('direct_rust','fresh_native_index'):
  record=a[label] if label=='direct_rust' else a['full_index_oracle']
  for stream in ('stdout','stderr'):c.eq('witness:actual raw stream SHA',sha(roles[label+'_'+stream][0]),record[stream+'_sha256'])
  config=parse(roles[label+'_config'][0]);c.eq('witness:configured sealed input',config['export_file_path'],a['snapshot']['path'])
  c.eq('witness:one thread',config['num_threads'],1);c.eq('witness:axiom policy',config['permitted_axioms'],['propext','Classical.choice','Quot.sound']);c.eq('witness:hard axiom errors',config['unpermitted_axiom_hard_error'],True)
  for f in ('nat_extension','string_extension'):c.eq('witness:kernel extensions',config[f],True)
 c.need('witness:actual full Rust success output',('Checked '+str(len(expected))+' declarations with no errors') in roles['direct_rust_stdout'][0].decode())
 for label in ('leanchecker','leanchecker-paranoid'):
  record=a['independent_kernels'][label];command(c,'witness:Cpp command',record)
  c.eq('witness:Cpp same snapshot',record['command'][1:],['--from-export',a['snapshot']['path']])
  for stream in ('stdout','stderr'):c.eq('witness:Cpp raw output',sha(roles[label+'_'+stream][0]),record[stream+'_sha256'])
 return dict(export_sha256=digest,export_bytes=nbytes,obligations=len(expected),checked=len(accepted['checked_indices']),receipt_id=r['evidence_id'],historical_hmac_authenticated_by_this_review=False)

def git_bytes(repo,source,path):return subprocess.check_output(['git','show',source+':'+path],cwd=repo)
def source_check(c,r,repo,source):
 for path,digest in r['source_sha256'].items():c.eq('source:Git-pinned bytes:'+path,sha(git_bytes(repo,source,path)),digest)
def inner_binding(c,inner,profile,mode,comparison):
 warm=[s for s in inner['samples'] if not s['cold_replay']]
 c.eq('inner:exact warm keys',{(s['variant'],s['repetition']) for s in warm},{(v,i) for v in VARIANTS for i in range(5)})
 for s in inner['samples']:
  c.need('inner:no sample execution failure','error' not in s)
  if s['cold_replay']:
   a=comparison['profiles'][profile]['cold_restart'][mode]['arm']
  else:
   pairs=comparison['profiles'][profile][s['variant']]['pairs'];a=next(p for p in pairs if p['repetition']==s['repetition'])['arms'][mode]
  for field,sfield in [('wall_seconds','apply_wall_seconds'),('setup_seconds','setup_wall_seconds'),('constructor_seconds','session_constructor_wall_seconds'),('start_seconds','start_wall_seconds'),('receipt_sha256','evidence_id'),('receipt_audit','persisted_acceptance_audit')]:c.eq('inner:actual sample projection:'+field,a[field],s[sfield])
  for field in ('snapshot','direct_rust','full_index_oracle','partition_audit','baseline_result','baseline_result_path','baseline_result_sha256','setup_report','result_path'):c.eq('inner:actual sample projection:'+field,a[field],s[field])
  c.eq('inner:actual signed comparison policy',s['setup_report']['delta_provenance']['receipt_index_comparison'],mode)
def legacy_check(c,art,source):
 out={}
 for folder,flag,n in [('original-qualification','qualification_passed',197),('native-qualification','qualification_passed',335),('native-independent-replay','passed',719),('native-benchmark','correctness_passed',251)]:
  r=art.load(folder+'/summary.json');c.eq('legacy:complete:'+folder,r[flag],True);g=r['gates']
  c.need('legacy:all gates:'+folder,len(g)>=n and all(x['passed'] is True for x in g))
  if 'source_git_commit' in r:c.eq('legacy:source',r['source_git_commit'],source)
  out[folder]=dict(gates=len(g),summary_sha256=file_sha(art.path(folder+'/summary.json')))
 return out

def archive_extract(path,destination,c):
 destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(path) as z:
  c.eq('archive:CRC',z.testzip(),None);c.eq('archive:unique names',len(z.namelist()),len(set(z.namelist())))
  for info in z.infolist():
   p=PurePosixPath(info.filename);c.need('archive:safe member',not p.is_absolute() and '..' not in p.parts and ((info.external_attr>>16)&0o170000)!=0o120000)
  z.extractall(destination)
 roots=list(destination.rglob('ci-observations.json'));c.eq('archive:single evidence root',len(roots),1)
 return roots[0].parent
def metadata_check(c,args):
 run=read(args.run);jobs=read(args.jobs);artifacts=read(args.artifacts)
 if 'workflow_run' in run:run=run['workflow_run']
 if 'jobs' in jobs:jobs=jobs['jobs']
 if 'artifacts' in artifacts:artifacts=artifacts['artifacts']
 c.eq('provider:run id',run['id'],args.run_id);c.eq('provider:run source',run['head_sha'],args.source)
 c.eq('provider:run completed',run['status'],'completed');c.eq('provider:run success',run['conclusion'],'success')
 job=next(x for x in jobs if x['id']==args.job_id)
 c.eq('provider:job success',job['conclusion'],'success');c.eq('provider:job completed',job['status'],'completed')
 if 'run_id' in job:c.eq('provider:job run',job['run_id'],args.run_id)
 if 'head_sha' in job:c.eq('provider:job source',job['head_sha'],args.source)
 for step in job['steps']:c.eq('provider:all actual steps success:'+step['name'],step['conclusion'],'success')
 record=next(x for x in artifacts if x['id']==args.artifact_id)
 c.eq('provider:archive bytes',Path(args.archive).stat().st_size,record['size_in_bytes'])
 c.eq('provider:archive digest','sha256:'+file_sha(args.archive),record['digest'])
 c.eq('provider:artifact source',record['workflow_run']['head_sha'],args.source);c.eq('provider:artifact run',record['workflow_run']['id'],args.run_id)
 c.eq('provider:not expired',record['expired'],False)
 c.eq('provider:artifact exact name',record['name'],'receipt-comparison-summaries-'+args.source)
 return dict(run_id=args.run_id,job_id=args.job_id,artifact_id=args.artifact_id,archive_sha256=file_sha(args.archive),archive_bytes=Path(args.archive).stat().st_size)

def review(args):
 c=Checks();transport=metadata_check(c,args);root=archive_extract(args.archive,Path(args.out)/'artifact',c);art=Artifact(root)
 r=art.load('receipt-comparison/summary.json');out=comparison_check(r,args.source,c);source_check(c,r,args.repo,args.source)
 phases=art.load('receipt-comparison/compact-phases.json');c.eq('phase:schema',phases['schema'],'mathgraph.receipt-comparison-phases.v1');c.eq('phase:complete',phases['completed'],True);c.eq('phase:source',phases['source_sha'],args.source);c.eq('phase:exact projection',phases['profiles'],r['profiles'])
 observed=art.load('ci-observations.json');c.eq('publisher:source',observed['source_sha'],args.source);c.eq('publisher:correctness',observed['correctness_passed'],True);c.eq('publisher:no failures',observed['failures'],[])
 for label,path in [('original-197','original-qualification/summary.json'),('native-335','native-qualification/summary.json'),('independent-719','native-independent-replay/summary.json'),('old-binary-251','native-benchmark/summary.json'),('protected-shared-default','receipt-protected/protected-summary.json'),('retained-parser-shadow','retained-parser-shadow/summary.json'),('receipt-comparison','receipt-comparison/summary.json')]:
  c.eq('publisher:exact report SHA:'+label,observed['reports'][label]['summary_sha256'],file_sha(art.path(path)))
 protected={};aggregate=art.load('receipt-protected/protected-summary.json');c.eq('protected aggregate:source',aggregate['source_sha'],args.source);c.eq('protected aggregate:qualified',aggregate['qualified'],True)
 for profile in TOTAL:
  q=art.load('receipt-protected/'+profile+'/protected-matrix/retained_selected/summary.json');protected[profile]=protected_check(c,q,profile,args.source)
  ap=aggregate['profiles'][profile];c.eq('protected aggregate:source',ap['source_sha'],args.source);c.eq('protected aggregate:complete',ap['qualification_status'],'PASS');c.eq('protected aggregate:no failures',ap['failed_gates'],[])
  c.eq('protected aggregate:actual gate count',ap['required_gates'],protected[profile]['required_gates']);c.eq('protected aggregate:sample count',ap['actual_samples'],21)
  c.eq('protected aggregate:signed backend',ap['signed_kernel_backend'],'sha-pinned-retained-parser-v1');c.eq('protected aggregate:pinned kernel',ap['retained_kernel_tool_sha256'],r['binary_sha256']['retained_checker'])
  for path,digest in q['measured_source_sha256'].items():c.eq('protected:source bytes',digest,sha(git_bytes(args.repo,args.source,path)))
  c.eq('protected:harness digest',q['harness_sha256'],sha(git_bytes(args.repo,args.source,'experiments/incremental/qualify_delta.py')))
  for name,digest in r['binary_sha256'].items():c.eq('protected:shared measured binaries',digest,q['tools'][name]['sha256'])
  for mode in MODES:
   inner=art.load('receipt-comparison/'+profile+'/comparison/'+mode+'/summary.json')
   for f in ('run_completed','correctness_passed'):c.eq('inner:complete',inner[f],True)
   c.eq('inner:status',inner['qualification_status'],'PASS');c.eq('inner:source',inner['source_git_commit'],args.source)
   c.need('inner:all required gates',bool(inner['gates']) and all(g['passed'] is True for g in inner['gates'] if g['required']))
   c.eq('inner:eleven actual samples',len(inner['samples']),11)
   inner_binding(c,inner,profile,mode,r)
   for path,digest in inner['measured_source_sha256'].items():c.eq('inner:source bytes',digest,sha(git_bytes(args.repo,args.source,path)))
   for name,digest in r['binary_sha256'].items():c.eq('inner:shared measured binaries',digest,inner['tools'][name]['sha256'])
 shadow=art.load('retained-parser-shadow/summary.json');c.eq('shadow:source',shadow['source_sha'],args.source);c.eq('shadow:complete',shadow['complete'],True);c.eq('shadow:reps',shadow['repetitions'],5)
 for path,digest in shadow['source_hashes'].items():c.eq('shadow:source bytes',digest,sha(git_bytes(args.repo,args.source,path)))
 for name,digest in shadow['binary_hashes'].items():c.eq('shadow:shared binary',digest,r['binary_sha256']['checker' if name=='selected_checker' else name])
 for profile in TOTAL:
  for v in VARIANTS:
   ss=shadow['profiles'][profile][v];c.eq('shadow:case complete',ss['complete'],True);c.eq('shadow:five pairs',len(ss['samples']),5)
   for s in ss['samples']:
    c.eq('shadow:obligation parity',s['trials']['fresh']['checked'],s['trials']['retained']['checked'])
    if s['repetition']==0:
     c.eq('shadow:all oracle names',set(s['full_oracles']),{'full-rust','cxx','paranoid-cxx'})
     for cmd in s['full_oracles'].values():c.eq('shadow:full success',cmd['returncode'],0)
  for name in ('malformed-unused-node','overwrite-admitted-expression'):
   v=shadow['negative_controls'][profile+'-'+name];c.eq('shadow:negative pass',v['passed'],True);c.eq('shadow:negative no checks',v['checked'],[])
   cause='expected u16' if name=='malformed-unused-node' else 'changed typed expression DAG index overwrites admitted baseline'
   c.need('shadow:intended parser rejection',cause in v['reason'])
 legacy=legacy_check(c,art,args.source);witnesses={};layouts={}
 for profile in TOTAL:
  for variant in VARIANTS:
   for mode in MODES:
    a=r['profiles'][profile][variant]['pairs'][0]['arms'][mode]
    witnesses[profile+'/'+variant+'/'+mode]=witness_check(c,a,art,layouts,r['source_sha256'])
 # Source stability logs are observations; exact manifest bytes are independently Git-bound.
 for kind in ('source','binaries'):
  before=art.path(kind+'-before.sha256').read_bytes();after=art.path(kind+'-after.sha256').read_bytes();c.eq('stability:before/after manifest',before,after)
  lines=before.decode().splitlines();c.need('stability:nonempty manifest',bool(lines))
  if kind=='source':
   for line in lines:
    digest,path=line.split('  ',1);c.eq('stability:Git source',digest,sha(git_bytes(args.repo,args.source,path)))
  else:
   manifest={x['path']:x['sha256'] for x in art.load('binaries-before.json')}
   c.eq('stability:binary manifest binding',dict(line.split('  ',1)[::-1] for line in lines),manifest)
 result=dict(schema='independent.receipt-comparison-review.v1',source=args.source,transport=transport,passed=True,status='PASS_COMPACT_CONTENT_SOURCE_ARITHMETIC',check_count=c.count,
  economics=out,protected=protected,legacy=legacy,representative_witnesses=witnesses,
  helper_sha256=file_sha(__file__),limitations=[
   'Standard-library independent content/source/observation/arithmetic review; no engine/controller imports and no new kernel execution.',
   'Historical HMAC keys are not included; issuer authentication is an archived actual harness observation, not independently reauthenticated by this reviewer.',
   'Eight representative complete raw receipt/baseline/delta/result/native-index witnesses are replayed structurally; other samples rely on compact actual observations and their published hashes.',
   'Binary before/after equality and source association are archived CI observations; executable bytes are in the separately downloadable full artifact, not rebuilt by this review.',
   'Warm paired arm comparison, fresh full Rust comparison, phase costs and setup+one-apply components have separate scopes; shutdown and multi-update amortization are unmeasured.',
   'Procfs VmRSS/VmHWM are post-phase observations, HWM cumulative startup-inclusive, missing exited processes are missing; these do not establish total/phase peak-memory savings.',
   'Full sparse acceptance reconstruction, second conservative reuse, export materialization/hash, declaration-list scan and cold setup remain linear in admitted state.'])
 if args.falsifiers:result['falsifiers']=falsifiers(r,args.source)
 Path(args.out).mkdir(parents=True,exist_ok=True);Path(args.out,'review.json').write_text(json.dumps(result,indent=2)+'\n')
 return result

def falsifiers(r,source):
 mutations=[('partial',lambda x:x.update(completed=False)),('false correctness',lambda x:x.update(correctness_passed=False)),
  ('wrong source',lambda x:x.update(source_sha='0'*40)),('missing pair',lambda x:x['profiles']['original']['early-definition']['pairs'].pop()),
  ('duplicate repetition',lambda x:x['profiles']['original']['early-definition']['pairs'][1].update(repetition=0)),
  ('wrong count',lambda x:x['profiles']['expanded']['early-definition']['pairs'][0]['arms']['shared_json'].update(checked=0)),
  ('wrong policy',lambda x:x['profiles']['original']['early-definition']['pairs'][0]['arms']['shared_json'].update(signed_comparison_policy='canonical_json')),
  ('wrong kernel',lambda x:x['profiles']['original']['early-definition']['pairs'][0]['arms']['shared_json']['kernel_report'].update(kernel='hint')),
  ('false audit',lambda x:x['profiles']['original']['early-definition']['pairs'][0]['arms']['shared_json']['receipt_audit'].update(issuer_hmac_valid=False)),
  ('timeout comparator',lambda x:x['profiles']['original']['early-definition']['pairs'][0]['arms']['shared_json']['direct_rust'].update(timed_out=True)),
  ('altered timing',lambda x:x['profiles']['original']['early-definition']['pairs'][0]['arms']['shared_json'].update(wall_seconds=99)),
  ('wrong CPU metric',lambda x:x['profiles']['original']['early-definition']['warm_cpu_economics'].update(measurement='wall_seconds')),
  ('wrong economic scope',lambda x:x['profiles']['original']['early-definition']['warm_economics'].update(scope='fresh Rust')),
  ('false cold',lambda x:x['profiles']['original']['cold_restart']['shared_json'].update(passed=False)),
  ('wrong mode refusal',lambda x:x['profiles']['original']['cross_mode_controls'][0].update(observed_refusal='timeout')),
  ('persisted cross-mode acceptance',lambda x:x['profiles']['original']['cross_mode_controls'][0]['accepted_records_after'].update(forged='0'*64)),
  ('missing witness',lambda x:x['profiles']['original']['early-definition']['pairs'][0]['arms']['shared_json'].update(representative_witness=[])),
  ('negative phase',lambda x:x['profiles']['original']['early-definition']['pairs'][0]['arms']['shared_json']['phases']['timings'].update(end_to_end_cpu_seconds=-1))]
 out=[]
 for name,mutate in mutations:
  v=copy.deepcopy(r);mutate(v)
  try:comparison_check(v,source,Checks())
  except (ValueError,KeyError,TypeError,IndexError) as e:out.append(dict(name=name,passed=True,refusal=str(e)))
  else:raise ValueError('falsifier accepted: '+name)
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for arg in ('repo','source','archive','artifacts','run','jobs','out'):p.add_argument('--'+arg,required=True)
 for arg in ('run-id','job-id','artifact-id'):p.add_argument('--'+arg,type=int,required=True)
 p.add_argument('--falsifiers',action='store_true');args=p.parse_args()
 try:
  result=review(args);print(json.dumps({k:result[k] for k in ('status','passed','check_count','source')}))
 except Exception as e:
  Path(args.out).mkdir(parents=True,exist_ok=True);Path(args.out,'review.json').write_text(json.dumps(dict(passed=False,status='FAIL_OR_INCOMPLETE',error=type(e).__name__+': '+str(e),helper_sha256=file_sha(__file__)),indent=2)+'\n');raise
if __name__=='__main__':main()
