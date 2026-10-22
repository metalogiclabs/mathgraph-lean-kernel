#!/usr/bin/env python3
"""Independent contextual arithmetic for authenticated-state three-arm evidence.

Standard library only. This reader does not certify source semantics, HMACs,
reuse decisions or kernel verdicts. It never promotes a local smoke result.
"""
import argparse
import csv
from decimal import Decimal, getcontext
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import random
import re
import statistics
import zipfile

getcontext().prec = 80
ZERO = Decimal(0)
SCHEMA = 'mathgraph.authenticated-export-state-economics.v1'
ARMS = ('state', 'full_export', 'direct')
EDITS = ('early-definition', 'unrelated-definition',
         'restore-early-definition', 'restore-unrelated-definition')
PHASES = ('baseline_validation', 'identity_update', 'materialization_and_hash',
          'checking', 'persistence')
FULL_COUNTERS = ('full_export_bytes_materialized', 'full_export_bytes_hashed',
                 'full_successor_bytes_read', 'full_export_disk_bytes_written')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def pairs_hook(items):
    out = {}
    for key, value in items:
        require(key not in out, 'duplicate JSON key: ' + key)
        out[key] = value
    return out


def loads(raw):
    def bad(value):
        raise ValueError('nonfinite JSON number: ' + value)
    return json.loads(raw, parse_float=Decimal, parse_constant=bad,
                      object_pairs_hook=pairs_hook)


def num(value):
    require(type(value) in (int, Decimal), 'expected finite JSON numeric measurement')
    out = Decimal(value)
    require(out.is_finite(), 'nonfinite numeric measurement')
    return out


def total(values):
    return sum((num(value) for value in values), ZERO)


def stats(values):
    values = sorted(num(value) for value in values)
    if not values:
        return dict(count=0, minimum=None, median=None, maximum=None, sum=ZERO)
    return dict(count=len(values), minimum=values[0], median=statistics.median(values),
                maximum=values[-1], sum=total(values))


def digest_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key:plain(item) for key,item in value.items()}
    if isinstance(value, (tuple,list)):
        return [plain(item) for item in value]
    return value


