#!/usr/bin/env python3
"""Independent compact phase/archive checks; never reads omitted sample result JSON.

Uses only retained summaries, frozen publisher projections, source Git bytes,
checksum logs and the downloaded ZIP. Does not run kernels or authenticate old
issuer HMACs. VmHWM observations are cumulative post-phase observations in KiB.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile

VARIANTS=('early-definition','unrelated-definition','theorem-leaf','baseline')
HEX=re.compile('[0-9a-f]{64}\\Z')
MEMORY_SCOPE='Verbatim post-phase procfs samples in KiB. VmHWM is cumulative since process startup; no exact phase peak or aggregate RSS is inferred.'
PROCESS_SCOPE='Post-phase procfs samples; VmHWM is cumulative since process startup; not exact phase peaks or aggregate memory savings'
CPU_SCOPE='Adapter + completed children + live producer/index procfs ticks; live counters have SC_CLK_TCK granularity'
PHASES=('producer','validation','identity','materialization','checking','persistence')
OLD={
 'original-correctness':('original-qualification/summary.json',197,'qualification_passed'),
 'native-correctness':('native-qualification/summary.json',335,'qualification_passed'),
 'independent-replay':('native-independent-replay/summary.json',719,'passed'),
 'native-economics':('native-benchmark/summary.json',251,'correctness_passed')}
PROFILES={'producer-delta':('delta-qualification','original-qualified-3436',3436),
          'producer-delta-expanded':('delta-expanded-qualification','std-hashmap-expanded-v1',11653)}


def canonical(value):
 return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
 def pairs(items):
  result={}
  for key,value in items:
   if key in result:raise ValueError('duplicate JSON key: '+key)
   result[key]=value
  return result
 def constant(value):raise ValueError('nonfinite JSON number: '+value)
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)


def median(values):
 values=sorted(values);middle=len(values)//2
 return values[middle] if len(values)%2 else (values[middle-1]+values[middle])/2


class Checks:
 def __init__(self):self.count=0;self.failures=[]
 def need(self,name,condition):
  self.count+=1
  if not condition:
   self.failures.append(name);raise ValueError(name)
 def equal(self,name,left,right):self.need(name,canonical(left)==canonical(right))
 def near(self,name,left,right):
  self.need(name,type(left) in (float,int) and type(right) in (float,int) and
            math.isfinite(left) and math.isfinite(right) and math.isclose(left,right,rel_tol=1e-12,abs_tol=1e-12))
 def number(self,name,value):
  self.need(name,type(value) in (float,int) and math.isfinite(value) and value>=0)
 def digest(self,name,value):self.need(name,type(value) is str and HEX.fullmatch(value) is not None)


def collapse_roots(value):
 if type(value) is dict:
  return {key:({'count':len(item),'canonical_sha256':sha(canonical(item))}
               if key=='roots' and type(item) is list else collapse_roots(item))
          for key,item in value.items()}
 if type(value) is list:return [collapse_roots(item) for item in value]
 return value


def numeric_medians(checks,name,rows):
 checks.need(name+':nonempty',bool(rows))
 fields=set().union(*(row.keys() for row in rows))
 checks.need(name+':complete-fields',all(set(row)==fields for row in rows))
 for row in rows:
  for field,value in row.items():checks.number(name+':'+field,value)
 return {field:median([row[field] for row in rows]) for field in sorted(fields)}


def phase_review(phase,summary,source,summary_raw,checks):
 checks.equal('phase:schema',phase.get('schema'),'mathgraph.producer-delta-compact-phases.v1')
 checks.equal('phase:source',phase.get('source_sha'),source)
 checks.equal('phase:summary-digest',phase.get('summary_sha256'),sha(summary_raw))
 checks.equal('phase:harness',phase.get('harness_sha256'),summary.get('harness_sha256'))
 checks.equal('phase:host',phase.get('host'),summary.get('host'))
 checks.equal('phase:policy',phase.get('measurement_policy'),summary.get('measurement_policy'))
 checks.equal('phase:profile',phase.get('profile'),summary.get('profile'))
 checks.equal('phase:honest-memory-scope',phase.get('memory_scope'),MEMORY_SCOPE)
 checks.need('phase:completed-main-report',summary.get('run_completed') is True and
             summary.get('correctness_passed') is True and summary.get('qualification_status')=='PASS')
 repetitions=summary.get('repetitions')
 checks.need('phase:five-or-more',type(repetitions) is int and repetitions>=5)
 samples=phase.get('samples',[]);main=summary.get('samples',[])
 checks.need('phase:sample-count',len(samples)==len(main)==4*repetitions+1)
 def key(row):return (row['variant'],str(row['repetition']),row['cold_replay'])
 checks.need('phase:unique-samples',len({key(row) for row in samples})==len(samples))
 checks.equal('phase:main-sample-set',sorted(key(row) for row in samples),sorted(key(row) for row in main))
 mapping={key(row):row for row in main}
 count=11653 if phase['profile']=='std-hashmap-expanded-v1' else 3436
 memory_values={};memory_hwm={};warm_results={}
 for row in samples:
  name='phase:'+row['variant']+':'+str(row['repetition']);original=mapping[key(row)]
  checks.need(name+':cold-boolean',type(row['cold_replay']) is bool)
  for field in ('variant','repetition','cold_replay','apply_wall_seconds','direct_wall_seconds',
                'session_constructor_wall_seconds','start_wall_seconds','setup_wall_seconds',
                'direct_rust','baseline_result','evidence_id','result_path'):
   checks.equal(name+':main:'+field,row.get(field),original.get(field))
  checks.equal(name+':setup-projection',row.get('setup_report'),collapse_roots(original.get('setup_report')))
  checks.digest(name+':result-digest',row.get('result_sha256'))
  checks.digest(name+':export-digest',row.get('export_sha256'))
  checks.equal(name+':same-exact-export',row['export_sha256'],original['snapshot']['sha256'])
  checks.equal(name+':cpu-scope',row.get('cpu_measurement'),CPU_SCOPE)
  counts=row.get('counts',{});audit=original['partition_audit']
  checks.equal(name+':counts',counts,dict(total=count,scheduled=audit['actual_kernel_checked'],
      rechecked=audit['actual_kernel_checked'],reused=audit['independently_replayed_reused'],
      invalidated=audit['actual_kernel_checked']))
  checker=row.get('checker_result',{})
  checks.need(name+':actual-checker-success',checker.get('code')==0 and type(checker.get('code')) is int)
  checks.need(name+':bounded-checker-output',all(type(checker.get(field)) is str and
      len(checker[field].encode())<=16384 for field in ('stdout','stderr')))
  checks.equal(name+':actual-checker-stdout',strict_json(checker['stdout']),
      dict(checked=counts['scheduled'],total_declarations=count,
           scope='selected_obligations_under_caller_trusted_environment'))
  representation=row.get('representation',{})
  checks.equal(name+':representation-bytes',representation,dict(
      delta_bytes=original['persisted_acceptance_audit']['delta_bytes'],
      export_bytes=original['snapshot']['bytes'],full_export_disk_bytes_written=0,immutable_memfd=True))
  producer=row.get('producer_report',{});typed=row.get('typed_update',{})
  checks.need(name+':actual-producer-status',producer.get('status')=='delta' and typed.get('status')=='indexed')
  changed=producer.get('changed_names',[])
  checks.equal(name+':complete-mutation-names',sorted(changed),sorted(typed.get('replaced_names',[])))
  stats=producer.get('stats',{})
  checks.need(name+':bounded-owned-region',stats.get('compared_local_constants')==7 and
      stats.get('imported_identity_retained') is True and stats.get('unchanged_local_constants')+len(changed)==7)
  for field in ('new_exprs','new_levels','new_names'):
   checks.need(name+':producer:'+field,type(stats.get(field)) is int and stats[field]>=0)
  for field in ('rows_processed','dag_rows'):
   checks.need(name+':index:'+field,type(typed.get(field)) is int and typed[field]>=0)
  timings=row.get('timings',{})
  required={'producer_seconds','baseline_validation_seconds','identity_update_seconds',
      'materialization_and_hash_seconds','checking_seconds','persistence_seconds','consumer_seconds',
      'consumer_cpu_seconds','baseline_validation_cpu_seconds','identity_update_cpu_seconds',
      'materialization_and_hash_cpu_seconds','checking_cpu_seconds','persistence_cpu_seconds',
      'end_to_end_seconds','end_to_end_cpu_seconds'}
  checks.need(name+':all-timing-fields',required<=set(timings))
  for field,value in timings.items():checks.number(name+':timing:'+field,value)
  checks.need(name+':outer-contains-apply',row['apply_wall_seconds']+1e-6>=timings['end_to_end_seconds'])
  wall_parts=sum(timings[field] for field in ('baseline_validation_seconds','identity_update_seconds',
      'materialization_and_hash_seconds','checking_seconds','persistence_seconds'))
  checks.need(name+':consumer-contains-wall-phases',timings['consumer_seconds']+1e-6>=wall_parts)
  # CPU procfs counters have tick granularity; no fabricated sub-tick conservation assertion.
  memory=row.get('memory',{})
  checks.equal(name+':memory-stage-set',sorted(memory),sorted(PHASES))
  for stage,observation in memory.items():
   if observation is None:
    checks.need(name+':memory-empty-only-cold-producer',row['cold_replay'] and stage=='producer');continue
   checks.equal(name+':memory-scope:'+stage,observation.get('scope'),PROCESS_SCOPE)
   processes=observation.get('processes',{})
   checks.equal(name+':memory-processes:'+stage,sorted(processes),['adapter','index','producer'])
   for process,fields in processes.items():
    for field in ('VmHWM','VmRSS','RssAnon','RssFile'):
     checks.need(name+':KiB:'+stage+':'+process+':'+field,type(fields.get(field)) is int and fields[field]>=0)
    checks.need(name+':cumulative-hwm:'+stage+':'+process,fields['VmHWM']>=fields['VmRSS'])
    if not row['cold_replay']:
     memory_values.setdefault((row['variant'],process),[]).append(fields['VmRSS'])
     memory_hwm.setdefault((row['variant'],process),[]).append(fields['VmHWM'])
 for variant in VARIANTS:
  warm=[row for row in samples if row['variant']==variant and row['cold_replay'] is False]
  checks.need('phase:complete-warm:'+variant,len(warm)==repetitions and
      sorted(row['repetition'] for row in warm)==list(range(repetitions)))
  timing=numeric_medians(checks,'phase:timing-medians:'+variant,[row['timings'] for row in warm])
  observed=numeric_medians(checks,'phase:observed-medians:'+variant,[dict(
      apply_wall_seconds=row['apply_wall_seconds'],direct_wall_seconds=row['direct_wall_seconds'],
      direct_completed_child_cpu_seconds=row['direct_rust']['completed_child_cpu_seconds'],
      session_constructor_wall_seconds=row['session_constructor_wall_seconds'],
      start_wall_seconds=row['start_wall_seconds'],setup_wall_seconds=row['setup_wall_seconds'],
      start_report_cpu_seconds=row['setup_report']['cpu_seconds']) for row in warm])
  supplied=phase.get('warm_medians_by_variant',{}).get(variant,{})
  checks.equal('phase:sample-count-median:'+variant,supplied.get('sample_count'),repetitions)
  for field,values in (('timings',timing),('observed_wall_and_cpu',observed)):
   checks.equal('phase:median-fields:'+variant+':'+field,sorted(supplied.get(field,{})),sorted(values))
   for metric,value in values.items():checks.near('phase:median:'+variant+':'+field+':'+metric,supplied[field][metric],value)
  wall_fields=('producer_seconds','baseline_validation_seconds','identity_update_seconds',
               'materialization_and_hash_seconds','checking_seconds','persistence_seconds')
  warm_results[variant]=dict(timings=timing,observed_wall_and_cpu=observed,
      remaining_wall_phase_order=sorted(wall_fields,key=lambda key:timing[key],reverse=True),
      observed_memory_KiB={process:dict(VmRSS_sample_range=[min(memory_values[(variant,process)]),
          max(memory_values[(variant,process)])],VmHWM_cumulative_sample_range=[
          min(memory_hwm[(variant,process)]),max(memory_hwm[(variant,process)])])
          for process in ('adapter','producer','index')})
 cold=[row for row in samples if row['cold_replay']]
 checks.need('phase:one-cold-replay',len(cold)==1 and cold[0]['variant']=='early-definition')
 return dict(profile=phase['profile'],source=source,samples=len(samples),
     warm_medians_by_variant=warm_results,cold_replay={key:cold[0][key] for key in
      ('setup_wall_seconds','apply_wall_seconds','direct_wall_seconds','timings')},
     memory_scope=MEMORY_SCOPE)


def gate_report(report,minimum,flag,checks,label):
 gates=report.get('gates',[])
 checks.need(label+':minimum-gates',type(gates) is list and len(gates)>=minimum)
 checks.need(label+':strict-acceptance',report.get(flag) is True)
 checks.need(label+':all-gates-pass',all(type(gate) is dict and gate.get('passed') is True for gate in gates))
 checks.need(label+':unique-gates',len({gate['name'] for gate in gates})==len(gates))
 return len(gates)


class ArchiveReview:
 def __init__(self,args):self.args=args;self.checks=Checks();self.raw={};self.reports={};self.findings={};self.source_cache={}
 def source(self,path):
  if path not in self.source_cache:
   self.source_cache[path]=subprocess.check_output(['git','show',self.args.source+':'+path],cwd=self.args.repo)
  return self.source_cache[path]
 def member(self,suffix):
  found=[name for name in self.names if name==suffix or name.endswith('/'+suffix)]
  self.checks.need('unique-archive-member:'+suffix,len(found)==1)
  return self.archive.read(found[0])
 def load(self,label,suffix):
  self.raw[label]=self.member(suffix);self.reports[label]=strict_json(self.raw[label]);return self.reports[label]
 def mapping(self,raw):
  result={}
  for line in raw.decode().splitlines():
   match=re.fullmatch(r'([0-9a-f]{64}) [ *](.+)',line)
   self.checks.need('checksum-line-valid:'+line[:80],match is not None)
   identity,path=match.groups();self.checks.need('checksum-path-unique:'+path,path not in result)
   result[path]=identity
  return result
 def check_sources(self):
  c=self.checks;source=self.args.source;observations=self.reports['observations']
  c.equal('source:ref',self.member('source-ref.txt').decode().strip(),source)
  c.equal('source:observation',observations.get('source_sha'),source)
  c.equal('source:no-failures',observations.get('failures'),[])
  stable=self.load('stability','source-stability.json')
  c.need('source:stable',stable.get('passed') is True and stable.get('source_sha')==source)
  c.equal('source:observed-stability',observations.get('source_stability'),stable)
  source_sums=self.mapping(self.member('source-SHA256SUMS'))
  verified=self.member('source-checksums-verified.log').decode().splitlines()
  c.equal('source:all-checksum-log-lines',sorted(verified),sorted(path+': OK' for path in source_sums))
  for path,identity in source_sums.items():
   c.need('source:safe-path:'+path,not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts)
   c.equal('source:committed-bytes:'+path,identity,sha(self.source(path)))
  binaries=self.mapping(self.member('delta-binaries-SHA256SUMS'))
  verified=self.member('delta-binaries-verified.log').decode().splitlines()
  c.equal('binary:all-checksum-log-lines',sorted(verified),sorted(path+': OK' for path in binaries))
  c.need('binary:final-tool-universe',set(Path(path).name for path in binaries)==
      {'delta-producer','index-session','export-index','check-selected','sokonanoda'})
  self.binaries={Path(path).name:identity for path,identity in binaries.items()}
  pre=self.mapping(self.member('delta-binaries-pretests-SHA256SUMS'))
  c.equal('binary:producer-stable-before-tests',next(identity for path,identity in pre.items()
      if Path(path).name=='delta-producer'),self.binaries['delta-producer'])
  for label,(suffix,minimum,flag) in OLD.items():
   report=self.load(label,suffix);observation=observations['reports'][label]
   count=gate_report(report,minimum,flag,c,label)
   c.equal(label+':observed-summary',observation.get('summary_sha256'),sha(self.raw[label]))
   c.equal(label+':observed-source',observation.get('source_sha'),source)
   c.need(label+':publisher-pass',observation.get('report_passed') is True and observation.get('all_gates_passed') is True)
   c.equal(label+':observed-gates',observation.get('gates'),count)
   c.equal(label+':minimum',observation.get('minimum_gates'),minimum)
   if label!='independent-replay':c.equal(label+':source',report.get('source_git_commit'),source)
  original=self.reports['original-correctness'];native=self.reports['native-correctness'];replay=self.reports['independent-replay'];bench=self.reports['native-economics']
  for report,label in ((original,'original'),(native,'native')):
   for field,tool in (('checker_sha256','check-selected'),('full_checker_sha256','sokonanoda'),('indexer_sha256','export-index')):
    c.equal(label+':final-binary:'+tool,report[field],self.binaries[tool])
   c.equal(label+':engine-source',report['adapter_sha256'],sha(self.source('experiments/incremental/engine.py')))
   c.equal(label+':pins',report['pins'],strict_json(self.source('experiments/incremental/pins.json')))
  for report,key in ((original,'harness_sources_sha256'),(native,'source_sha256'),(bench,'harness_sources_sha256')):
   c.need('nonempty-harness-source-map:'+key,bool(report.get(key)))
   for name,identity in report[key].items():c.equal('harness-source:'+name,identity,
      sha(self.source('experiments/incremental/'+name)))
  c.equal('native:original-report-link',native['original_qualification']['summary_sha256'],sha(self.raw['original-correctness']))
  c.equal('replay:original-report-link',replay['qualification_summary_sha256'],sha(self.raw['original-correctness']))
  c.equal('replay:source',replay['replay_source_sha256'],sha(self.source('experiments/incremental/replay_native.py')))
  for label,tool in (('rust','sokonanoda'),('indexer','export-index')):c.equal('replay:binary:'+tool,replay['binary_sha256'][label],self.binaries[tool])
  for label,tool in (('cpp','leanchecker'),('paranoid','leanchecker-paranoid')):c.equal('replay:official:'+tool,
      replay['binary_sha256'][label],original['pins']['lean_release_binaries_sha256'][tool])
  for label,tool in (('current-check-selected','check-selected'),('current-sokonanoda','sokonanoda'),('export-index','export-index')):
   c.equal('benchmark:binary:'+tool,bench['captured_tools'][label]['sha256'],self.binaries[tool])
  c.equal('benchmark:source-engine',bench['current_engine_snapshot']['sha256'],original['adapter_sha256'])
  self.findings['retained_original_suites']={label:len(self.reports[label]['gates']) for label in OLD}
  self.findings['native_adapter_economic_status']=bench['economic_status']
  for label,log,flag in (('original-correctness','original-qualification.log','qualification_passed'),
      ('native-correctness','native-qualification.log','correctness_passed'),
      ('independent-replay','native-independent-replay.log','passed'),
      ('native-economics','native-benchmark.log','correctness_passed')):
   rows=[]
   for line in self.member(log).decode().splitlines():
    try:value=strict_json(line)
    except (ValueError,TypeError):continue
    if type(value) is dict and flag in value:rows.append(value)
   c.need(label+':actual-log-summary',bool(rows) and rows[-1][flag] is True)
   c.need(label+':log-no-failed-gates',not rows[-1].get('failed_gates',[]) and not rows[-1].get('failures',[]))
 def run(self):
  c=self.checks
  try:
   metadata=strict_json(self.args.metadata.read_bytes())
   if 'artifact' in metadata:metadata=metadata['artifact']
   c.equal('transport:source',metadata['workflow_run']['head_sha'],self.args.source)
   c.equal('transport:name',metadata['name'],'incremental-producer-delta-summaries-'+self.args.source)
   raw=self.args.zip.read_bytes();c.equal('transport:size',metadata['size_in_bytes'],len(raw))
   c.equal('transport:digest',metadata['digest'],'sha256:'+sha(raw))
   self.findings['archive']=dict(bytes=len(raw),sha256=sha(raw),artifact_id=metadata.get('id'))
   with zipfile.ZipFile(self.args.zip) as archive:
    self.archive=archive;self.names=[];total=0
    for member in archive.infolist():
     path=PurePosixPath(member.filename);parts=path.parts
     c.need('transport:safe-member:'+member.filename,not path.is_absolute() and '..' not in parts and
        '\\' not in member.filename and ':' not in (parts[0] if parts else '') and
        member.filename not in self.names and not stat.S_ISLNK(member.external_attr>>16) and
        not member.flag_bits&1 and not member.filename.endswith('.key'))
     self.names.append(member.filename);total+=member.file_size
    c.need('transport:compact-bound',total<=512*(1<<20))
    c.need('transport:CRCs',archive.testzip() is None)
    self.load('observations','ci-observations.json');self.check_sources()
    results={}
    for label,(directory,profile,count) in PROFILES.items():
     summary=self.load(label,directory+'/summary.json')
     phase=self.load(label+'-phases',directory+'/compact-phases.json')
     observation=self.reports['observations']['reports'][label]
     c.equal(label+':exact-profile',summary['profile'],profile)
     c.equal(label+':source',summary['source_git_commit'],self.args.source)
     c.equal(label+':publisher-summary-digest',observation['summary_sha256'],sha(self.raw[label]))
     c.equal(label+':publisher-phase-digest',observation['compact_phases']['sha256'],sha(self.raw[label+'-phases']))
     c.equal(label+':publisher-sample-count',observation['compact_phases']['samples'],len(phase['samples']))
     c.equal(label+':publisher-cold-count',observation['compact_phases']['cold_samples'],1)
     c.need(label+':publisher-qualified',observation['report_passed'] is True and observation['qualification_status']=='PASS')
     c.equal(label+':harness-source',summary['harness_sha256'],sha(self.source('experiments/incremental/qualify_delta.py')))
     for key,tool in (('producer','delta-producer'),('checker','check-selected'),('full_checker','sokonanoda'),('indexer','export-index'),('index_session','index-session')):
      c.equal(label+':frozen-binary:'+tool,summary['tools'][key]['sha256'],self.binaries[tool])
     results[label]=phase_review(phase,summary,self.args.source,self.raw[label],c)
     for name in ('delta-qualification.log' if label=='producer-delta' else 'delta-expanded-qualification.log',):
      lines=[strict_json(line) for line in self.member(name).decode().splitlines() if line.startswith('{') and 'qualification_status' in line]
      c.need(label+':actual-log-qualified',bool(lines) and lines[-1].get('qualification_status')=='PASS' and lines[-1].get('correctness_passed') is True)
    self.findings['phase_profiles']=results
    c.equal('publisher:report-universe',sorted(self.reports['observations']['reports']),sorted((*OLD,*PROFILES)))
    wanted=[label for label in ('producer-delta-expanded','producer-delta') if
      self.reports[label]['economic_status']=='SPEEDUP' and self.reports[label]['economics']['early-definition']['passed'] is True]
    c.equal('publisher:qualified-profile-list',self.reports['observations']['qualified_speedup_profiles'],wanted)
  except Exception as error:
   c.failures.append(type(error).__name__+': '+str(error))
  return dict(schema='mathgraph.producer-delta-compact-phase-independent-review.v1',
      passed=not c.failures,status='PASS_WITH_STATED_LIMITS' if not c.failures else 'FAIL_CLOSED',
      check_count=c.count,failures=c.failures,reviewer_sha256=sha(Path(__file__).read_bytes()),
      expected_source=self.args.source,findings=self.findings,
      limits=['No kernel execution or historical issuer HMAC reauthentication.',
       'Supplement to the frozen summary/economic reviewer, not a replacement for its qualification and bootstrap checks.',
       'No omitted full sample result JSON was read; result digests are frozen publisher projections.',
       'Phase CPU includes the recorded live-daemon procfs tick method with SC_CLK_TCK granularity.',
       MEMORY_SCOPE,'Warm timings exclude constructor, imported baseline and initial full verification.',
       'Full baseline hashing, SCC/declaration reclosure, full composite hashing/parsing and full receipt remain O(total).'])


def self_test():
 checks=Checks()
 valid=dict(gates=[dict(name='gate'+str(i),passed=True) for i in range(719)],passed=True)
 gate_report(valid,719,'passed',checks,'valid-replay')
 falsifiers={}
 for name,mutate in [('missing-gates',lambda value:value.update(gates=[])),
     ('false-gate',lambda value:value['gates'][0].update(passed=False)),
     ('false-acceptance',lambda value:value.update(passed=False))]:
  value=copy.deepcopy(valid);mutate(value)
  try:gate_report(value,719,'passed',Checks(),name);falsifiers[name]=False
  except ValueError:falsifiers[name]=True
 # Exercise median/projection mechanics without importing the publisher/runtime.
 self_checks=Checks();derived=numeric_medians(self_checks,'median',[{'wall':1.0,'cpu':.5},{'wall':3.0,'cpu':2.0},{'wall':2.0,'cpu':1.0}])
 assert derived=={'cpu':1.0,'wall':2.0}
 for name,rows in [('missing-phase',[{'wall':1.0,'cpu':.5},{'wall':2.0}]),
                   ('nonfinite-phase',[{'wall':float('nan')}])]:
  try:numeric_medians(Checks(),name,rows);falsifiers[name]=False
  except ValueError:falsifiers[name]=True
 assert collapse_roots({'roots':['a','b']})=={'roots':{'count':2,'canonical_sha256':sha(canonical(['a','b']))}}
 source='4'*40
 timings=dict(producer_seconds=.1,baseline_validation_seconds=.1,identity_update_seconds=.1,
   materialization_and_hash_seconds=.1,checking_seconds=.1,persistence_seconds=.1,
   consumer_seconds=.6,consumer_cpu_seconds=.3,baseline_validation_cpu_seconds=.05,
   identity_update_cpu_seconds=.05,materialization_and_hash_cpu_seconds=.05,
   checking_cpu_seconds=.05,persistence_cpu_seconds=.05,end_to_end_seconds=.8,end_to_end_cpu_seconds=.4)
 samples=[];main=[]
 for variant in VARIANTS:
  for repetition in range(5):
   changed=[] if variant=='baseline' else ['local.changed'];checked=int(bool(changed));identity='a'*64
   original=dict(variant=variant,repetition=repetition,cold_replay=False,apply_wall_seconds=1.,direct_wall_seconds=2.,
      session_constructor_wall_seconds=1.,start_wall_seconds=3.,setup_wall_seconds=4.,
      direct_rust=dict(completed_child_cpu_seconds=1.5),baseline_result=dict(status='VERIFIED'),
      evidence_id=identity,result_path=f'/samples/{variant}-{repetition}/result.json',
      setup_report=dict(cpu_seconds=2.5,roots=['root.a','root.b']),
      snapshot=dict(sha256=identity,bytes=1024),
      partition_audit=dict(actual_kernel_checked=checked,independently_replayed_reused=3436-checked),
      persisted_acceptance_audit=dict(delta_bytes=16 if changed else 0))
   row={key:copy.deepcopy(value) for key,value in original.items() if key not in
        ('snapshot','partition_audit','persisted_acceptance_audit')}
   row.update(setup_report=collapse_roots(original['setup_report']),result_sha256='b'*64,export_sha256=identity,
      cpu_measurement=CPU_SCOPE,counts=dict(total=3436,scheduled=checked,rechecked=checked,reused=3436-checked,invalidated=checked),
      checker_result=dict(code=0,stdout=json.dumps(dict(checked=checked,total_declarations=3436,
          scope='selected_obligations_under_caller_trusted_environment')),stderr=''),
      representation=dict(delta_bytes=16 if changed else 0,export_bytes=1024,full_export_disk_bytes_written=0,immutable_memfd=True),
      producer_report=dict(status='delta',changed_names=changed,stats=dict(compared_local_constants=7,
          imported_identity_retained=True,unchanged_local_constants=7-checked,new_exprs=checked,new_levels=0,new_names=0)),
      typed_update=dict(status='indexed',replaced_names=changed,rows_processed=checked,dag_rows=checked),
      timings=copy.deepcopy(timings),memory={stage:dict(scope=PROCESS_SCOPE,processes={
          process:dict(VmHWM=16,VmRSS=8,RssAnon=4,RssFile=4) for process in ('adapter','index','producer')}) for stage in PHASES})
   samples.append(row);main.append(original)
 cold=copy.deepcopy(samples[0]);cold.update(cold_replay=True,repetition='cold-restart');cold['memory']['producer']=None;samples.append(cold)
 cold_main=copy.deepcopy(main[0]);cold_main.update(cold_replay=True,repetition='cold-restart');main.append(cold_main)
 summary=dict(run_completed=True,correctness_passed=True,qualification_status='PASS',repetitions=5,
    harness_sha256='c'*64,profile='original-qualified-3436',host={'host':'fixture'},measurement_policy={'scope':'fixture'},samples=main)
 summary_raw=canonical(summary)
 observed=dict(apply_wall_seconds=1.,direct_wall_seconds=2.,direct_completed_child_cpu_seconds=1.5,
    session_constructor_wall_seconds=1.,start_wall_seconds=3.,setup_wall_seconds=4.,start_report_cpu_seconds=2.5)
 phase=dict(schema='mathgraph.producer-delta-compact-phases.v1',source_sha=source,profile=summary['profile'],
    summary_sha256=sha(summary_raw),harness_sha256=summary['harness_sha256'],host=summary['host'],
    measurement_policy=summary['measurement_policy'],memory_scope=MEMORY_SCOPE,samples=samples,
    warm_medians_by_variant={variant:dict(sample_count=5,timings=copy.deepcopy(timings),observed_wall_and_cpu=observed) for variant in VARIANTS})
 phase_review(phase,summary,source,summary_raw,Checks())
 for name,mutate in [
    ('missing-phase-sample',lambda value:value['samples'].pop()),
    ('wrong-phase-source',lambda value:value.update(source_sha='0'*40)),
    ('wrong-export-root',lambda value:value['samples'][0].update(export_sha256='0'*64)),
    ('forged-checker-count',lambda value:value['samples'][0]['checker_result'].update(stdout=json.dumps(dict(checked=2,total_declarations=3436,scope='selected_obligations_under_caller_trusted_environment')))),
    ('changed-direct-cpu',lambda value:value['samples'][0]['direct_rust'].update(completed_child_cpu_seconds=99.)),
    ('false-phase-median',lambda value:value['warm_medians_by_variant']['early-definition']['timings'].update(identity_update_seconds=99.)),
    ('false-memory-peak',lambda value:value['samples'][0]['memory']['identity'].update(scope='exact phase peak memory')),
    ('missing-phase-cpu',lambda value:value['samples'][0]['timings'].pop('identity_update_cpu_seconds'))]:
  value=copy.deepcopy(phase);mutate(value)
  try:phase_review(value,summary,source,summary_raw,Checks());falsifiers[name]=False
  except (ValueError,KeyError,TypeError):falsifiers[name]=True
 assert all(falsifiers.values())
 return dict(status='PASS_HELPER_SELF_TEST',scope='report gate and median/projection mechanics only',falsifiers=falsifiers)


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--self-test',action='store_true')
 parser.add_argument('--zip',type=Path);parser.add_argument('--metadata',type=Path)
 parser.add_argument('--repo',type=Path);parser.add_argument('--source');parser.add_argument('--out',type=Path)
 args=parser.parse_args()
 if args.self_test:print(json.dumps(self_test()));return 0
 for field in ('zip','metadata','repo','source','out'):
  if getattr(args,field) is None:parser.error('--'+field+' is required')
 result=ArchiveReview(args).run();args.out.parent.mkdir(parents=True,exist_ok=True)
 args.out.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({key:result[key] for key in ('status','passed','check_count','failures')}))
 return 0 if result['passed'] else 1


if __name__=='__main__':sys.exit(main())
