#!/usr/bin/env python3
"""Independent, read-only review of the compact native CI ZIP and Git source.

No producer Python modules are imported or executed. No kernels run, archives
are not extracted, and old issuer secrets/HMACs are not independently verified.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import random
import re
import stat
import statistics
import subprocess
import zipfile

EXPECTED_SOURCE = 'c5ab12699338aa57b7e9d48b15d4a7409e453c7b'
BASELINE = '9ac04033b51703fb135ec3c28621d44b183944fe'
MATHGRAPH = 'cf359686c74549a132c7a651cd7aabc7c1a870fe'
REPORTS = {'original-correctness': ('original-qualification/summary.json',197,'qualification_passed'),
           'native-correctness': ('native-qualification/summary.json',335,'qualification_passed'),
           'independent-replay': ('native-independent-replay/summary.json',719,'passed'),
           'native-economics': ('native-benchmark/summary.json',251,'correctness_passed')}
VARIANTS = ('baseline','early-definition','unrelated-definition','theorem-leaf','invalid-proof','axiom-type')
ARMS = ('baseline-python-full','baseline-python-incremental','native-full','native-incremental','baseline-direct-full','current-direct-full')
MEMORY_CASES = {'unchanged': ('baseline',0,3436), 'early': ('early-definition',413,3023),
                'unrelated': ('unrelated-definition',1,3435), 'leaf': ('theorem-leaf',1,3435),
                'invalid': ('invalid-proof',None,3435)}
HEX = re.compile(r'^[0-9a-f]{64}$')


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('duplicate JSON key: '+key)
            result[key]=value
        return result
    def constant(value): raise ValueError('nonfinite JSON number: '+value)
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)


class Incomplete(Exception): pass


class Review:
    def __init__(self,args):
        self.args=args;self.checks=[];self.raw={};self.reports={};self.summary={}

    def check(self,name,passed,**details):
        self.checks.append(dict(name=name,passed=bool(passed),**details))
        return bool(passed)

    def need(self,name,passed,**details):
        if not self.check(name,passed,**details):raise Incomplete(name)

    def equal(self,name,left,right):
        self.check(name,canonical(left)==canonical(right))

    def near(self,name,left,right):
        valid=lambda value:type(value) in (float,int) and math.isfinite(value)
        self.check(name,valid(left) and valid(right) and math.isclose(left,right,rel_tol=1e-11,abs_tol=1e-10))

    def section(self,name,function):
        try:function()
        except (Incomplete,KeyError,ValueError,TypeError,IndexError,OSError,zipfile.BadZipFile,subprocess.CalledProcessError) as error:
            self.check(name+':complete',False,error=type(error).__name__+': '+str(error))

    def git(self,path):
        return subprocess.check_output(['git','-C',str(self.args.repo),'show',self.args.source+':'+path],stderr=subprocess.PIPE)

    def source_hashes(self,name,mapping,expected=None):
        self.need(name+':nonempty',type(mapping) is dict and bool(mapping))
        if expected is not None:self.equal(name+':file-set',sorted(mapping),sorted(expected))
        for filename,actual in mapping.items():
            self.need(name+':safe-source-name:'+filename,Path(filename).name==filename and filename.endswith('.py'))
            self.equal(name+':'+filename,actual,digest(self.git('experiments/incremental/'+filename)))

    def transport(self):
        metadata=strict_json(self.args.artifact_metadata.read_bytes())
        if 'artifact' in metadata:metadata=metadata['artifact']
        self.need('artifact-metadata-object',type(metadata) is dict)
        self.need('provider-digest-present',bool(re.fullmatch(r'sha256:[0-9a-f]{64}',metadata.get('digest',''))))
        size=self.args.zip.stat().st_size
        sha=hashlib.sha256()
        with self.args.zip.open('rb') as stream:
            for block in iter(lambda:stream.read(1<<20),b''):sha.update(block)
        self.need('provider-ZIP-size',type(metadata.get('size_in_bytes')) is int and metadata['size_in_bytes']==size)
        self.need('provider-ZIP-sha256',metadata['digest']=='sha256:'+sha.hexdigest())
        self.equal('provider-artifact-source',metadata['workflow_run']['head_sha'],self.args.source)
        self.equal('provider-artifact-name',metadata['name'],'incremental-native-index-summaries-'+self.args.source)
        self.summary['archive']=dict(path=str(self.args.zip),bytes=size,sha256=sha.hexdigest(),
            artifact_id=metadata.get('id'),artifact_name=metadata['name'],provider_digest=metadata['digest'])
        self.archive=zipfile.ZipFile(self.args.zip)
        names=set();total=0
        for item in self.archive.infolist():
            parts=item.filename.split('/')
            safe=(not item.filename.startswith('/') and '\\' not in item.filename
                and all(part not in ('.','..') for part in parts)
                and all(part!='' for part in (parts[:-1] if item.is_dir() else parts))
                and ':' not in parts[0] and '\x00' not in item.filename)
            self.need('safe-ZIP-member:'+item.filename,safe)
            self.need('unique-ZIP-member:'+item.filename,item.filename not in names)
            names.add(item.filename);total+=item.file_size
            self.need('regular-unencrypted-ZIP-member:'+item.filename,
                not stat.S_ISLNK(item.external_attr>>16) and not item.flag_bits&1)
            self.need('no-issuer-key-file:'+item.filename,not item.filename.endswith('.key'))
        self.need('bounded-compact-archive',total<=256*(1<<20))
        self.need('all-ZIP-CRCs',self.archive.testzip() is None)
        self.members=names
        self.summary['archive'].update(member_count=len(names),uncompressed_bytes=total)
        for label,(suffix,_,_) in REPORTS.items():self.load(label,suffix)
        self.load('observations','ci-observations.json')
        self.load('integration','mathgraph-integration/summary.json')
        self.load('memory','native-phase-memory/summary.json')

    def load(self,label,suffix):
        names=[name for name in self.members if name==suffix or name.endswith('/'+suffix)]
        self.need('one-required-member:'+suffix,len(names)==1)
        raw=self.archive.read(names[0]);self.need('nonempty-report:'+label,bool(raw.strip()))
        self.raw[label]=raw;self.reports[label]=strict_json(raw)

    def sources(self):
        self.need('expected-repaired-source',self.args.source==EXPECTED_SOURCE)
        self.equal('Git-source-resolves',subprocess.check_output(['git','-C',str(self.args.repo),'rev-parse',self.args.source+'^{commit}'],text=True).strip(),self.args.source)
        self.pins=strict_json(self.git('experiments/incremental/pins.json'))
        self.reference=strict_json(self.git('experiments/incremental/results/local-qualified.json'))
        observation=self.reports['observations']
        self.equal('observations-source',observation['source_sha'],self.args.source)
        self.equal('observations-failures',observation['failures'],[])
        self.equal('observations-four-report-labels',sorted(observation['reports']),sorted(REPORTS))
        for label,(path,count,flag) in REPORTS.items():
            report=self.reports[label];obs=observation['reports'][label]
            schema={'original-correctness':'mathgraph.incremental-qualification.v1',
                'native-correctness':'mathgraph.incremental-native-qualification.v1',
                'independent-replay':'mathgraph.native-independent-review.v1',
                'native-economics':'mathgraph.incremental-native-benchmark.v1'}[label]
            self.equal(label+':schema',report['schema'],schema)
            self.equal(label+':observed-content-hash',obs['summary_sha256'],digest(self.raw[label]))
            self.equal(label+':observed-source',obs['source_sha'],self.args.source)
            self.equal(label+':observed-count',obs['gates'],count)
            self.check(label+':observation-pass-flags',obs['all_gates_passed'] is True and obs['report_passed'] is True)
            gates=report['gates']
            self.need(label+':nonempty-exact-gates',type(gates) is list and len(gates)==count)
            self.check(label+':strict-gates-pass',all(type(g) is dict and g.get('passed') is True for g in gates))
            self.check(label+':unique-gate-names',len({g['name'] for g in gates})==count)
            self.check(label+':top-acceptance-flag',report.get(flag) is True)
            if label!='independent-replay':self.equal(label+':source',report['source_git_commit'],self.args.source)
        original=self.reports['original-correctness'];native=self.reports['native-correctness'];bench=self.reports['native-economics'];replay=self.reports['independent-replay']
        self.check('native-correctness-top-flag',native['correctness_passed'] is True)
        for label in ('original-correctness','native-correctness','native-economics'):
            self.equal(label+':full-qualified-pins',self.reports[label]['pins'],self.pins)
        self.equal('original-197-gate-name-order',[g['name'] for g in original['gates']],[g['name'] for g in self.reference['gates']])
        self.equal('original-native-backend',original['identity_backend'],'native')
        files=subprocess.check_output(['git','-C',str(self.args.repo),'ls-tree','--name-only',self.args.source+':experiments/incremental'],text=True).splitlines()
        self.source_hashes('original-source',original['harness_sources_sha256'],[f for f in files if f.endswith('.py')])
        self.source_hashes('native-source',native['source_sha256'],('engine.py','qualify.py','process.py','test_predicate.py','qualify_native.py'))
        self.source_hashes('benchmark-source',bench['harness_sources_sha256'],('benchmark_native.py','qualify_native.py','process.py','engine.py'))
        engine=digest(self.git('experiments/incremental/engine.py'))
        self.equal('original-engine-source',original['adapter_sha256'],engine)
        self.equal('native-engine-source',native['adapter_sha256'],engine)
        self.equal('native-harness-source',native['harness_sha256'],digest(self.git('experiments/incremental/qualify_native.py')))
        self.equal('replay-source',replay['replay_source_sha256'],digest(self.git('experiments/incremental/replay_native.py')))
        self.equal('replay-committed-reference-bytes',replay['reference_summary_sha256'],digest(self.git('experiments/incremental/results/local-qualified.json')))
        self.equal('native-original-summary',native['original_qualification']['summary_sha256'],digest(self.raw['original-correctness']))
        self.check('native-original-summary-pass',native['original_qualification']['passed'] is True and native['original_qualification']['gates']==197)
        self.equal('replay-original-summary',replay['qualification_summary_sha256'],digest(self.raw['original-correctness']))
        manifest=original['workload_manifest_sha256']
        for label in ('native-correctness','native-economics','memory'):
            self.equal(label+':manifest-cross-pin',self.reports[label]['workload_manifest_sha256'],manifest)
        for field in ('checker_sha256','full_checker_sha256','indexer_sha256'):
            self.equal('native:'+field,native[field],original[field])
        self.equal('benchmark-engine-snapshot',bench['current_engine_snapshot']['sha256'],engine)
        self.equal('benchmark-baseline-ref',bench['baseline_ref'],BASELINE)
        self.equal('benchmark-baseline-engine-source',bench['baseline_source_sha256'],digest(subprocess.check_output(['git','-C',str(self.args.repo),'show',BASELINE+':experiments/incremental/engine.py'])))
        for name,field in [('current-check-selected','checker_sha256'),('current-sokonanoda','full_checker_sha256'),('export-index','indexer_sha256')]:
            self.equal('benchmark-current-binary-cross-pin:'+name,bench['captured_tools'][name]['sha256'],original[field])
        for name,field in [('rust','full_checker_sha256'),('indexer','indexer_sha256')]:
            self.equal('replay-current-binary-cross-pin:'+name,replay['binary_sha256'][name],original[field])
        for name,release in [('cpp','leanchecker'),('paranoid','leanchecker-paranoid')]:
            self.equal('replay-release-binary-pin:'+name,replay['binary_sha256'][name],self.pins['lean_release_binaries_sha256'][release])
        self.summary['source']=dict(commit=self.args.source,engine_sha256=engine,replay_sha256=replay['replay_source_sha256'],
            pins_sha256=digest(self.git('experiments/incremental/pins.json')),manifest_sha256=manifest,
            reported_binary_sha256={k:original[k] for k in ('checker_sha256','full_checker_sha256','indexer_sha256')})

    def process(self,name,record,code):
        self.check(name+':actual-process',record.get('returncode')==code and type(record.get('returncode')) is int and record.get('timed_out') is False)
        for metric in ('wall_seconds','cpu_seconds','max_rss_kib'):
            value=record[metric]
            self.check(name+':nonnegative-'+metric,type(value) in (int,float) and math.isfinite(value) and value>=0)

    def oracles(self):
        original=self.reports['original-correctness'];replay=self.reports['independent-replay'];native=self.reports['native-correctness']
        self.equal('original-oracle-variant-set',sorted(original['oracles']),sorted(self.pins['export_sha256']))
        rejects={'invalid-proof','axiom-type','malformed-unused-dag','malformed-unused-typed-node'}
        for variant,tools in original['oracles'].items():
            self.equal('original-two-oracles:'+variant,sorted(tools),['leanchecker','leanchecker-paranoid'])
            for tool,value in tools.items():
                negative=variant in rejects;status='REJECT' if negative else 'ACCEPT'
                self.equal('original-oracle-status:'+variant+':'+tool,[value['status'],value['expected']],[status,status])
                self.equal('original-oracle-export:'+variant+':'+tool,value['export_sha256'],self.pins['export_sha256'][variant])
                self.process('original-oracle:'+variant+':'+tool,value['resources'],1 if negative else 0)
        direct_variants={'baseline','early-definition','unrelated-definition','theorem-leaf','invalid-proof','axiom-type','malformed-unused-typed-node'}
        self.equal('replay-seven-direct-variants',sorted(replay['direct']),sorted(direct_variants))
        direct_count=0
        for variant,tools in replay['direct'].items():
            self.equal('replay-three-kernels:'+variant,sorted(tools),['cpp','paranoid','rust'])
            code=1 if variant in rejects else 0
            for tool,value in tools.items():
                direct_count+=1;self.process('fresh-replay:'+variant+':'+tool,value['record'],code)
                self.equal('fresh-replay-binary:'+variant+':'+tool,value['binary_sha256'],replay['binary_sha256'][tool])
                self.equal('fresh-replay-export:'+variant+':'+tool,value['export_sha256'],self.pins['export_sha256'][variant])
            comparison=replay['comparisons'][variant];status='REJECTED' if code else 'VERIFIED'
            self.equal('replay-comparison-expected:'+variant,[comparison['direct_expected_exit'],comparison['native_backend_expected_status']],[code,status])
            self.check('replay-comparison-actual:'+variant,bool(comparison['native_backend_statuses']) and all(s==status for s in comparison['native_backend_statuses']))
        self.equal('replay-invocation-count',replay['invocation_count'],72)
        self.equal('replay-evidence-record-count',replay['unique_evidence_record_paths_checked'],35)
        self.equal('replay-distinct-record-list',len({e['record'] for e in replay['evidence']}),35)
        indexes=native['indexes'];self.equal('index-case-count',len(indexes),82)
        for variant,expected in self.pins['export_sha256'].items():self.equal('native-pinned-export:'+variant,indexes[variant]['export_sha256'],expected)
        self.equal('exact-native-supported-count',sum(v['index_equal'] is True for v in indexes.values()),45)
        self.equal('explicit-fallback-count',sum(v['python_fallback_required'] is True for v in indexes.values()),17)
        self.equal('both-index-refusal-count',sum(not v['python']['indexed'] and not v['native']['indexed'] for v in indexes.values()),20)
        self.check('index-case-pass-flags',all(v['passed'] is True for v in indexes.values()))
        self.summary['fresh_oracle_processes']=direct_count

    def benchmark(self):
        b=self.reports['native-economics'];self.equal('benchmark-variants',b['variants'],list(VARIANTS));self.equal('benchmark-arms',b['arms'],list(ARMS))
        self.equal('benchmark-five-repetitions',b['repetitions'],5);samples=b['samples'];self.need('benchmark-180-samples',len(samples)==180)
        by={};resources_checked=phases_checked=0
        for sample in samples:
            variant,arm,repeat=sample['variant'],sample['arm'],sample['repetition'];key=(variant,arm,repeat)
            self.need('benchmark-unique-sample:'+str(key),key not in by and variant in VARIANTS and arm in ARMS and type(repeat) is int and 0<=repeat<5)
            by[key]=sample;negative=variant in ('invalid-proof','axiom-type');status='REJECTED' if negative else 'VERIFIED'
            self.check('benchmark-protocol:'+str(key),sample['protocol_valid'] is True and sample['status']==sample['expected']==status)
            self.process('benchmark-process:'+str(key),sample['resources'],1 if negative else 0)
            if 'direct-full' not in arm:
                count=sample['counts'];incremental=arm.endswith('incremental')
                selected={'baseline':0,'early-definition':413,'unrelated-definition':1,'theorem-leaf':1,'invalid-proof':1,'axiom-type':3436}[variant] if incremental else 3436
                self.equal('benchmark-counts:'+str(key),[count['total'],count['scheduled'],count['reused'],count['rechecked']],
                    [3436,selected,3436-selected,None if negative else selected])
                self.check('benchmark-evidence:'+str(key),sample['evidence_id'] is None if negative else isinstance(sample['evidence_id'],str) and HEX.fullmatch(sample['evidence_id']) is not None)
        for variant in VARIANTS:
            for arm in ARMS:
                group=[by[(variant,arm,i)] for i in range(5)];median=b['medians'][variant][arm]
                self.equal('benchmark-status-list:'+variant+':'+arm,median['statuses'],[v['status'] for v in group])
                self.equal('benchmark-median-repetitions:'+variant+':'+arm,median['repetitions'],5)
                for metric in ('wall_seconds','cpu_seconds','max_rss_kib'):
                    resources_checked+=1;self.near('benchmark-median:'+variant+':'+arm+':'+metric,statistics.median(v['resources'][metric] for v in group),median['resources'][metric])
                keys=set().union(*(v.get('phases',{}) for v in group))
                self.equal('benchmark-phase-key-set:'+variant+':'+arm,sorted(median['phases']),sorted(keys))
                for phase in keys:
                    phases_checked+=1;self.near('benchmark-phase-median:'+variant+':'+arm+':'+phase,statistics.median(v['phases'][phase] for v in group if phase in v.get('phases',{})),median['phases'][phase])
                construction=b['construction'][variant];summed=construction['construction_sum']
                for metric in ('wall_seconds','cpu_seconds'):
                    self.near('benchmark-construction-sum:'+variant+':'+arm+':'+metric,b['component_addition_totals'][variant][arm][metric],summed[metric]+median['resources'][metric])
                    export=construction['processes'].get('export_process');actual=b['export_plus_verification_subtotals'][variant][arm][metric]
                    if export:self.near('benchmark-export-sum:'+variant+':'+arm+':'+metric,actual,export[metric]+median['resources'][metric])
                    else:self.equal('benchmark-no-export-sum:'+variant+':'+arm+':'+metric,actual,None)
            for repeat in range(5):
                for mode in ('full','incremental'):
                    self.equal('benchmark-decision-projection:'+variant+':'+str(repeat)+':'+mode,by[(variant,'baseline-python-'+mode,repeat)]['projection_sha256'],by[(variant,'native-'+mode,repeat)]['projection_sha256'])
        recomputed={}
        for offset,variant in enumerate(('early-definition','unrelated-definition')):
            self.equal('observations-primary-resources:'+variant,
                self.reports['observations']['reports']['native-economics']['primary'][variant],
                {arm:data['resources'] for arm,data in b['medians'][variant].items()})
            pairs=[]
            for repeat in range(5):
                native,direct=(by[(variant,arm,repeat)] for arm in ('native-incremental','current-direct-full'))
                pairs.append(dict(repetition=repeat,native_wall_seconds=native['resources']['wall_seconds'],direct_wall_seconds=direct['resources']['wall_seconds'],native_position=native['position'],direct_position=direct['position']))
            e=b['economics'][variant];self.equal('benchmark-paired-inputs:'+variant,e['pairs'],pairs)
            native=[v['native_wall_seconds'] for v in pairs];direct=[v['direct_wall_seconds'] for v in pairs]
            ratio=statistics.median(native)/statistics.median(direct);wins=sum(a<c for a,c in zip(native,direct));rng=random.Random(20261016+offset);ratios=[]
            for _ in range(10000):
                indices=[rng.randrange(5) for _ in range(5)]
                ratios.append(statistics.median(native[i] for i in indices)/statistics.median(direct[i] for i in indices))
            ratios.sort();interval=[ratios[int(.025*9999)],ratios[int(.975*9999)]]
            expected=dict(native_median_wall_seconds=statistics.median(native),direct_median_wall_seconds=statistics.median(direct),median_ratio=ratio,
                paired_wins=wins,paired_count=5,bootstrap_ratio_interval_95=interval,bootstrap_repetitions=10000,bootstrap_seed=20261016+offset,
                median_lower=ratio<1,paired_majority=wins>2.5,bootstrap_upper_lower=interval[1]<1,passed=ratio<1 and wins>2.5 and interval[1]<1)
            for field,value in expected.items():self.equal('benchmark-recomputed-economics:'+variant+':'+field,e[field],value)
            recomputed[variant]=expected
        economic_pass=all(e['passed'] for e in recomputed.values())
        self.equal('benchmark-economic-result',b['economic_passed'],economic_pass)
        self.equal('benchmark-economic-status',b['economic_status'],'SPEEDUP' if economic_pass else 'NO_SPEEDUP')
        self.equal('benchmark-overall-status',b['status'],b['economic_status'])
        self.equal('observed-economic-status',self.reports['observations']['reports']['native-economics']['economic_status'],b['economic_status'])
        self.summary['benchmark']=dict(samples=len(samples),resource_medians_checked=resources_checked,phase_medians_checked=phases_checked,economic_passed=economic_pass,economic_status=b['economic_status'],primary=recomputed)

    def integration(self):
        r=self.reports['integration'];original=self.reports['original-correctness'];a=r['admission'];early=original['scenarios']['early-definition']['runs'][0]['incremental'];v=early['result']
        self.equal('integration-schema',r['schema'],'mathgraph.incremental-lean.mathgraph-integration-qualification.v1')
        self.check('integration-top-pass',r['qualification_passed'] is True and r['status']=='QUALIFIED_BOUNDED_EXISTING_MATHGRAPH_IMPORT' and r['action_authorization']=='NONE' and r['production_check_binder'] is False)
        self.equal('integration-original-content-hash',r['source_qualification']['sha256'],digest(self.raw['original-correctness']))
        self.equal('integration-MathGraph-pin',r['mathgraph_commit'],MATHGRAPH)
        committed=strict_json(self.git('experiments/incremental/results/local-mathgraph-integration.json'))
        self.equal('integration-resolver-source-pin',r['resolver_source_sha256'],committed['resolver_source_sha256'])
        for field,expected in [('result_sha256',early['result_sha256']),('expected_evidence_id',v['evidence_id']),('expected_export_sha256',self.pins['export_sha256']['early-definition']),('qualification_gates',197),('oracle_sources',['leanchecker','leanchecker-paranoid'])]:self.equal('integration-admission:'+field,a[field],expected)
        self.check('integration-no-new-authority',a['engine_hmac_checked_in_this_consumer'] is False)
        expected={'qualified-import':(0,None),'changed-bytes-same-evidence-id':(2,'QUALIFIED_RESULT_BYTES_CHANGED'),'wrong-export-root':(2,'EXPORT_PIN_MISMATCH'),'wrong-evidence-root':(2,'EVIDENCE_PIN_MISMATCH'),'unknown-result':(2,'ENGINE_RESULT_NOT_QUALIFIED')}
        cases={x['name']:x for x in r['cases']};self.need('integration-exact-five-cases',len(r['cases'])==5 and set(cases)==set(expected))
        for name,(code,error) in expected.items():
            case=cases[name];result=case['result'];self.process('integration-process:'+name,case['resources'],code)
            self.check('integration-case-pass:'+name,case['passed'] is True and result['action_authorization']=='NONE' and result['production_mathgraph_check_binder'] is False)
            self.equal('integration-result-schema:'+name,result['schema'],'mathgraph.incremental-lean.warrant-integration.v1')
            self.equal('integration-result-status:'+name,result['status'],'UNKNOWN' if error else 'WARRANTED_BOUNDED_CALLER_QUALIFIED_IMPORT')
            if error:self.equal('integration-expected-refusal:'+name,result['error'],error)
        positive=cases['qualified-import'];result=positive['result']
        self.equal('integration-admitted-bytes',positive['input_sha256'],a['result_sha256'])
        self.equal('integration-positive-resolver',result['mathgraph']['source_sha256'],r['resolver_source_sha256'])
        for field in ('result_sha256','expected_evidence_id','expected_export_sha256'):self.equal('integration-positive-pin:'+field,result['admission'][field],a[field])
        self.check('integration-consumer-trust-scope',result['admission']['result_byte_pin_supplied_externally'] is True and result['admission']['authentication_performed_here'] is False and result['admission']['original_lean_rerun'] is False)
        obligations=result['obligations'];self.need('integration-full-obligations-present',type(obligations) is list and len(obligations)==3436)
        environment=digest(canonical(v['provenance']));self.equal('integration-environment',result['environment_sha256'],environment)
        counts=Counter();names=set();claims=set();receipts=set()
        for number,o in enumerate(obligations):
            name='integration-obligation:'+str(number);w=o['dependency_witness'];new=o['native_status']=='VERIFIED_NEW';origin='CHECKED_THIS_RUN' if new else 'REUSED_PREVIOUS_EVIDENCE'
            evidence=a['expected_evidence_id'] if new else v['previous_evidence']
            self.check(name+':status-index',o['native_status'] in ('VERIFIED_NEW','VERIFIED_REUSED') and type(o['index']) is int and o['index']==number and o['origin']==origin and o['evidence_id']==evidence and o['warrant_state']=='WARRANTED_BOUNDED')
            self.check(name+':witness',set(w)=={'own','closure','direct'} and isinstance(w['own'],str) and HEX.fullmatch(w['own']) and isinstance(w['closure'],str) and HEX.fullmatch(w['closure']) and type(w['direct']) is list and all(isinstance(key,str) and HEX.fullmatch(key) for key in w['direct']))
            identity=digest(canonical({key:o[key] for key in ('name','index','dependency_witness')}));scope='lean-export:'+a['expected_export_sha256']+':environment:'+environment+':obligation:'+identity
            self.equal(name+':claim',o['claim_id'],'lean-obligation:'+identity);self.equal(name+':scope',o['scope'],scope)
            self.equal(name+':receipt',o['receipt_id'],'qualified-lean-receipt:'+digest(canonical([scope,evidence])))
            self.check(name+':unique',isinstance(o['name'],str) and bool(o['name']) and o['name'] not in names and o['claim_id'] not in claims and o['receipt_id'] not in receipts)
            names.add(o['name']);claims.add(o['claim_id']);receipts.add(o['receipt_id']);counts[o['native_status']]+=1
        self.equal('integration-obligation-counts',[counts['VERIFIED_NEW'],counts['VERIFIED_REUSED']],[413,3023])
        withdrawal=result['withdrawal'];victim=obligations[0];independent=obligations[1]
        for field,value in [('affected_claim',victim['claim_id']),('withdrawn_receipt',victim['receipt_id']),('independent_claim',independent['claim_id']),('dependent_claim','support-projection:'+victim['claim_id']),('affected_after','UNKNOWN'),('dependent_after','UNKNOWN'),('independent_after','WARRANTED_BOUNDED'),('descendant_basis','DECLARED_CONFORMANCE_SUPPORT_PROJECTION_NOT_LEAN_DEPENDENCY'),('source_withdrawal_observed',False)]:self.equal('integration-withdrawal:'+field,withdrawal[field],value)
        resolutions=withdrawal['resolutions'];self.equal('integration-withdrawal-complete-domain',sorted(resolutions),sorted(claims|{withdrawal['dependent_claim']}))
        for claim,value in resolutions.items():
            changed=claim in (withdrawal['affected_claim'],withdrawal['dependent_claim'])
            self.equal('integration-resolution:'+claim,[value['before'],value['after'],value['changed']],['WARRANTED_BOUNDED','STALE' if changed else 'WARRANTED_BOUNDED',changed])
        self.summary['integration']=dict(cases=5,obligations=3436,checked_origins=counts['VERIFIED_NEW'],reused_origins=counts['VERIFIED_REUSED'])

    def memory(self):
        m=self.reports['memory'];o=self.reports['original-correctness'];self.equal('memory-source',m['source_git_commit'],self.args.source)
        self.equal('memory-schema',m['schema'],'mathgraph.incremental-native-phase-memory.v1')
        self.equal('memory-diagnostic-only',m['measurement_use'],'MEMORY_DIAGNOSTIC_NOT_PERFORMANCE_ECONOMICS')
        self.equal('memory-profiling-source',m['profiling_tool_sha256'],digest(self.git('experiments/incremental/profile_native_phases.py')))
        self.equal('memory-pins-source',m['qualification_pins_sha256'],digest(self.git('experiments/incremental/pins.json')))
        for name,field in [('engine.py','adapter_sha256'),('check-selected','checker_sha256'),('export-index','indexer_sha256'),('parse-only-checker','full_checker_sha256')]:self.equal('memory-captured:'+name,m['captured_sha256'][name],o[field])
        self.equal('memory-manifest-capture',m['captured_sha256']['workload-manifest.json'],m['workload_manifest_sha256'])
        self.equal('memory-pins-capture',m['captured_sha256']['pins.json'],m['qualification_pins_sha256'])
        self.equal('memory-two-repetitions',m['repetitions'],2);self.equal('memory-five-cases',sorted(m['cases']),sorted(MEMORY_CASES))
        for name,(variant,checked,reused) in MEMORY_CASES.items():
            export=m['validated_exports'][name];self.equal('memory-export:'+name,[export['variant'],export['sha256'],export['matches_manifest'],export['matches_qualification_pin']],[variant,self.pins['export_sha256'][variant],True,True])
            self.check('memory-export-path:'+name,export['path'].endswith('/'+variant+'/export.ndjson'))
            runs=m['cases'][name];self.need('memory-two-runs:'+name,len(runs)==2)
            for index,run in enumerate(runs):
                label='memory:'+name+':'+str(index);code=1 if name=='invalid' else 0
                self.check(label+':status',run['status']==('REJECTED' if code else 'VERIFIED') and run['returncode']==code and run['classification_and_counts_validated'] is True)
                self.equal(label+':counts',[run['counts'][key] for key in ('total','rechecked','reused','scheduled','invalidated')],[3436,checked,reused,3436-reused,3436-reused])
                detail=run['memory'];self.equal(label+':nested-returncode',detail['returncode'],code)
                children=detail['subprocess_wait4'];self.equal(label+':child-role-set',sorted(child['role'] for child in children),[] if name=='unchanged' else ['check-selected','export-index'])
                for child in children:
                    expected=code if child['role']=='check-selected' else 0
                    self.check(label+':post-exec-child:'+child['role'],child['exitcode']==expected and child['confirmed_post_exec_sample_count']>0 and child['sampled_post_exec_hwm_peak_kib'] is not None)
                self.check(label+':sampling-flag',run['subprocess_sampling_complete'] is True)
        parse=m['separate_parse_only_observation'];self.check('memory-separate-parse-only-process',parse['returncode']==0 and parse['memory']['returncode']==0 and len(parse['memory']['subprocess_wait4'])==1 and parse['memory']['subprocess_wait4'][0]['role']=='parse-only-checker' and parse['memory']['subprocess_wait4'][0]['exitcode']==0)
        self.summary['memory']=dict(cases=5,runs=10,counts_validated=True,use='Separate sampled diagnostic; not economics or exact memory savings')

    def run(self):
        self.section('transport',self.transport)
        if len(self.reports)==7:
            self.section('sources',self.sources)
            if hasattr(self,'pins'):
                for name in ('oracles','benchmark','integration','memory'):self.section(name,getattr(self,name))
        failed=[item for item in self.checks if not item['passed']]
        result=dict(schema='mathgraph.native-ci-archive-independent-review.v1',passed=not failed and len(self.reports)==7,
            reviewer_sha256=digest(Path(__file__).read_bytes()),
            artifact_metadata_sha256=digest(self.args.artifact_metadata.read_bytes()),
            source_sha=self.args.source,check_count=len(self.checks),failed_count=len(failed),failures=failed,
            checks_sha256=digest(canonical(self.checks)),summary=self.summary,
            report_sha256={name:digest(raw) for name,raw in self.raw.items()},
            scope='Read-only provider-bound compact ZIP, source attribution, report/protocol consistency, obligation import identities, and arithmetic review. No kernels or producer modules executed. No independent old-secret HMAC verification; caches, original receipt bodies, exporter inputs and built binaries are absent from this compact archive. Reported replay checks retain their original trust boundary.')
        self.args.out.parent.mkdir(parents=True,exist_ok=True)
        self.args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(passed=result['passed'],checks=result['check_count'],failures=len(failed),out=str(self.args.out))))
        return 0 if result['passed'] else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zip',type=Path,required=True)
    p.add_argument('--artifact-metadata',type=Path,required=True);p.add_argument('--source',required=True)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    return Review(p.parse_args()).run()


if __name__=='__main__':raise SystemExit(main())
