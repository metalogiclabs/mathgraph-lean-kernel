#!/usr/bin/env python3
"""Independent exact-export qualification; all status/resource evidence is retained."""
import argparse
import functools
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

from process import run, sha256

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def verdict(record):
    if record['timed_out']:
        return 'ERROR_TIMEOUT'
    return {0:'ACCEPT', 1:'REJECT', 2:'DECLINE'}.get(record['returncode'], 'ERROR')


def invoke_engine(export, selected, cache, key, output, previous=None, policy='default', disable=False,
                  *, identity_backend='python', indexer=None):
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(HERE / 'engine.py'), '--export', str(export),
               '--checker', str(selected), '--cache', str(cache), '--authority-key', str(key),
               '--output', str(output), '--policy', policy]
    command += ['--identity-backend', identity_backend]
    if identity_backend != 'python':
        command += ['--indexer', str(indexer)]
    if previous:
        command += ['--previous', previous]
    if disable:
        command += ['--disable-cache']
    resources = run(command, output.with_name(output.stem + '-process'), timeout=900)
    result = json.loads(output.read_text()) if output.exists() else {'status':'UNKNOWN', 'error':'missing result'}
    protocol_valid = (output.exists() and not resources['timed_out'] and resources['returncode']==
                      {'VERIFIED':0,'REJECTED':1,'UNKNOWN':2}.get(result.get('status')))
    return dict(result=result, resources=resources, result_path=str(output), protocol_valid=protocol_valid,
                result_sha256=sha256(output) if output.exists() else None)


def compact(value):
    if isinstance(value, dict):
        return {key:compact(item) for key,item in value.items()
                if key not in ('decisions','invalidation_events','checker_result')}
    if isinstance(value,list):
        return [compact(item) for item in value]
    return value


