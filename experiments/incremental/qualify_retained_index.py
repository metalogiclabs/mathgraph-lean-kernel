#!/usr/bin/env python3
"""Independent retained SCC identity parity and paired measurement."""
import copy
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time
import unittest

import qualify_delta as q

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASELINE = '4496042c75368f6c35675a9b131c960080afa518'
VARIANTS = ('early-definition', 'unrelated-definition')


def validate_update(update, reference, mode, cone):
    if update.get('status') != 'indexed' or q.canonical(update.get('index')) != q.canonical(reference):
        raise ValueError('complete typed identity differs from independent full index')
    stats = update.get('finish_stats', {})
    expected_mode = 'retained' if mode == 'retained' else 'full'
    expected_reason = {'retained': None, 'full': 'forced_full_finish',
                       'retained-fallback': 'dependency_edges_changed'}[mode]
    if stats.get('mode') != expected_mode or stats.get('reason') != expected_reason:
        raise ValueError('unexpected retained/full mode or fallback reason')
    for name in ('compute_wall_seconds', 'compute_cpu_seconds', 'finish_wall_seconds', 'finish_cpu_seconds'):
        value = stats.get(name)
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise ValueError('missing or invalid compute duration: ' + name)
    if stats['finish_wall_seconds'] < stats['compute_wall_seconds']:
        raise ValueError('whole finish interval does not contain its core compute interval')
    for name in ('changed_sccs', 'affected_sccs', 'changed_declarations',
                 'affected_declarations', 'touched_declarations', 'total_declarations',
                 'total_sccs', 'closure_hashes', 'dependency_edges_touched'):
        if type(stats.get(name)) is not int or stats[name] < 0:
            raise ValueError('missing or invalid operation counter: ' + name)
    if stats['total_declarations'] != reference['count']:
        raise ValueError('counter graph size differs from independently indexed graph')
    if mode == 'retained':
        keys = stats.get('affected_keys')
        recomputed = stats.get('recomputed_sccs')
        if (not isinstance(keys, list) or len(keys) != len(set(keys)) or set(keys) != cone or
                stats['affected_declarations'] != len(cone) or
                stats['touched_declarations'] != len(cone) or
                not isinstance(recomputed, list) or len(recomputed) != len(set(recomputed)) or
                len(recomputed) != stats['affected_sccs'] or
                stats['closure_hashes'] != len(recomputed) or len(recomputed) > len(cone)):
            raise ValueError('retained work differs from independent affected cone')
    return stats


def completed(report, repetitions):
    if (report.get('run_completed') is not True or repetitions < 5 or
            not report.get('gates') or
            any(g.get('passed') is not True for g in report['gates'])):
        return False
    if any(report.get('controls', {}).get(name, {}).get('passed') is not True
           for name in report.get('required_controls', [])):
        return False
    expected = {(p, v, i) for p, v in report.get('required_pairs', [])
                for i in range(repetitions)}
    samples = report.get('samples', [])
    observed = [(s.get('profile'), s.get('variant'), s.get('repetition')) for s in samples]
    return (bool(expected) and len(observed) == len(set(observed)) and set(observed) == expected
            and all(s.get('passed') is True for s in samples))


def affected_cone(old, current):
    before = {d['key']: d for d in old['declarations']}
    after = {d['key']: d for d in current['declarations']}
    if set(before) != set(after):
        raise ValueError('comparison changed declaration universe')
    changed = {k for k in before if before[k]['own'] != after[k]['own']}
    reverse = {k: set() for k in before}
    for index in (before, after):
        for key, declaration in index.items():
            for dependency in declaration['deps']:
                if dependency in reverse:
                    reverse[dependency].add(key)
    cone, pending = set(changed), list(changed)
    while pending:
        for key in reverse[pending.pop()] - cone:
            cone.add(key); pending.append(key)
    return cone