class Source:
    def __init__(self, *, local_summary=None, artifact=None, summary_member=None, evidence_root=None):
        require(bool(local_summary) != bool(artifact), 'choose one summary source')
        self.path = Path(local_summary or artifact).resolve()
        self.archive = None
        if artifact:
            self.zip_signature=self.file_signature()
            self.archive=zipfile.ZipFile(self.path)
            self.assert_opened_zip()
        self.member = summary_member
        self.raw = None
        self.evidence_root=Path(evidence_root).resolve() if evidence_root else None
        if self.evidence_root is not None:
            require(not self.archive and self.path.is_relative_to(self.evidence_root),
                    'summary is outside evidence root or root supplied with ZIP')
        if self.archive:
            self.members = {}
            for item in self.archive.infolist():
                name = item.filename
                require(not name.startswith('/') and '..' not in PurePosixPath(name).parts,
                        'unsafe ZIP path')
                require(name not in self.members, 'duplicate ZIP member')
                self.members[name] = item
            if self.member is None:
                choices = [name for name in self.members if name.endswith('authenticated-state/summary.json')]
                require(len(choices) == 1, 'select exact authenticated-state summary member')
                self.member = choices[0]
            require(self.member in self.members, 'missing summary member')
            require(self.members[self.member].file_size <= 512*1024*1024, 'summary exceeds scoped 512 MiB cap')
            parent=str(PurePosixPath(self.member).parent)
            self.prefix = '' if parent=='.' else parent+'/'
        else:
            self.prefix = ''

    def load(self):
        if self.archive:
            self.assert_opened_zip()
        self.signature = self.file_signature()
        self.input_digest = digest_file(self.path)
        self.raw = self.archive.read(self.member) if self.archive else self.path.read_bytes()
        self.assert_stable()
        return loads(self.raw)

    def file_signature(self):
        value=self.path.stat()
        return tuple(getattr(value,key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))

    def assert_stable(self):
        if self.archive:
            self.assert_opened_zip()
        require(self.file_signature()==self.signature and digest_file(self.path)==self.input_digest,
                'source bytes changed during arithmetic')

    def assert_opened_zip(self):
        value=os.fstat(self.archive.fp.fileno())
        opened=tuple(getattr(value,key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
        require(opened==self.zip_signature==self.file_signature(),
                'opened ZIP identity differs from current artifact path')

    def namespace(self, relative):
        """File sizes in one post-timing runtime namespace, no extraction."""
        if self.archive:
            prefix = self.prefix + relative + '/'
            result = [(name[len(prefix):],item.file_size) for name,item in self.members.items()
                      if name.startswith(prefix) and not item.is_dir()]
            return bool(result), result
        root = self.path.parent / relative
        if not root.is_dir():
            return False, []
        result = []
        for path in sorted(root.rglob('*')):
            require(not path.is_symlink(), 'symlink in runtime namespace')
            if path.is_file():
                result.append((path.relative_to(root).as_posix(),path.stat().st_size))
        return True, result


def paired(candidate, control, seed, repetitions=10000):
    """Reimplement paired-index bootstrap using native float report arithmetic."""
    a, b = [float(value) for value in candidate], [float(value) for value in control]
    require(a and len(a) == len(b), 'nonempty complete paired observations required')
    require(all(value > 0 and value < float('inf') for value in a+b), 'positive finite economic durations required')
    mid_a, mid_b = statistics.median(a), statistics.median(b)
    ratio = mid_a/mid_b
    rng = random.Random(seed)
    draws = []
    for _ in range(repetitions):
        indices = [rng.randrange(len(a)) for _ in a]
        draws.append(statistics.median(a[i] for i in indices)/statistics.median(b[i] for i in indices))
    draws.sort()
    interval = [draws[int(q*(repetitions-1))] for q in (.025,.975)]
    wins = sum(x < y for x,y in zip(a,b))
    passed = ratio < 1 and wins > len(a)/2 and interval[1] < 1
    return dict(candidate_values=a, control_values=b, apply_median_wall_seconds=mid_a,
                direct_median_wall_seconds=mid_b, median_ratio=ratio, paired_count=len(a),
                paired_wins=wins, bootstrap_ratio_interval_95=interval,
                bootstrap_seed=seed, bootstrap_repetitions=repetitions,
                reduction_percent=100*(1-ratio), speedup=1/ratio,
                passed=passed, status='SPEEDUP' if passed else 'NO_SPEEDUP')


def compare_published(calculated, reported, count):
    for field in ('apply_median_wall_seconds','direct_median_wall_seconds','median_ratio',
                  'paired_count','paired_wins','bootstrap_ratio_interval_95',
                  'bootstrap_seed','bootstrap_repetitions','reduction_percent','speedup'):
        expected, observed = calculated[field], reported[field]
        if isinstance(expected,list):
            equal = len(expected)==len(observed) and all(x==float(num(y)) for x,y in zip(expected,observed))
        else:
            equal = expected==float(num(observed))
        require(equal, 'published economics mismatch: '+field)
    expected_status = calculated['status'] if count >= 5 else 'INCOMPLETE_FEWER_THAN_FIVE_PAIRS'
    expected_pass = calculated['passed'] if count >= 5 else False
    require(reported['status']==expected_status and reported['passed'] is expected_pass,
            'published economics mismatch: status/pass')
    if count < 5:
        require(reported['observed_status']==calculated['status'], 'published economics mismatch: observed status')


def partition(timings):
    wall = {name+'_seconds':num(timings[name+'_seconds']) for name in PHASES}
    wall['producer_seconds'] = num(timings['producer_seconds'])
    wall['consumer_gap_seconds'] = num(timings['consumer_seconds'])-total(wall[name+'_seconds'] for name in PHASES)
    wall['before_consumer_gap_seconds'] = num(timings['end_to_end_seconds'])-wall['producer_seconds']-num(timings['consumer_seconds'])
    wall['disjoint_reconstruction_seconds'] = total(wall.values())
    wall['promotion_nested_seconds'] = num(timings['chain_promotion_seconds'])
    wall['persistence_before_promotion_seconds'] = wall['persistence_seconds']-wall['promotion_nested_seconds']
    wall['apply_seconds'] = num(timings['end_to_end_seconds'])
    wall['has_negative_residual'] = wall['consumer_gap_seconds'] < 0 or wall['before_consumer_gap_seconds'] < 0
    cpu = {name+'_seconds':num(timings[name+'_cpu_seconds']) for name in PHASES}
    cpu['consumer_gap_seconds'] = num(timings['consumer_cpu_seconds'])-total(cpu.values())
    cpu['before_consumer_seconds'] = num(timings['end_to_end_cpu_seconds'])-num(timings['consumer_cpu_seconds'])
    cpu['disjoint_reconstruction_seconds'] = total(cpu.values())
    cpu['promotion_nested_seconds'] = num(timings['chain_promotion_cpu_seconds'])
    cpu['persistence_before_promotion_seconds'] = cpu['persistence_seconds']-cpu['promotion_nested_seconds']
    cpu['apply_seconds'] = num(timings['end_to_end_cpu_seconds'])
    cpu['has_negative_residual'] = cpu['consumer_gap_seconds'] < 0 or cpu['before_consumer_seconds'] < 0
    return dict(wall=wall, cpu=cpu)


def cache_size(source, profile, repetition, arm, descriptors):
    relative=f'primary/{profile}/pair-{repetition}/{arm}/session'
    complete, files=source.namespace(relative)
    archived={}
    for item in descriptors:
        origin=item['original_path'];needle=relative+'/'
        require(origin.count(needle)==1, 'cache descriptor does not name one runtime namespace')
        name=origin.split(needle,1)[1]
        require(name and '..' not in PurePosixPath(name).parts, 'unsafe cache original path')
        size=item['uncompressed_bytes']
        require(type(size) is int and size>=0 and name not in archived, 'invalid/repeated logical cache descriptor')
        archived[name]=size
    raw={name:size for name,size in files if not name.endswith('.archive.json')}
    require(not (set(raw)&set(archived)), 'runtime file exists as both raw and archived')
    if complete:
        wrappers={name[:-len('.archive.json')] for name,_ in files if name.endswith('.archive.json')}
        require(wrappers==set(archived), 'runtime archive-wrapper coverage differs from descriptors')
    return dict(namespace_complete=complete,
        logical_runtime_file_bytes=sum(raw.values())+sum(archived.values()) if complete else None,
        logical_runtime_files=len(raw)+len(archived) if complete else None,
        surviving_raw_file_bytes=sum(raw.values()), archive_restored_logical_bytes=sum(archived.values()),
        archived_files_lower_bound_bytes=sum(archived.values()),
        scope='Logical persisted file-content bytes in this runtime session after close, substituting pre-compression originals. '
              'Transport archive wrappers excluded; repeated baseline copies in separate namespaces count separately. '
              'Completeness assumes supplied namespace packaging retains every small runtime file; descriptors alone cannot prove that. '
              'Not physical allocated blocks, compressed artifact size, native heap or aggregate RAM.')


def memory(rows, final):
    observed=[];grouped={};missing=[]
    for revision,sample in [(row['revision'],row['memory']) for row in rows]+[(None,final)]:
        for process,fields in sample.get('processes',{}).items():
            if not fields:
                missing.append(dict(revision=revision,process=process));continue
            for field in ('VmRSS','VmHWM','RssAnon','RssFile'):
                if field in fields:
                    require(type(fields[field]) is int and fields[field]>=0,'invalid memory observation')
                    observed.append(dict(revision=revision,process=process,field=field,kib=fields[field]))
                    grouped.setdefault(process,{}).setdefault(field,[]).append(fields[field])
    return dict(observations=observed, missing=missing,
        per_process_statistics={p:{f:{k:x for k,x in stats(v).items() if k!='sum'} for f,v in fs.items()} for p,fs in grouped.items()},
        scope='Post-apply per-process procfs KiB; VmHWM is cumulative since startup. Final sample is separate. '
              'No sum across process peaks, continuous aggregate peak, isolated phase peak or memory-saving claim.')


def arm_analysis(source,profile,repetition,kind,raw,expected_steps):
    if kind=='direct':
        commands=raw['commands']
        require(len(commands)==expected_steps+1 and all(c['revision']==i and c['returncode']==0 and c['timed_out'] is False for i,c in enumerate(commands)),
                'incomplete/direct failed command sequence')
        return dict(lifecycle_wall_seconds=num(raw['wall_seconds']),lifecycle_cpu_seconds=num(raw['cpu_seconds']),
            genesis_command_wall_seconds=num(commands[0]['wall_seconds']),
            revision_command_wall_seconds=[num(c['wall_seconds']) for c in commands[1:]],
            scope='Fresh Rust on genesis plus each identical export; input preparation outside timer.')
    require(len(raw['steps'])==expected_steps,'incomplete update sequence')
    rows=[];work=dict(delta_bytes=0,export_bytes=0,checked=0,reused=0,**{field:0 for field in FULL_COUNTERS})
    for i,step in enumerate(raw['steps'],1):
        require(step['revision']==i and step['status']=='VERIFIED','missing actual accepted update')
        rep=step['representation']
        for key in ('delta_bytes','export_bytes','full_export_disk_bytes_written'):
            require(type(rep[key]) is int and rep[key]>=0,'invalid representation work counter')
        if kind=='state':
            require(step['export_sha256'] is None and all(type(rep.get(k)) is int and rep[k]==0 for k in FULL_COUNTERS),
                    'state full-export work is not zero or acquired full-export hash')
            counters={k:rep[k] for k in FULL_COUNTERS}
        else:
            counters={k:rep['export_bytes'] for k in FULL_COUNTERS[:3]}
            counters['full_export_disk_bytes_written']=rep['full_export_disk_bytes_written']
        parts=partition(step['timings'])
        rows.append(dict(revision=i,name=EDITS[(i-1)%4],apply_wall_seconds=num(step['apply_wall_seconds']),
            apply_cpu_seconds=num(step['apply_cpu_seconds']),wall=parts['wall'],cpu=parts['cpu'],
            delta_bytes=rep['delta_bytes'],export_bytes=rep['export_bytes'],work=counters,
            counts=step['counts'],memory=step.get('memory',{})))
        for k,v in counters.items():work[k]+=v
        work['delta_bytes']+=rep['delta_bytes'];work['export_bytes']+=rep['export_bytes']
        work['checked']+=step['counts']['rechecked'];work['reused']+=step['counts']['reused']
    phases={unit:{key:total(row[unit][key] for row in rows) for key in rows[0][unit] if key!='has_negative_residual'} for unit in ('wall','cpu')}
    outer=num(raw['wall_seconds']);outer_cpu=num(raw['cpu_seconds'])
    setup=num(raw['setup_wall_seconds']);setup_cpu=num(raw['setup_cpu_seconds'])
    close=num(raw['close_wall_seconds']);close_cpu=num(raw['close_cpu_seconds'])
    warm=total(row['apply_wall_seconds'] for row in rows);warm_cpu=total(row['apply_cpu_seconds'] for row in rows)
    ready=raw['genesis']['ready']
    return dict(lifecycle_wall_seconds=outer,lifecycle_cpu_seconds=outer_cpu,
        constructor_plus_start_wall_seconds=setup,constructor_plus_start_cpu_seconds=setup_cpu,
        start_reported_wall_seconds=num(ready['wall_seconds']),
        constructor_and_call_overhead_residual_wall_seconds=setup-num(ready['wall_seconds']),
        warm_update_sum_wall_seconds=warm,warm_update_sum_cpu_seconds=warm_cpu,
        close_wall_seconds=close,close_cpu_seconds=close_cpu,
        outer_recording_sampling_residual_wall_seconds=outer-setup-warm-close,
        outer_recording_sampling_residual_cpu_seconds=outer_cpu-setup_cpu-warm_cpu-close_cpu,
        phases=phases,updates=rows,warm_work=work,
        work_counter_scope='State full-export zeros are recorded counters. Full-export materialized/hashed/readback bytes are derived from export_bytes and frozen full-materializer/promotion semantics, not direct byte counters. Logical byte traffic only; not all physical memory movement.',
        cache=cache_size(source,profile,repetition,kind,raw['compressed_session_files']),
        memory=memory(rows,raw.get('memory',{})))


def cold_summary(profile,steps):
    out={}
    for arm,key in (('state','state_witness'),('full_export','full_export_witness')):
        cold=profile[key]['cold_replay'];ready=cold['ready']
        require(cold['passed'] is True and ready['replayed_revisions']==steps,'cold replay missing full history')
        out[arm]=dict(observed_outer_setup_seconds=num(cold['wall_seconds'] if arm=='state' else cold['setup_wall_seconds']),
            reported_start_history_seconds=num(ready['wall_seconds']),
            reported_baseline_start_seconds=num(ready['baseline_start_seconds']),
            reported_start_history_cpu_seconds=num(ready['cpu_seconds']),
            replayed_revisions=ready['replayed_revisions'],
            close_seconds=num(cold['close_wall_seconds']) if 'close_wall_seconds' in cold else None,
            scope='One logical cold constructor/start/history recovery observation with warm OS caches. State close is not separately recorded. Full-export setup/close have independent audits between them. Prior baseline evidence is authenticated; not a new full genesis check.')
    return out


def analyze(report,source,expected_source):
    source.assert_stable()
    require(report.get('schema')==SCHEMA,'unrecognized benchmark schema')
    require(re.fullmatch('[0-9a-f]{40}',expected_source or '') and report['source_sha']==expected_source,'source mismatch')
    require(report['completed'] is True and report['correctness_passed'] is True and report['source_and_binary_stable'] is True,'incomplete/unstable measured report')
    n,cycles=report['repetitions'],report['cycles']
    require(type(n) is int and n>0 and type(cycles) is int and cycles>0,'positive actual pair/cycle counts required')
    qualified=report['correctness_qualified']
    require(type(qualified) is bool,'correctness qualification flag must be boolean')
    if qualified:
        require(n==5 and cycles==10 and set(report['profiles'])=={'original','expanded'} and report['source_tracked_clean'] is True,
                'qualification dimensions/source are incomplete')
    require(report['qualified'] is qualified,'qualified alias differs from correctness scope')
    require(set(report['profiles'])==set(report['requested_profiles']),'requested profiles differ from actual profiles')
    raw=source.raw
    require(raw is not None,'load raw source before arithmetic')
    out=dict(schema='mathgraph.authenticated-state-independent-cost-arithmetic.v1',
        status='CONTEXTUAL_EXACT_SOURCE_5X40_ARITHMETIC' if qualified else 'CONTEXTUAL_SMOKE_ONLY',
        qualification_claim=False,source_report_correctness_qualified=qualified,
        source_sha=expected_source,summary_sha256=hashlib.sha256(raw).hexdigest(),summary_bytes=len(raw),
        reported_economic_status=report['economic_status'],profiles={},
        provenance=dict(input=str(source.path),summary_member=source.member,
            artifact_sha256=digest_file(source.path) if source.archive else None,
            evidence_root=str(source.evidence_root) if source.evidence_root else None,
            helper_sha256=digest_file(__file__),source_tracked_clean=report['source_tracked_clean']),
        scope='Independent arithmetic/context only; no checker, authority, producer or benchmark imports. '
              'Source-report correctness qualification is observed, not independently certified here. '
              'Negative economics and missing measurements retained. Native index copies/loops, Python applicability scans and cold admission remain O(N); no asymptotic total-work claim.')
    expected_steps=cycles*4
    for name,item in report['profiles'].items():
        require(len(item['pairs'])==n,'missing measured pairs')
        pairs=[]
        for rep,pair in enumerate(item['pairs']):
            require(pair['repetition']==rep and pair['completed'] is True,'incomplete/misordered pair')
            require(pair['order']==list(ARMS[rep%3:]+ARMS[:rep%3]),'three-arm order differs from rotating design')
            require(all(pair[k]['completed'] is True for k in ARMS),'incomplete measured arm')
            for i in range(expected_steps):
                state,full=pair['state']['steps'][i],pair['full_export']['steps'][i]
                command=pair['direct']['commands'][i+1]
                require(state['counts']==full['counts'] and state['representation']['export_bytes']==full['representation']['export_bytes'] and
                        full['export_sha256']==command['input_sha256'] and full['representation']['export_bytes']==command['input_bytes'],
                        'three-arm input/work correspondence differs')
            pairs.append(dict(repetition=rep,order=pair['order'],arms={kind:arm_analysis(source,name,rep,kind,pair[kind],expected_steps) for kind in ARMS}))
        economics={}
        for index,(candidate,control) in enumerate((('state','direct'),('state','full_export'),('full_export','direct'))):
            for metric in ('wall_seconds','cpu_seconds'):
                key=candidate+'_vs_'+control+'_'+metric
                calc=paired([p[candidate][metric] for p in item['pairs']],[p[control][metric] for p in item['pairs']],20261024+index)
                compare_published(calc,item['economics'][key],n)
                economics[key]=calc
        warm={}
        for edit_index,edit in enumerate(EDITS):
            positions=list(range(edit_index,expected_steps,4));series=[]
            for pair in item['pairs']:
                # Reproduce the frozen report's native-float summation, while
                # phase arithmetic elsewhere uses exact Decimal literals.
                series.append({kind:sum(float(pair[kind]['steps'][i]['apply_wall_seconds']) for i in positions) for kind in ('state','full_export')} |
                              {'direct':sum(float(pair['direct']['commands'][i+1]['wall_seconds']) for i in positions)})
            entry=dict(updates_per_pair=len(positions),paired_sum_values=series,
                paired_mean_values=[{kind:value/len(positions) for kind,value in row.items()} for row in series],comparisons={})
            for control in ('direct','full_export'):
                key='state_vs_'+control
                calc=paired([s['state'] for s in series],[s[control] for s in series],20261030)
                published=item['warm_edit_economics'][edit][key]
                compare_published(calc,published,n)
                require(published['updates_per_pair']==len(positions),'warm update count differs')
                require(float(num(published['state_median_seconds_per_update']))==calc['apply_median_wall_seconds']/len(positions) and
                        float(num(published['comparator_median_seconds_per_update']))==calc['direct_median_wall_seconds']/len(positions),'warm mean arithmetic differs')
                entry['comparisons'][key]=calc
            warm[edit]=entry
        summaries={}
        for arm in ARMS:
            fields=[k for k,v in pairs[0]['arms'][arm].items() if isinstance(v,Decimal)]
            summaries[arm]={field:stats(pair['arms'][arm][field] for pair in pairs) for field in fields}
        out['profiles'][name]=dict(pairs=pairs,economics=economics,warm_edits=warm,
            lifecycle_component_statistics=summaries,cold=cold_summary(item,expected_steps))
    economics_pass=all(p['economics'][key]['passed'] is True for p in out['profiles'].values()
        for key in ('state_vs_direct_wall_seconds','state_vs_full_export_wall_seconds'))
    expected_economic_status=('QUALIFIED_SPEEDUP' if economics_pass else 'QUALIFIED_NEGATIVE_OR_INCONCLUSIVE') if qualified else 'SMOKE_OR_INCOMPLETE'
    require(report['economic_status']==expected_economic_status,'economic qualification status differs from actual paired measurements')
    source.assert_stable()
    return out


def write_outputs(out,directory):
    directory.mkdir(parents=True,exist_ok=False)
    (directory/'analysis.json').write_text(json.dumps(plain(out),indent=2)+'\n')
    life=[];updates=[];warm=[];mem=[]
    for profile,item in out['profiles'].items():
        for pair in item['pairs']:
            for arm,record in pair['arms'].items():
                life.append(dict(profile=profile,pair=pair['repetition'],arm=arm,
                    **{k:v for k,v in record.items() if isinstance(v,Decimal)}))
                for row in record.get('updates',[]):
                    update=dict(profile=profile,pair=pair['repetition'],arm=arm,revision=row['revision'],edit=row['name'],
                        external_apply_wall_seconds=row['apply_wall_seconds'],external_apply_cpu_seconds=row['apply_cpu_seconds'],delta_bytes=row['delta_bytes'],
                        **row['work'])
                    for unit in ('wall','cpu'):
                        update.update({unit+'_'+k:v for k,v in row[unit].items()})
                    updates.append(update)
                for observation in record.get('memory',{}).get('observations',[]):
                    mem.append(dict(profile=profile,pair=pair['repetition'],arm=arm,**observation))
        for edit,entry in item['warm_edits'].items():
            for rep,means in enumerate(entry['paired_mean_values']):
                warm.append(dict(profile=profile,edit=edit,pair=rep,updates_per_pair=entry['updates_per_pair'],**means))
    for filename,rows in (('raw-lifecycles.csv',life),('raw-update-phases.csv',updates),('raw-warm-paired-means.csv',warm),('raw-memory-observations.csv',mem)):
        keys=list(dict.fromkeys(key for row in rows for key in row))
        with (directory/filename).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(rows)
    lines=['# Authenticated-state cost arithmetic','',out['status']+'. Contextual arithmetic only; no new correctness authority.',
           '','Source `'+out['source_sha']+'`; exact summary SHA256 `'+out['summary_sha256']+'`.',
           '','| Profile | State lifecycle, s | Full export, s | Direct Rust, s | State/direct reduction | State/full reduction |',
           '| --- | ---: | ---: | ---: | ---: | ---: |']
    for profile,item in out['profiles'].items():
        values=[item['lifecycle_component_statistics'][arm]['lifecycle_wall_seconds']['median'] for arm in ARMS]
        ed=item['economics']['state_vs_direct_wall_seconds'];ef=item['economics']['state_vs_full_export_wall_seconds']
        statuses=[e['status'] if out['source_report_correctness_qualified'] else 'UNQUALIFIED_OBSERVATION' for e in (ed,ef)]
        lines.append(f'| {profile} | '+ ' | '.join(f'{v:.6f}' for v in values)+f" | {ed['reduction_percent']:.3f}% ({statuses[0]}) | {ef['reduction_percent']:.3f}% ({statuses[1]}) |")
    lines += ['', 'Full producer/authentication/identity/selected checking/persistence and supported close are inside each candidate timer. '
        'Direct input preparation is outside timing. Raw pairs, ten-update per-edit means (four-update smoke: one), CPU, cold components, nested phases, logical cache sizes and per-process memory remain in JSON/CSV.',
        '', 'Promotion is included in persistence. State materialization_and_hash is a delta-only recipe phase; no full-export SHA is claimed. '
        'Full-export byte counts are derived; state zero counts are recorded. Procfs RSS/HWM samples establish no aggregate peak. '
        'Cold admission/history replay and remaining index/applicability loops prevent any asymptotic total-work claim.']
    (directory/'analysis.md').write_text('\n'.join(lines)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--local-summary','--summary',dest='local_summary',type=Path);group.add_argument('--artifact',type=Path)
    parser.add_argument('--evidence-root',type=Path)
    parser.add_argument('--summary-member');parser.add_argument('--expected-source',required=True)
    parser.add_argument('--ci-run');parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    source=Source(local_summary=args.local_summary,artifact=args.artifact,summary_member=args.summary_member,evidence_root=args.evidence_root)
    report=source.load();out=analyze(report,source,args.expected_source)
    out['provenance']['declared_ci_run']=args.ci_run
    require(hashlib.sha256(source.raw).hexdigest()==out['summary_sha256'],'loaded summary drift')
    write_outputs(out,args.out)
    source.assert_stable()
    print(json.dumps(dict(status=out['status'],profiles=list(out['profiles']),summary_sha256=out['summary_sha256'])))


if __name__=='__main__':main()