def qualify(args):
    # Exercise the original gates and controls with the selected accelerator;
    # their expected outcomes and reuse predicate remain unchanged.
    invoke_engine = functools.partial(globals()['invoke_engine'],
        identity_backend=args.identity_backend, indexer=args.indexer)
    out = args.out.resolve()
    if (out / 'summary.json').exists():
        raise ValueError('use a new output directory; previous evidence must remain reviewable')
    out.mkdir(parents=True, exist_ok=True)
    workloads = args.workloads.resolve()
    manifest = json.loads((workloads / 'manifest.json').read_text())
    selected = args.checker.resolve()
    full_checker = args.full_checker.resolve()
    tools = manifest['tools']
    pin = json.loads((HERE/'pins.json').read_text())
    release_pins = pin['lean_release_binaries_sha256']
    for name, expected in release_pins.items():
        if tools[name]['sha256'] != expected or sha256(tools[name]['path']) != expected:
            raise ValueError('independent release executable differs from pin: '+name)
    if set(manifest['variants']) != set(pin['export_sha256']):
        raise ValueError('qualification requires the exact pinned variant set')
    for name, info in manifest['variants'].items():
        if sha256(info['path']) != info['sha256'] or info['sha256'] != pin['export_sha256'][name]:
            raise ValueError('workload hash changed: ' + info['path'])
    for tool in ('leanchecker', 'leanchecker-paranoid'):
        if not tools[tool]['exists'] or sha256(tools[tool]['path']) != tools[tool]['sha256']:
            raise ValueError('missing or changed mandatory independent kernel: ' + tool)
    authority = (args.authority_dir or out.parent / ('.' + out.name + '-authority')).resolve()
    if authority == out or out in authority.parents:
        raise ValueError('authority secret must live outside published result/cache directories')
    authority.mkdir(parents=True, exist_ok=True)
    key = authority / 'issuer.key'
    if key.exists():
        raise ValueError('qualification requires its own fresh authority key')
    initialized = run([sys.executable, str(HERE / 'engine.py'), '--init-key', str(key)], out / 'init-key')
    if initialized['returncode']:
        raise RuntimeError('authority initialization failed')
    summary = dict(schema='mathgraph.incremental-qualification.v1',
                   source_git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
                   adapter_sha256=sha256(HERE/'engine.py'),
                   harness_sources_sha256={p.name:sha256(p) for p in sorted(HERE.glob('*.py'))},
                   pins=json.loads((HERE / 'pins.json').read_text()),
                   workload_manifest_sha256=sha256(workloads / 'manifest.json'),
                   checker_sha256=sha256(selected), full_checker_sha256=sha256(full_checker),
                   identity_backend=args.identity_backend,
                   indexer_sha256=sha256(args.indexer) if args.identity_backend != 'python' else None,
                   repetitions=args.repetitions, oracles={}, scenarios={}, optional_kernels={}, gates=[])
    cache = out / 'cache'
    baseline = Path(manifest['variants']['baseline']['path'])
    base = invoke_engine(baseline, selected, cache, key, out / 'baseline-full.json', disable=True)
    summary['baseline'] = base
    if base['result']['status'] != 'VERIFIED':
        write(out / 'summary.json', summary)
        raise RuntimeError('baseline selected-check engine did not verify')
    base_id = base['result']['evidence_id']
    # The raw full checker is also measured independently of Python/cache overhead.
    config = dict(export_file_path=str(baseline), use_stdin=False,
                  permitted_axioms=['propext','Classical.choice','Quot.sound'],
                  unpermitted_axiom_hard_error=True, num_threads=1,
                  nat_extension=True, string_extension=True, print_success_message=True)
    write(out / 'full-checker-config.json', config)
    native = run([str(full_checker), str(out / 'full-checker-config.json')], out / 'native-full')
    summary['native_full'] = dict(status=verdict(native), resources=native)
    summary['gates'].append(dict(name='native-full-baseline', passed=verdict(native)=='ACCEPT'))
    parse_config = dict(config, parse_only=True)
    write(out / 'parse-only-config.json', parse_config)
    parsed = run([str(full_checker), str(out/'parse-only-config.json')],out/'native-parse-only')
    summary['native_parse_only'] = dict(status=verdict(parsed),resources=parsed)
    summary['gates'].append(dict(name='native-parse-only',passed=verdict(parsed)=='ACCEPT'))
    lake = Path(tools['lean']['path']).with_name('lake')
    lake_run = run([str(lake), 'check', '--from-export', str(baseline), '--paranoid'],
                   out / 'lake-check-paranoid', timeout=900)
    lake_stderr = Path(lake_run['stderr_path']).read_text()
    summary['lake_check_paranoid'] = dict(status='ACCEPT' if lake_run['returncode']==0 else
        'INFRASTRUCTURE_UNAVAILABLE' if lake_run['returncode']==2 or 'bwrap:' in lake_stderr else 'FAILED',
        resources=lake_run,
        scope='Lake also enforces standard axioms; direct exact-export kernel runs remain mandatory below')
    lake_unsandboxed = run([str(lake),'check','--from-export',str(baseline),'--paranoid',
                           '--inadvisably-no-sandbox'],out/'lake-check-paranoid-unsandboxed',timeout=900)
    summary['lake_check_paranoid_unsandboxed'] = dict(status='ACCEPT' if lake_unsandboxed['returncode']==0 else 'FAILED',
        resources=lake_unsandboxed,sandbox=False,
        scope='Explicit expert diagnostic; sandboxed command above is the stronger Lake result')
    # Same raw bytes enter both mandatory independent C++ implementations.
    for variant, info in manifest['variants'].items():
        summary['oracles'][variant] = {}
        expected = 'REJECT' if variant in ('invalid-proof', 'axiom-type', 'malformed-unused-dag','malformed-unused-typed-node') else 'ACCEPT'
        for tool in ('leanchecker', 'leanchecker-paranoid'):
            record = run([tools[tool]['path'], '--from-export', info['path']], out / 'oracles' / (variant + '-' + tool))
            actual = verdict(record)
            summary['oracles'][variant][tool] = dict(status=actual, expected=expected, resources=record,
                                                       export_sha256=info['sha256'], binary_sha256=tools[tool]['sha256'])
            summary['gates'].append(dict(name=variant + '-' + tool, passed=actual==expected))
    if args.optional_kernels:
        for tool, flags in [('lean4lean',['--import']), ('con-leche',['--verified']), ('con-ron',['--verified']), ('nanoda_bin',[])]:
            if not tools[tool]['exists']:
                summary['optional_kernels'][tool] = dict(status='UNAVAILABLE')
                continue
            if tool == 'nanoda_bin':
                config['num_threads'] = 4
                config['unpermitted_axiom_hard_error'] = False
                write(out / 'nanoda-config.json', config)
                command = [tools[tool]['path'], str(out / 'nanoda-config.json')]
            else:
                command = [tools[tool]['path'], *flags, str(baseline)]
            record = run(command, out / 'optional' / tool, timeout=args.optional_timeout)
            summary['optional_kernels'][tool] = dict(status=verdict(record), resources=record,
                                                        binary_sha256=tools[tool]['sha256'])
            summary['gates'].append(dict(name='optional-'+tool+'-no-disagreement',
                passed=verdict(record) in ('ACCEPT','DECLINE','ERROR_TIMEOUT')))
        if all(entry['status']=='ACCEPT' for entry in summary['optional_kernels'].values()):
            summary['gates'].append(dict(name='lake-paranoid-unsandboxed-agreement',passed=lake_unsandboxed['returncode']==0))
            summary['gates'].append(dict(name='lake-paranoid-sandboxed-agreement',
                passed=summary['lake_check_paranoid']['status'] in ('ACCEPT','INFRASTRUCTURE_UNAVAILABLE')))
    # Each invocation is a separate process. Warm results therefore include a real
    # process restart and cache authentication; there is no process-local cache.
    cases = [('no-change','baseline'), ('early-definition','early-definition'),
             ('unrelated-definition','unrelated-definition'), ('theorem-leaf','theorem-leaf'),
             ('type-change','type-change'), ('invalid-proof','invalid-proof'),
             ('axiom-type','axiom-type'), ('toolchain-metadata','toolchain-metadata'),
             ('malformed-unused-dag','malformed-unused-dag'),
             ('malformed-unused-typed-node','malformed-unused-typed-node')]
    early_id = None
    for name, variant in cases:
        runs = []
        for repeat in range(args.repetitions):
            export = Path(manifest['variants'][variant]['path'])
            location = out / 'scenarios' / name / str(repeat)
            location.mkdir(parents=True, exist_ok=True)
            # Alternate pair order to expose rather than hide scheduling/cache bias.
            modes = ['fresh','incremental'] if repeat % 2 == 0 else ['incremental','fresh']
            pair = {}
            for mode in modes:
                pair[mode] = invoke_engine(export, selected, cache if mode=='incremental' else location/'fresh-cache', key,
                    location/(mode+'.json'), previous=base_id if mode=='incremental' else None,
                    disable=mode=='fresh')
            fresh, incremental = pair['fresh']['result'], pair['incremental']['result']
            expected = 'UNKNOWN' if variant=='malformed-unused-dag' else 'REJECTED' if variant in ('invalid-proof','axiom-type','malformed-unused-typed-node') else 'VERIFIED'
            agreed = fresh['status']==incremental['status']==expected
            summary['gates'].append(dict(name=f'{name}-{repeat}-agreement', passed=agreed))
            if expected != 'VERIFIED':
                summary['gates'].append(dict(name=f'{name}-{repeat}-no-evidence',
                    passed=not incremental.get('evidence_id') and not fresh.get('evidence_id')))
            if variant=='malformed-unused-typed-node':
                summary['gates'].append(dict(name=f'{name}-{repeat}-real-parser-with-zero-obligations',
                    passed=incremental.get('counts',{}).get('scheduled')==0 and
                    incremental.get('counts',{}).get('reused')==incremental.get('counts',{}).get('total') and
                    incremental.get('checker_result',{}).get('code')==1))
            if name in ('no-change','early-definition','unrelated-definition','theorem-leaf') and agreed:
                fewer = incremental['counts']['rechecked'] < fresh['counts']['rechecked']
                summary['gates'].append(dict(name=f'{name}-{repeat}-fewer-kernel-obligations', passed=fewer))
            if name == 'early-definition' and incremental['status']=='VERIFIED':
                early_id = incremental['evidence_id']
                decisions = {d['name']:d for d in incremental['decisions']}
                early = decisions['IncrementalWorkload.early']
                later = sum(d['index']>early['index'] for d in incremental['decisions'])
                summary['gates'].append(dict(name=f'early-definition-{repeat}-large-later-development',passed=later>=3000))
                summary['gates'].append(dict(name=f'early-definition-{repeat}-changed-cone-rechecked',passed=all(
                    decisions[n]['status']=='VERIFIED_NEW' for n in ['IncrementalWorkload.early',
                    'IncrementalWorkload.dependent','IncrementalWorkload.dependent_spec'])))
                summary['gates'].append(dict(name=f'early-definition-{repeat}-unrelated-preserved',
                    passed=decisions['IncrementalWorkload.unrelated']['status']=='VERIFIED_REUSED' and incremental['counts']['reused']>=3000))
            if incremental['status']=='VERIFIED':
                decisions = {d['name']:d for d in incremental['decisions']}
                changed_targets = {'unrelated-definition':['IncrementalWorkload.unrelated'],
                                   'theorem-leaf':['IncrementalWorkload.leaf'],
                                   'type-change':['IncrementalWorkload.typed','IncrementalWorkload.typed_identity']}.get(name,[])
                if changed_targets:
                    summary['gates'].append(dict(name=f'{name}-{repeat}-edited-targets-rechecked',
                        passed=all(decisions[n]['status']=='VERIFIED_NEW' for n in changed_targets)))
                if name=='toolchain-metadata':
                    summary['gates'].append(dict(name=f'{name}-{repeat}-full-fallback',
                        passed=incremental['counts']['reused']==0 and incremental['counts']['rechecked']==incremental['counts']['total']))
            runs.append(pair)
        summary['scenarios'][name] = dict(runs=runs)
        print(name, [(p['fresh']['result']['status'],p['incremental']['result']['status'],p['incremental']['result'].get('counts')) for p in runs], flush=True)
        write(out/'progress.json',compact(summary))
    # Restore a changed dependency, preserving every previous evidence object.
    controls = [('restore-dependency',cache,key,early_id,'default',False),
                ('cold-cache',out/'empty-cache',key,base_id,'default',False),
                ('policy-change',cache,key,base_id,'changed-control',False),
                ('cache-disabled',cache,key,base_id,'default',True),
                ('missing-evidence',cache,key,'0'*64,'default',False)]
    corrupt = out / 'corrupt-record-cache'
    shutil.copytree(cache, corrupt)
    record = corrupt / 'records' / (base_id+'.json')
    record.chmod(0o600)
    data = json.loads(record.read_text())
    data['hmac_sha256'] = '0'*64
    record.write_text(json.dumps(data))
    controls.append(('corrupt-record',corrupt,key,base_id,'default',False))
    corrupt_snapshot = out / 'corrupt-snapshot-cache'
    shutil.copytree(cache, corrupt_snapshot)
    snapshot = corrupt_snapshot / 'exports' / (sha256(baseline)+'.ndjson')
    snapshot.chmod(0o600)
    with snapshot.open('ab') as stream:
        stream.write(b'\n')
    controls.append(('corrupt-snapshot',corrupt_snapshot,key,base_id,'default',False))
    foreign_key = authority / 'foreign.key'
    shutil.copyfile(key, foreign_key)
    foreign_key.write_bytes(b'foreign authority'.ljust(32,b'!'))
    controls.append(('foreign-authority',cache,foreign_key,base_id,'default',False))
    for name, control_cache, control_key, previous, policy, disabled in controls:
        entry = invoke_engine(baseline, selected, control_cache, control_key, out/'controls'/(name+'.json'), previous,policy,disabled)
        result = entry['result']
        summary['scenarios'][name] = entry
        verified = result['status']=='VERIFIED'
        summary['gates'].append(dict(name=name+'-verified',passed=verified))
        if name != 'restore-dependency' and verified:
            summary['gates'].append(dict(name=name+'-full-fallback',passed=result['counts']['rechecked']==result['counts']['total'] and result['counts']['reused']==0))
        if name=='restore-dependency' and verified:
            decisions = {d['name']:d for d in result['decisions']}
            summary['gates'].append(dict(name='restore-dependency-cone-rechecked',passed=result['counts']['reused']>0 and all(
                decisions[n]['status']=='VERIFIED_NEW' for n in ['IncrementalWorkload.early',
                    'IncrementalWorkload.dependent','IncrementalWorkload.dependent_spec'])))
            restored = invoke_engine(baseline,selected,cache,key,out/'controls'/'restored-evidence-reuse.json',result['evidence_id'])
            summary['scenarios']['restored-evidence-reuse'] = restored
            summary['gates'].append(dict(name='restored-evidence-fully-reused',passed=restored['result']['status']=='VERIFIED' and
                restored['result']['counts']['rechecked']==0 and restored['result']['counts']['reused']==restored['result']['counts']['total']))
    # A real ELF with an appended section still runs, but its identity changed.
    changed_checker = out / 'changed-checker'
    shutil.copy2(selected, changed_checker)
    with changed_checker.open('ab') as stream:
        stream.write(b'\nqualification executable provenance control\n')
    changed = invoke_engine(baseline,changed_checker,cache,key,out/'controls'/'checker-change.json',base_id)
    summary['scenarios']['checker-change'] = changed
    result = changed['result']
    summary['gates'].append(dict(name='checker-change-full-fallback',passed=result['status']=='VERIFIED' and
        result['counts']['reused']==0 and result['counts']['rechecked']==result['counts']['total']))
    changed_checker.unlink()
    restart = invoke_engine(baseline,selected,cache,key,out/'controls'/'cold-process-restart.json',base_id)
    summary['scenarios']['cold-process-restart'] = restart
    initial_warm = summary['scenarios']['no-change']['runs'][0]['incremental']['result']
    comparable = lambda r:[(d['index'],d['name'],d['status'],d['reason'],d['dependency_witness']) for d in r.get('decisions',[])]
    summary['gates'].append(dict(name='cold-process-restart-identical-decisions',passed=
        restart['result']['status']=='VERIFIED' and comparable(restart['result'])==comparable(initial_warm)))
    for name in [case[0] for case in cases]:
        pairs = summary['scenarios'][name]['runs']
        metrics = {}
        for mode in ('fresh','incremental'):
            metrics[mode] = {metric: statistics.median(p[mode]['resources'][metric] for p in pairs)
                             for metric in ('wall_seconds','cpu_seconds','max_rss_kib')}
        summary['scenarios'][name]['paired_resource_medians'] = metrics
        phase_medians = {}
        for mode in ('fresh','incremental'):
            phase_medians[mode] = {metric:statistics.median(p[mode]['result']['timings'][metric] for p in pairs if 'timings' in p[mode]['result'])
                for metric in ('identity_seconds','cache_validation_seconds','checking_seconds','total_seconds')
                if any('timings' in p[mode]['result'] for p in pairs)}
        summary['scenarios'][name]['verification_phase_medians'] = phase_medians
        summary['scenarios'][name]['incremental_wall_improvement_percent'] = 100*(1-metrics['incremental']['wall_seconds']/metrics['fresh']['wall_seconds'])
        export_process = manifest['variants'][dict(cases)[name]].get('export_process')
        if export_process:
            summary['scenarios'][name]['export_plus_verification_resources'] = {
                mode:dict(wall_seconds=metrics[mode]['wall_seconds']+export_process['wall_seconds'],
                          cpu_seconds=metrics[mode]['cpu_seconds']+export_process['cpu_seconds'],
                          max_rss_kib=max(metrics[mode]['max_rss_kib'],export_process['max_rss_kib']),
                          scope='sum/max of separately measured exporter and verifier; source build measured in workload manifest')
                for mode in ('fresh','incremental')}
            build_process = manifest['variants'][dict(cases)[name]]['build']
            summary['scenarios'][name]['build_export_verification_resources'] = {
                mode:dict(wall_seconds=metrics[mode]['wall_seconds']+export_process['wall_seconds']+build_process['wall_seconds'],
                          cpu_seconds=metrics[mode]['cpu_seconds']+export_process['cpu_seconds']+build_process['cpu_seconds'],
                          max_rss_kib=max(metrics[mode]['max_rss_kib'],export_process['max_rss_kib'],build_process['max_rss_kib']),
                          scope='sum/max of separately measured identical source build/export cost plus each verification arm')
                for mode in ('fresh','incremental')}
    summary['cache_resources'] = dict(
        bytes=sum(p.stat().st_size for p in cache.rglob('*') if p.is_file()),
        snapshot_bytes=sum(p.stat().st_size for p in (cache/'exports').glob('*') if p.is_file()),
        evidence_bytes=sum(p.stat().st_size for p in (cache/'records').glob('*') if p.is_file()),
        evidence_records=sum(1 for p in (cache/'records').glob('*') if p.is_file()))
    def invocation_protocols(value):
        if isinstance(value,dict):
            if 'protocol_valid' in value:
                yield (value['result_path'],value['protocol_valid'])
            for nested in value.values():
                yield from invocation_protocols(nested)
        elif isinstance(value,list):
            for nested in value:
                yield from invocation_protocols(nested)
    for path,valid in list(invocation_protocols(summary)):
        summary['gates'].append(dict(name='engine-exit-protocol:'+str(Path(path).relative_to(out)),passed=valid))
    summary['qualification_passed'] = all(g['passed'] for g in summary['gates'])
    summary['scope'] = ('Authenticated selected-obligation work reduction and exact-export oracle agreement. '
        'Timing medians are observations; edit speedup is not assumed. The bounded Lean theorem '
        'does not verify the NDJSON dependency extractor or production kernel locality.')
    write(out / 'summary.json', compact(summary))
    rows = ['# Incremental external checking qualification','',f"Qualification passed: **{summary['qualification_passed']}**",'',
            '| Edit | Full obligations | Rechecked | Reused | Fresh verify s | Incremental verify s | Fresh build+export+verify s | Incremental build+export+verify s |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name,_ in cases:
        entry = summary['scenarios'][name]
        result = entry['runs'][0]['incremental']['result']
        count = result.get('counts',{})
        metric = entry['paired_resource_medians']
        pipeline = entry.get('build_export_verification_resources')
        fresh_pipeline = f"{pipeline['fresh']['wall_seconds']:.3f}" if pipeline else 'boundary mutation'
        incremental_pipeline = f"{pipeline['incremental']['wall_seconds']:.3f}" if pipeline else 'boundary mutation'
        rows.append(f"| {name} | {count.get('total','?')} | {count.get('rechecked','?')} | {count.get('reused','?')} | {metric['fresh']['wall_seconds']:.3f} | {metric['incremental']['wall_seconds']:.3f} | {fresh_pipeline} | {incremental_pipeline} |")
    rows += ['',summary['scope'],'','Optional kernel statuses: '+', '.join(k+'='+v['status'] for k,v in summary['optional_kernels'].items()),'',
             'Failed gates: '+', '.join(g['name'] for g in summary['gates'] if not g['passed'])]
    (out/'summary.md').write_text('\n'.join(rows)+'\n')
    print(json.dumps({'qualification_passed':summary['qualification_passed'],'failed_gates':[g for g in summary['gates'] if not g['passed']]}),flush=True)
    return 0 if summary['qualification_passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workloads',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--checker',type=Path,default=REPO/'target/release/check-selected')
    parser.add_argument('--full-checker',type=Path,default=REPO/'target/release/sokonanoda')
    parser.add_argument('--authority-dir',type=Path)
    parser.add_argument('--repetitions',type=int,default=1)
    parser.add_argument('--optional-kernels',action='store_true')
    parser.add_argument('--optional-timeout',type=int,default=180)
    parser.add_argument('--identity-backend',choices=['python','native','differential'],default='python')
    parser.add_argument('--indexer',type=Path)
    options=parser.parse_args()
    if options.repetitions < 1:
        parser.error('--repetitions must be positive')
    if options.identity_backend != 'python' and options.indexer is None:
        parser.error('--indexer is required for native or differential identity')
    raise SystemExit(qualify(options))