def worker(spec_path):
    """An isolated interpreter imports the exact selected adapter package."""
    spec = json.loads(Path(spec_path).read_bytes())
    sys.path.insert(0, spec['adapter'])
    from producer_delta import DeltaSession, seal, engine as adapter_engine
    args = {k: spec[k] for k in ('root', 'workloads', 'producer', 'checker',
                                'indexer', 'index_session', 'authority_key')}
    if spec['arm'] != 'qualified449':
        args['identity_mode'] = spec['arm']
    lifecycle_cpu_start = adapter_engine.cpu_time()
    lifecycle_start = tick = time.perf_counter()
    session = DeltaSession(**args)
    closed = False
    constructor = time.perf_counter() - tick
    try:
        tick = time.perf_counter(); setup = session.start(); start = time.perf_counter() - tick
        if spec.get('control') == 'mode-boundary':
            def records():
                return {str(p): q.file_hash(p) for p in (session.root / 'cache/records').glob('*.json')}
            before = records()
            transaction = session.prepare(source_dir=Path(spec['workloads']) / 'early-definition/source',
                patch=q.EDITS['early-definition'], claimed_names=q.NAMES['early-definition'])
            payload = copy.deepcopy(transaction['attestation']['payload'])
            payload['provenance']['identity_finish'] = 'full'
            transaction['attestation'] = seal(payload, session.key)
            try:
                session.validate_apply(transaction)
            except ValueError as error:
                refusal = str(error)
                if refusal != 'transition environment/version/base mismatch':
                    raise
            else:
                raise ValueError('authenticated mode mismatch was accepted')
            if records() != before:
                raise ValueError('refused mode mismatch wrote an accepted receipt')
            try:
                session.validate_apply(transaction)
            except ValueError as error:
                poison_refusal = str(error)
                if poison_refusal != 'one baseline-anchored transaction per session':
                    raise
            else:
                raise ValueError('failed mode transaction did not poison the session')
            session.close()
            args['identity_mode'] = 'full'
            session = DeltaSession(**args)
            try:
                session.start()
            except ValueError as error:
                restart_refusal = str(error)
                if restart_refusal != 'source-owner genesis provenance mismatch':
                    raise
            else:
                raise ValueError('cross-mode restart accepted retained genesis')
            q.write(Path(spec['root']).parent / 'control.json', dict(passed=True,
                signed_mode_flip_refusal=refusal, failed_attempt_poison_refusal=poison_refusal,
                cross_mode_restart_refusal=restart_refusal, no_new_accepted_record=True))
            return
        tick = time.perf_counter()
        result = session.apply(source_dir=Path(spec['workloads']) / spec['variant'] / 'source',
            patch=q.EDITS[spec['variant']], claimed_names=q.NAMES[spec['variant']])
        elapsed = time.perf_counter() - tick
        lifecycle = time.perf_counter() - lifecycle_start
        lifecycle_cpu = session.cpu_time() - lifecycle_cpu_start
        directory = Path(spec['root']).parent
        q.write(directory / 'result.json', result)
        if result.get('status') != 'VERIFIED':
            raise ValueError('adapter arm did not verify: ' + str(result))
        sealed = q.sealed_snapshot(session.snapshot_path)
        full_config = directory / 'full-config.json'
        q.write(full_config, q.configuration(session.snapshot_path))
        direct, _ = q.command_run([spec['full_checker'], full_config], directory / 'direct-rust')
        if direct['returncode'] != 0 or direct['timed_out']:
            raise ValueError('fresh full Rust rejected the live exact sealed snapshot')
        # Materialization to a durable oracle file is AFTER the timed API call.
        shutil.copyfile(session.snapshot_path, directory / 'composite.ndjson')
        (directory / 'delta.ndjson').write_bytes(session.last_transaction['delta_bytes'])
        memory = session.memory_observation()
        close_cpu_start = session.cpu_time()
        close_start = time.perf_counter()
        session.close()
        closed = True
        close_wall = time.perf_counter() - close_start
        close_cpu = session.cpu_time() - close_cpu_start
        observed_lifecycle = time.perf_counter() - lifecycle_start
        q.write(directory / 'worker.json', dict(arm=spec['arm'], apply_wall_seconds=elapsed,
            constructor_wall_seconds=constructor, start_wall_seconds=start,
            constructor_through_apply_wall_seconds=lifecycle,
            constructor_through_apply_cpu_seconds=lifecycle_cpu,
            close_wall_seconds=close_wall, close_cpu_seconds=close_cpu,
            one_update_api_component_sum_wall_seconds=lifecycle + close_wall,
            one_update_api_component_sum_cpu_seconds=lifecycle_cpu + close_cpu,
            observed_constructor_through_close_wall_seconds=observed_lifecycle,
            close_scope='supported adapter close: terminate/wait daemons and remove private files; SIGTERM does not promise clean Rust EOF/destructor execution',
            lifecycle_scope='API component sum excludes later full-check/index/receipt oracles, result persistence by harness and snapshot copy; observed whole interval includes those executed before close',
            direct_rust=direct, setup=setup, sealed_snapshot=sealed, memory=memory,
            result_path=str(directory / 'result.json'),
            result_sha256=q.file_hash(directory / 'result.json'),
            delta_sha256=q.file_hash(directory / 'delta.ndjson')))
    finally:
        if not closed:
            session.close()


def direct_update(binary, baseline, delta, mode, directory, expected, cone, reference, old):
    """Roundtrip includes complete JSON decoding; Rust compute excludes JSON/IPC."""
    from producer_delta import JsonProcess
    directory.mkdir(parents=True, exist_ok=True)
    config = directory / 'config.json'; q.write(config, q.configuration(baseline))
    command = [binary, config] + (['--full-finish'] if mode == 'full' else [])
    tick = time.perf_counter(); process = JsonProcess(command, directory / 'stderr')
    try:
        ready = process.receive(); setup = time.perf_counter() - tick
        if ready.get('status') != 'ready' or q.canonical(ready.get('index')) != q.canonical(old):
            raise ValueError('index session did not establish baseline')
        tick = time.perf_counter(); update = process.request(dict(delta_path=str(delta)))
        roundtrip = time.perf_counter() - tick
        expected_mode = 'retained-fallback' if mode == 'retained' and expected == 'fallback' else mode
        stats = validate_update(update, reference, expected_mode, cone)
        if stats['finish_wall_seconds'] > roundtrip:
            raise ValueError('whole finish interval exceeds actual request roundtrip')
        q.write(directory / 'update.json', update)
        value = dict(command=[str(x) for x in command], setup_wall_seconds=setup,
            ready_identity_mode=ready.get('identity_mode'),
            baseline_prepare_wall_seconds=ready.get('prepare_wall_seconds'),
            ready_index_sha256=q.digest(ready.get('index')),
            update_index_sha256=q.digest(update['index']),
            roundtrip_wall_seconds=roundtrip,
            roundtrip_minus_compute_wall_seconds=roundtrip-stats['compute_wall_seconds'],
            roundtrip_minus_finish_wall_seconds=roundtrip-stats['finish_wall_seconds'],
            finish_stats=stats, response_path=str(directory / 'update.json'),
            response_sha256=q.file_hash(directory / 'update.json'))
        q.write(directory / 'measurement.json', value)
        return value
    finally:
        process.close()


def economics(samples, numerator, denominator):
    pairs = [dict(apply_wall_seconds=numerator(s), direct_wall_seconds=denominator(s))
             for s in samples]
    values = [p[k] for p in pairs for k in ('apply_wall_seconds', 'direct_wall_seconds')]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('invalid paired duration')
    if any(v == 0 for v in values):
        return dict(status='UNRESOLVED_CLOCK_GRANULARITY', passed=False, pairs=pairs,
                    scope='zero observations retained exactly; no substituted durations or speedup claim')
    value = q.paired_economics(pairs)
    value['scope'] = 'paired retained / named comparator and phase; lifecycle/component-sum phases include setup and supported shutdown'
    if len(pairs) < 5:
        value.update(status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS', passed=False)
    return value


def compress_completed(directory, store):
    """Only called after closed workers and all consumers of these files finish.

    Hashes bind the original bytes and deterministic gzip representation. Shared
    immutable compressed outputs use hardlinks; no live cache is ever linked.
    """
    store.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in sorted(directory.rglob('*')):
        if not path.is_file() or path.stat().st_size < 1_000_000 or path.suffix == '.gz':
            continue
        raw_sha, raw_bytes = q.file_hash(path), path.stat().st_size
        compressed = path.with_name(path.name + '.gz')
        with path.open('rb') as source, compressed.open('wb') as destination:
            with gzip.GzipFile(filename='', fileobj=destination, mode='wb', mtime=0) as target:
                shutil.copyfileobj(source, target)
        identity = q.file_hash(compressed)
        shared = store / (identity + '.gz')
        if shared.exists():
            if q.file_hash(shared) != identity:
                raise ValueError('immutable compressed evidence was corrupted')
            compressed.unlink(); os.link(shared, compressed)
        else:
            os.link(compressed, shared)
        entries.append(dict(original_path=str(path), original_sha256=raw_sha,
            original_bytes=raw_bytes, compressed_path=str(compressed),
            compressed_sha256=identity, compressed_bytes=compressed.stat().st_size,
            encoding='gzip', scope='completed immutable evidence; never reused as live input'))
        path.unlink()
    q.write(directory / 'compressed-evidence.json', entries)
    return entries


def run(args):
    for field in ('workloads', 'expanded_workloads', 'producer', 'checker', 'indexer',
                  'index_session', 'full_checker', 'authority_key', 'baseline_dir', 'out'):
        setattr(args, field, Path(getattr(args, field)).resolve())
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError('use a fresh output directory')
    args.out.mkdir(parents=True, exist_ok=True)
    if args.out == args.authority_key or args.out in args.authority_key.parents:
        raise ValueError('issuer secret must remain outside evidence')
    key = args.authority_key.read_bytes()
    if len(key) != 32:
        raise ValueError('issuer key must contain exactly32bytes')
    profiles = {'original': args.workloads, 'expanded': args.expanded_workloads}
    report = dict(schema='mathgraph.retained-index-qualification.v1',
        source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        source_worktree_tracked_clean=subprocess.run(['git', 'diff', '--quiet', '--', 'src',
            'experiments/incremental', '.github/workflows/incremental-retained-index.yml'], cwd=REPO).returncode == 0,
        harness_sha256=q.file_hash(__file__), baseline_source=BASELINE,
        run_completed=False, correctness_passed=False, qualification_status='IN_PROGRESS',
        repetitions=args.repetitions, host=dict(uname=list(platform.uname()),
            cpu_model=next((s.split(':', 1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines()
                            if s.startswith('model name')), None)),
        required_pairs=[[p, v] for p in profiles for v in VARIANTS],
        required_controls=[p + ':mode-boundary' for p in profiles], controls={},
        measurement_policy=dict(one_baseline_anchored_update_per_process=True,
            arm_order='alternating qualified449/full/retained and reverse by repetition',
            standalone_order='alternating full/retained and reverse by repetition',
            caches='OS file cache warm; fresh sessions per arm; no host/profile pooling',
            compute='Rust finish/reclosure only, after row mutation, before full-index JSON serialization',
            finish='whole postparse finish call, including statistics construction and destructors reached there; retained lifetime anchor is accounted in actual adapter shutdown',
            forced_full_observation_overhead='full compute timer is the untouched historical algorithm; forced-full wholefinish additionally constructs O(N) observation counters/keys. Preserved449 adapter arm is the primary actual historical end-to-end comparator.',
            ipc='roundtrip includes Rust compute, full-index serialization, pipe transport and Python decode; difference is residual, not pure IPC',
            lifecycle='actual constructor through completed apply plus separately measured supported SIGTERM close, one update; per-sample API component sums, no hypothetical multi-update amortization',
            memory='post-phase procfs samples; cumulative VmHWM, no exact phase peak or aggregate RSS'),
        baseline_package={}, tools={}, references={}, gates=[], samples=[])
    def flush():
        report['correctness_passed'] = completed(report, args.repetitions)
        report['qualification_status'] = ('PASS' if report['correctness_passed'] else
            'FAIL' if any(g['passed'] is False for g in report['gates']) else
            'IN_PROGRESS' if not report['run_completed'] else 'INCOMPLETE')
        q.write(args.out / 'summary.json', report)
    def gate(name, condition):
        report['gates'].append(dict(name=name, passed=bool(condition), required=True))
        flush()
        if not condition:
            raise ValueError('required qualification gate failed: ' + name)
    baseline_package = args.baseline_dir / 'incremental'
    # Verify the actual imported source files, rather than trusting directory names.
    for name in ('producer_delta.py', 'engine.py', 'build_workloads.py', 'process.py',
                 'pins.json', 'delta-pins.json', 'expanded-roots.json'):
        expected = subprocess.check_output(['git', 'show', BASELINE + ':experiments/incremental/' + name], cwd=REPO)
        actual = (baseline_package / name).read_bytes()
        gate('qualified449_exact_source:' + name, actual == expected)
        report['baseline_package'][name] = hashlib.sha256(actual).hexdigest()
    for name in ('producer', 'checker', 'indexer', 'index_session', 'full_checker'):
        path = getattr(args, name)
        report['tools'][name] = dict(path=str(path), sha256=q.file_hash(path))
    for name in ('index-session', 'export-index', 'check-selected', 'sokonanoda'):
        path = args.baseline_dir / 'bin' / name
        report['tools']['qualified449_' + name] = dict(path=str(path), sha256=q.file_hash(path))
    stable_sources = [HERE / name for name in ('producer_delta.py', 'qualify_delta.py',
        'engine.py', 'qualify_retained_index.py', 'replay_retained_index.py', 'pins.json', 'delta-pins.json')]
    stable_sources += [REPO / name for name in ('src/identity.rs', 'src/parser.rs', 'src/bin/index_session.rs')]
    stable_sources += sorted((REPO / 'src/identity').glob('*.rs'))
    report['measured_source_sha256'] = {str(p.relative_to(REPO)): q.file_hash(p) for p in stable_sources}
    flush()
    try:
        for profile, workloads in profiles.items():
            manifest = json.loads((workloads / 'manifest.json').read_bytes())
            references = {}
            report['references'][profile] = {}
            for variant in ('baseline', *[v for v in VARIANTS if v != 'baseline']):
                export = Path(manifest['variants'][variant]['path'])
                native, resource = q.fresh_index(export, args.indexer,
                    args.out / 'references' / profile / variant / 'native')
                python, _ = q.fresh_index(export, args.indexer,
                    args.out / 'references' / profile / variant / 'python', python=True)
                gate('independent_python_native_exact:' + profile + ':' + variant,
                     q.canonical(native) == q.canonical(python))
                references[variant] = native
                report['references'][profile][variant] = dict(export_sha256=q.file_hash(export),
                    index_sha256=q.digest(native), count=native['count'], native=resource)
            report['references'][profile]['compressed_evidence'] = compress_completed(
                args.out / 'references' / profile, args.out / 'immutable-gzip')
            control = args.out / 'controls' / profile / 'mode-boundary'
            control.mkdir(parents=True, exist_ok=True)
            spec = dict(root=str(control / 'session'), workloads=str(workloads),
                producer=str(args.producer), checker=str(args.checker), indexer=str(args.indexer),
                index_session=str(args.index_session), full_checker=str(args.full_checker),
                authority_key=str(args.authority_key), adapter=str(HERE),
                arm='retained', variant='early-definition', control='mode-boundary')
            q.write(control / 'worker-spec.json', spec)
            record, _ = q.command_run([sys.executable, __file__, '--worker', control / 'worker-spec.json'], control / 'process')
            gate('mode_boundary_control_process:' + profile, record['returncode'] == 0 and not record['timed_out'])
            report['controls'][profile + ':mode-boundary'] = json.loads((control / 'control.json').read_bytes())
            report['controls'][profile + ':mode-boundary']['compressed_evidence'] = compress_completed(control, args.out / 'immutable-gzip')
            for variant in VARIANTS:
                reference, old = references[variant], references['baseline']
                cone = affected_cone(old, reference)
                for repetition in range(args.repetitions):
                    sample = dict(profile=profile, variant=variant, repetition=repetition,
                        passed=False, cone_keys=sorted(cone), cone_count=len(cone), arms={}, standalone={})
                    report['samples'].append(sample); flush()
                    directory = args.out / 'samples' / profile / f'{variant}-{repetition}'
                    order = ['qualified449', 'full', 'retained']
                    if repetition % 2:
                        order.reverse()
                    sample['arm_order'] = order
                    outputs, partitions = {}, {}
                    for arm in order:
                        output = directory / arm; output.mkdir(parents=True, exist_ok=True)
                        prior = arm == 'qualified449'
                        spec = dict(root=str(output / 'session'), workloads=str(workloads),
                            producer=str(args.producer), checker=str(args.baseline_dir / 'bin/check-selected' if prior else args.checker),
                            indexer=str(args.baseline_dir / 'bin/export-index' if prior else args.indexer),
                            index_session=str(args.baseline_dir / 'bin/index-session' if prior else args.index_session),
                            full_checker=str(args.baseline_dir / 'bin/sokonanoda' if prior else args.full_checker),
                            authority_key=str(args.authority_key), adapter=str(baseline_package if prior else HERE),
                            arm=arm, variant=variant)
                        spec_path = output / 'worker-spec.json'; q.write(spec_path, spec)
                        process, _ = q.command_run([sys.executable, __file__, '--worker', spec_path], output / 'worker-process')
                        gate(f'worker_completed:{profile}:{variant}:{repetition}:{arm}',
                             process['returncode'] == 0 and not process['timed_out'])
                        result = json.loads((output / 'result.json').read_bytes())
                        observed = json.loads((output / 'worker.json').read_bytes())
                        native, _ = q.fresh_index(output / 'composite.ndjson', args.indexer, output / 'full-native')
                        gate(f'full_identity_exact:{profile}:{variant}:{repetition}:{arm}',
                             q.canonical(native) == q.canonical(reference))
                        partition = q.audit_partition(result, old, native)
                        receipt = q.audit_receipt(output / 'session', result, native, key)
                        outputs[arm], partitions[arm] = result, partition
                        observed.update(partition=partition, receipt_audit=receipt,
                            timings=result['timings'], typed_update=result['typed_update'],
                            counts=result['counts'], memory=result['memory'],
                            index_sha256=q.digest(native), result_status=result['status'])
                        sample['arms'][arm] = observed
                    gate(f'exact_pair_delta_and_export:{profile}:{variant}:{repetition}',
                        len({a['delta_sha256'] for a in sample['arms'].values()}) == 1 and
                        len({r['export_sha256'] for r in outputs.values()}) == 1)
                    gate(f'partition_and_kernel_verdict_parity:{profile}:{variant}:{repetition}',
                         len({q.digest(p) for p in partitions.values()}) == 1 and
                         all(r['checker_result']['code'] == 0 for r in outputs.values()))
                    standalone_order = ['full', 'retained'] if repetition % 2 == 0 else ['retained', 'full']
                    for mode in standalone_order:
                        sample['standalone'][mode] = direct_update(args.index_session,
                            Path(manifest['variants']['baseline']['path']), directory / 'retained/delta.ndjson',
                            mode, directory / ('standalone-' + mode),
                            'fallback' if variant == 'theorem-leaf' else 'retained', cone, reference, old)
                    sample['compressed_evidence'] = compress_completed(directory, args.out / 'immutable-gzip')
                    compressed = {e['original_path']: e for e in sample['compressed_evidence']}
                    for record in [*sample['arms'].values(), *sample['standalone'].values()]:
                        for field in ('result_path', 'response_path'):
                            if record.get(field) in compressed:
                                record[field + '_compressed_evidence'] = compressed[record[field]]
                    sample['passed'] = True; flush()
        report['economics'] = {}
        for profile in profiles:
            report['economics'][profile] = {}
            for variant in VARIANTS:
                rows = [s for s in report['samples'] if s['profile'] == profile and s['variant'] == variant]
                named = {}
                for arm in ('full', 'qualified449'):
                    for phase in ('apply_wall_seconds', 'constructor_through_apply_wall_seconds',
                                  'constructor_through_apply_cpu_seconds', 'close_wall_seconds',
                                  'one_update_api_component_sum_wall_seconds',
                                  'one_update_api_component_sum_cpu_seconds'):
                        named['retained_vs_' + arm + ':' + phase] = economics(rows,
                            lambda s, p=phase: s['arms']['retained'][p],
                            lambda s, a=arm, p=phase: s['arms'][a][p])
                named['retained_vs_direct_fresh_rust'] = economics(rows,
                    lambda s: s['arms']['retained']['apply_wall_seconds'],
                    lambda s: s['arms']['retained']['direct_rust']['wall_seconds'])
                for field in ('compute_wall_seconds', 'compute_cpu_seconds', 'finish_wall_seconds', 'finish_cpu_seconds'):
                    named['retained_vs_full:' + field] = economics(rows,
                        lambda s, f=field: s['standalone']['retained']['finish_stats'][f],
                        lambda s, f=field: s['standalone']['full']['finish_stats'][f])
                named['retained_vs_full:index_roundtrip'] = economics(rows,
                    lambda s: s['standalone']['retained']['roundtrip_wall_seconds'],
                    lambda s: s['standalone']['full']['roundtrip_wall_seconds'])
                named['phase_medians'] = {}
                for arm in ('qualified449', 'full', 'retained'):
                    timings = [s['arms'][arm]['timings'] for s in rows]
                    fields = set.intersection(*(set(t) for t in timings))
                    named['phase_medians'][arm] = {f: statistics.median(t[f] for t in timings)
                        for f in sorted(fields) if all(type(t[f]) in (int, float) and math.isfinite(t[f]) for t in timings)}
                    for f in ('constructor_wall_seconds', 'start_wall_seconds', 'close_wall_seconds',
                              'close_cpu_seconds', 'constructor_through_apply_wall_seconds',
                              'constructor_through_apply_cpu_seconds',
                              'one_update_api_component_sum_wall_seconds', 'one_update_api_component_sum_cpu_seconds'):
                        named['phase_medians'][arm][f] = statistics.median(s['arms'][arm][f] for s in rows)
                report['economics'][profile][variant] = named
        report['same_cone_scaling'] = {}
        for variant in ('early-definition', 'unrelated-definition'):
            rows = {p: [s for s in report['samples'] if s['profile'] == p and s['variant'] == variant] for p in profiles}
            gate('same_identity_cone:' + variant,
                 {tuple(s['cone_keys']) for s in rows['original']} == {tuple(s['cone_keys']) for s in rows['expanded']})
            fields = ('affected_declarations', 'affected_sccs', 'closure_hashes', 'touched_declarations', 'dependency_edges_touched')
            operation_counts = {p: [{f: s['standalone']['retained']['finish_stats'][f] for f in fields}
                                   for s in samples] for p, samples in rows.items()}
            gate('same_retained_operation_counts:' + variant,
                 len({q.digest(v) for values in operation_counts.values() for v in values}) == 1)
            medians = {p: statistics.median(s['standalone']['retained']['finish_stats']['compute_wall_seconds']
                                           for s in samples) for p, samples in rows.items()}
            finish_medians = {p: statistics.median(s['standalone']['retained']['finish_stats']['finish_wall_seconds']
                                                  for s in samples) for p, samples in rows.items()}
            report['same_cone_scaling'][variant] = dict(operation_counts=operation_counts,
                compute_wall_medians=medians, expanded_over_original_compute_wall_ratio=medians['expanded']/medians['original'],
                finish_wall_medians=finish_medians,
                expanded_over_original_finish_wall_ratio=finish_medians['expanded']/finish_medians['original'],
                scope='identity finish only; complete-index JSON, row parsing, adapter, full selected-parser and persistence remain outside this cone claim')
        gate('measured_source_stable', all(q.file_hash(REPO / p) == h for p, h in report['measured_source_sha256'].items()))
        gate('measured_tool_bytes_stable', all(q.file_hash(t['path']) == t['sha256'] for t in report['tools'].values()))
        report['run_completed'] = True
        flush()
    except Exception as error:
        report['error'] = repr(error)
        report['gates'].append(dict(name='run_finished', passed=False, required=True, detail=repr(error)))
        flush()
        raise
    q.write(args.out / 'compact.json', report)
    lines = ['Retained index qualification: ' + report['qualification_status'], '',
        'Two pinned environments; early cone3 and unrelated cone1. Five paired repetitions required.',
        'Reclosure compute, whole finish, complete JSON roundtrip, warm adapter, and one-update lifecycle are separate measurements.',
        'Shutdown uses the supported SIGTERM/wait API. No multi-update amortization or aggregate memory claim.', '',
        'Forced-full wholefinish includes observation-only counters; its core compute is the untouched historical algorithm. The preserved449 adapter is the primary historical comparator.', '',
        '| Profile / edit | Warm vs449 ratio | Warm vs full ratio | One-update API sum vs449 ratio |',
        '| --- | ---: | ---: | ---: |']
    for profile, variants in report['economics'].items():
        for variant, values in variants.items():
            keys = ('retained_vs_qualified449:apply_wall_seconds', 'retained_vs_full:apply_wall_seconds',
                    'retained_vs_qualified449:one_update_api_component_sum_wall_seconds')
            ratios = [values[k].get('median_ratio') for k in keys]
            lines.append('| ' + profile + ' / ' + variant + ' | ' + ' | '.join(
                f'{value:.4f}' if value is not None else 'unresolved' for value in ratios) + ' |')
    (args.out / 'summary.md').write_text('\n'.join(lines) + '\n')
    return 0 if report['correctness_passed'] else 1


def self_test():
    class EvidenceTests(unittest.TestCase):
        def setUp(self):
            self.reference = {'declarations': [{'key': 'a', 'own': 'own',
                'deps': ['b'], 'closure': 'closure'}], 'count': 1}
            self.good = {'status': 'indexed', 'index': self.reference,
                'finish_stats': {'mode': 'retained', 'reason': None,
                    'affected_keys': ['a'], 'affected_declarations': 1,
                    'changed_declarations': 1, 'touched_declarations': 1,
                    'changed_sccs': 1, 'affected_sccs': 1, 'closure_hashes': 1,
                    'total_declarations': 1, 'total_sccs': 1,
                    'dependency_edges_touched': 1, 'recomputed_sccs': [0],
                    'compute_wall_seconds': 0.001, 'compute_cpu_seconds': 0.001,
                    'finish_wall_seconds': 0.002, 'finish_cpu_seconds': 0.002}}

        def test_complete_identity_is_required(self):
            validate_update(self.good, self.reference, 'retained', {'a'})
            for field in ('own', 'deps', 'closure'):
                update = copy.deepcopy(self.good)
                update['index']['declarations'][0][field] = 'wrong'
                with self.assertRaises(ValueError):
                    validate_update(update, self.reference, 'retained', {'a'})

        def test_retained_claim_requires_exact_affected_cone(self):
            update = copy.deepcopy(self.good)
            update['finish_stats']['affected_keys'] = []
            with self.assertRaises(ValueError):
                validate_update(update, self.reference, 'retained', {'a'})

        def test_missing_nonfinite_and_boolean_measurements_fail(self):
            for bad in (None, float('nan'), -1, True):
                update = copy.deepcopy(self.good)
                update['finish_stats']['compute_wall_seconds'] = bad
                with self.assertRaises(ValueError):
                    validate_update(update, self.reference, 'retained', {'a'})

        def test_silent_full_fallback_cannot_qualify_retained(self):
            update = copy.deepcopy(self.good)
            update['finish_stats'].update(mode='full', reason='dependency_edges_changed')
            with self.assertRaises(ValueError):
                validate_update(update, self.reference, 'retained', {'a'})

        def test_empty_partial_duplicate_and_failed_reports_fail_closed(self):
            sample = dict(profile='original', variant='theorem-leaf', repetition=0,
                          passed=True)
            report = dict(run_completed=True, required_pairs=[['original', 'theorem-leaf']],
                          samples=[sample], gates=[dict(passed=True)])
            self.assertFalse(completed(report, 5))
            report['samples'] = [dict(sample, repetition=i) for i in range(5)]
            self.assertTrue(completed(report, 5))
            report['required_controls'] = ['mode-boundary']
            self.assertFalse(completed(report, 5))
            report['controls'] = {'mode-boundary': {'passed': True}}
            self.assertTrue(completed(report, 5))
            for field, value in [('run_completed', False), ('samples', []),
                                 ('gates', []), ('samples', [sample] * 5),
                                 ('gates', [dict(passed=False)])]:
                bad = copy.deepcopy(report); bad[field] = value
                self.assertFalse(completed(bad, 5))

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceTests)
    return unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        raise SystemExit(0 if self_test() else 1)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        raise SystemExit(0)
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('workloads', 'expanded-workloads', 'producer', 'checker', 'indexer',
                 'index-session', 'full-checker', 'authority-key', 'baseline-dir', 'out'):
        parser.add_argument('--' + flag, required=True, type=Path)
    parser.add_argument('--repetitions', type=int, default=5)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error('--repetitions must be positive; qualification requires at least5')
    raise SystemExit(run(args))
