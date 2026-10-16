#!/usr/bin/env python3
"""Paired whole-process native-index economics, separate from correctness.

The frozen Python engine is copied verbatim from Git, not reimplemented here.
Every command, result, receipt, resource record and execution order is retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import tempfile

from process import run, sha256
from qualify_native import configuration, pinned_manifest, projection, write

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASELINE_REF = '9ac04033b51703fb135ec3c28621d44b183944fe'
HISTORICAL_BINARIES = {
    'check-selected': '869dbda8a8e2807c194b7937391cc659cfa437fc42bc365d51ec5c8f8cf2009d',
    'sokonanoda': 'c4523b615807d30cb9bbae426524af42eb31e1a90c79cc7a7a9dee8ac7ff9673',
}
VARIANTS = ('baseline', 'early-definition', 'unrelated-definition',
            'theorem-leaf', 'invalid-proof', 'axiom-type')
ARMS = ('baseline-python-full', 'baseline-python-incremental',
        'native-full', 'native-incremental', 'baseline-direct-full', 'current-direct-full')
PRIMARY = ('early-definition', 'unrelated-definition')
RANDOM_SEED = 20261016
BOOTSTRAP_REPETITIONS = 10000


def numeric_timings(result):
    """Preserve every numeric root phase, without mistaking booleans for times."""
    return {name: value for name, value in result.get('timings', {}).items()
            if type(value) in (int, float)}


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True).encode()).hexdigest()


def git_bytes(ref, path):
    return subprocess.check_output(['git', 'show', ref + ':' + path], cwd=REPO)


def capture(source, target, executable=False):
    """Freeze the exact measured bytes while other work may rebuild binaries."""
    before = sha256(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(0o500 if executable else 0o400)
    captured = sha256(target)
    if before != captured or sha256(source) != captured:
        raise ValueError('source changed during benchmark capture: ' + str(source))
    return dict(source_path=str(source), captured_path=str(target), sha256=captured)


def resource_medians(records):
    return {name: statistics.median(record['resources'][name] for record in records)
            for name in ('wall_seconds', 'cpu_seconds', 'max_rss_kib')}


def paired_economics(pairs, seed=RANDOM_SEED):
    """A prespecified strict median, paired-majority and bootstrap rule.

    The deterministic nonparametric bootstrap resamples complete pairs and
    computes a ratio of medians. Its percentile upper bound measures repeat
    stability on this host, not generalization to other machines/workloads.
    """
    native = [pair['native_wall_seconds'] for pair in pairs]
    direct = [pair['direct_wall_seconds'] for pair in pairs]
    ratio = statistics.median(native) / statistics.median(direct)
    rng = random.Random(seed)
    ratios = []
    for _ in range(BOOTSTRAP_REPETITIONS):
        indices = [rng.randrange(len(pairs)) for _ in pairs]
        ratios.append(statistics.median(native[i] for i in indices) /
                      statistics.median(direct[i] for i in indices))
    ratios.sort()
    lower = ratios[int(0.025 * (len(ratios) - 1))]
    upper = ratios[int(0.975 * (len(ratios) - 1))]
    wins = sum(left < right for left, right in zip(native, direct))
    return dict(pairs=pairs, native_median_wall_seconds=statistics.median(native),
                direct_median_wall_seconds=statistics.median(direct),
                median_ratio=ratio, paired_wins=wins, paired_count=len(pairs),
                bootstrap_ratio_interval_95=[lower, upper],
                bootstrap_repetitions=BOOTSTRAP_REPETITIONS, bootstrap_seed=seed,
                median_lower=ratio < 1, paired_majority=wins > len(pairs) / 2,
                bootstrap_upper_lower=upper < 1,
                passed=ratio < 1 and wins > len(pairs) / 2 and upper < 1)


def engine_command(script, export, checker, cache, key, output, indexer=None,
                   previous=None, disable=False):
    command = [sys.executable, str(script), '--export', str(export),
               '--checker', str(checker), '--cache', str(cache),
               '--authority-key', str(key), '--output', str(output)]
    if indexer is not None:
        command += ['--identity-backend', 'native', '--indexer', str(indexer)]
    if previous is not None:
        command += ['--previous', previous]
    if disable:
        command += ['--disable-cache']
    return command


def measure_engine(command, output):
    resources = run(command, output.with_name(output.stem + '-process'), timeout=900)
    result = json.loads(output.read_text()) if output.is_file() else dict(status='MISSING_RESULT')
    protocol = (not resources['timed_out'] and resources['returncode'] ==
                {'VERIFIED': 0, 'REJECTED': 1, 'UNKNOWN': 2}.get(result.get('status')))
    semantic = projection(result)
    return dict(resources=resources, result_path=str(output),
                result_sha256=sha256(output) if output.is_file() else None,
                protocol_valid=protocol, status=result.get('status'),
                evidence_id=result.get('evidence_id'), counts=result.get('counts'),
                phases=numeric_timings(result), projection_sha256=object_hash(semantic),
                identity_backend=result.get('identity_backend')), semantic


def measurement_table(samples):
    table = {}
    for variant in VARIANTS:
        table[variant] = {}
        for arm in ARMS:
            records = [sample for sample in samples
                       if sample['variant'] == variant and sample['arm'] == arm]
            phases = sorted({phase for record in records for phase in record.get('phases', {})})
            table[variant][arm] = dict(
                resources=resource_medians(records),
                phases={phase: statistics.median(record['phases'][phase] for record in records
                                                 if phase in record.get('phases', {}))
                        for phase in phases},
                statuses=[record['status'] for record in records], repetitions=len(records))
    return table


def build_export_resources(manifest):
    """Keep construction outside timed verification; totals explicitly add parts."""
    result = {}
    for variant in VARIANTS:
        info = manifest['variants'][variant]
        resources = {name: info[name] for name in ('build', 'export_process') if name in info}
        construction = {metric: sum(record[metric] for record in resources.values())
                        for metric in ('wall_seconds', 'cpu_seconds')}
        result[variant] = dict(processes=resources, construction_sum=construction,
                               source_build_available='build' in info,
                               mutation=info.get('mutation'),
                               note='NDJSON mutation; no independent source build/export' if
                               not resources else 'build and export are separately measured commands')
    return result


def markdown(report):
    rows = ['# Native identity-index whole-process benchmark', '',
            '**Correctness:** ' + ('PASS' if report['correctness_passed'] else 'FAIL') +
            '. **Economic result:** ' + report['economic_status'] + '.', '',
            'Median fresh-process measurements; seconds and KiB. Raw logs and all '
            'repetitions are retained in `summary.json` and per-command files.', '',
            '| Variant | Arm | Wall | CPU | Peak RSS |', '| --- | --- | ---: | ---: | ---: |']
    for variant, arms in report['medians'].items():
        for arm, entry in arms.items():
            resources = entry['resources']
            rows.append(f"| {variant} | {arm} | {resources['wall_seconds']:.6f} | "
                        f"{resources['cpu_seconds']:.6f} | {resources['max_rss_kib']:.0f} |")
    rows += ['', '| Primary variant | Native/direct median ratio | Paired wins | '
             'Bootstrap 95% interval | Economic gate |', '| --- | ---: | ---: | --- | --- |']
    for variant, value in report['economics'].items():
        interval = value['bootstrap_ratio_interval_95']
        rows.append(f"| {variant} | {value['median_ratio']:.4f} | "
                    f"{value['paired_wins']}/{value['paired_count']} | "
                    f"[{interval[0]:.4f}, {interval[1]:.4f}] | "
                    f"{'PASS' if value['passed'] else 'NO_SPEEDUP'} |")
    rows += ['', 'The prespecified rule requires a lower median, a strict majority of '
             'paired wins and a paired-bootstrap 95% upper ratio bound below one for '
             'both primary edits. The comparison uses current direct raw full checking.', '',
             'Baseline seeding is separate from timed incremental verification. Build/export '
             'resources and component-addition totals are reported separately; those sums '
             'are not new single-command measurements. Bootstrap stability on this finite '
             'run does not establish cross-host or Mathlib-scale speedup.', '',
             'Failed correctness gates: ' + ', '.join(gate['name'] for gate in report['gates']
                                                       if not gate['passed'])]
    return '\n'.join(rows) + '\n'


def benchmark(args):
    workloads, out = args.workloads.resolve(), args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('use a fresh benchmark output directory')
    out.mkdir(parents=True, exist_ok=True)
    manifest, pins = pinned_manifest(workloads)
    resolved_baseline = subprocess.check_output(
        ['git', 'rev-parse', args.baseline_ref + '^{commit}'], cwd=REPO, text=True).strip()
    if resolved_baseline != BASELINE_REF:
        raise ValueError('benchmark original implementation must be pinned to ' + BASELINE_REF)
    baseline_bins = args.baseline_bin.resolve()
    old_selected, old_full = baseline_bins / 'check-selected', baseline_bins / 'sokonanoda'
    selected, full, indexer = args.checker.resolve(), args.full_checker.resolve(), args.indexer.resolve()
    source_ref = baseline_bins / 'source-ref.txt'
    if source_ref.exists() and source_ref.read_text().strip() != BASELINE_REF:
        raise ValueError('baseline binary source-ref does not match the frozen implementation')
    for binary in (old_selected, old_full, selected, full, indexer):
        if not binary.is_file():
            raise ValueError('missing benchmark binary: ' + str(binary))
    baseline_source = out / 'baseline-source' / 'engine.py'
    baseline_source.parent.mkdir(parents=True)
    baseline_source.write_bytes(git_bytes(BASELINE_REF, 'experiments/incremental/engine.py'))
    baseline_provenance_path = baseline_bins / 'provenance.json'
    baseline_provenance = None
    if baseline_provenance_path.is_file():
        baseline_provenance = json.loads(baseline_provenance_path.read_text())
        if baseline_provenance['source_commit'] != BASELINE_REF:
            raise ValueError('baseline provenance source commit does not match original implementation')
        for name in ('check-selected', 'sokonanoda', 'engine.py'):
            path = baseline_source if name == 'engine.py' else baseline_bins / name
            if sha256(path) != baseline_provenance['files'][name]['sha256']:
                raise ValueError('baseline provenance digest mismatch: ' + name)
        shutil.copyfile(baseline_provenance_path, baseline_source.parent / 'provenance.json')
    source_snapshot = capture(HERE / 'engine.py', out / 'source-snapshot' / 'engine.py')
    source_binaries = (old_selected, old_full, selected, full, indexer)
    captured_tools = {}
    captured_paths = []
    for name, source in zip(('baseline-check-selected', 'baseline-sokonanoda',
                             'current-check-selected', 'current-sokonanoda', 'export-index'), source_binaries):
        target = out / 'captured-tools' / name
        captured_tools[name] = capture(source, target, executable=True)
        captured_paths.append(target)
    old_selected, old_full, selected, full, indexer = captured_paths
    authority_temp = None
    if args.authority_dir:
        authority = args.authority_dir.resolve()
    else:
        authority_temp = tempfile.TemporaryDirectory(prefix='native-benchmark-authority-')
        authority = Path(authority_temp.name).resolve()
    published_roots = [out, workloads] + [ancestor for ancestor in out.parents
                                        if ancestor.name == 'artifacts']
    if any(authority == root or root in authority.parents for root in published_roots):
        raise ValueError('authority keys must remain outside published artifacts and workloads')
    authority.mkdir(parents=True, exist_ok=True)
    report = dict(schema='mathgraph.incremental-native-benchmark.v1',
        source_git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        baseline_ref=BASELINE_REF, baseline_source_path=str(baseline_source),
        baseline_source_sha256=sha256(baseline_source),
        workload_manifest_sha256=sha256(workloads / 'manifest.json'), pins=pins,
        harness_sources_sha256={name: sha256(HERE / name) for name in
                               ('benchmark_native.py', 'qualify_native.py', 'process.py', 'engine.py')},
        binary_sha256={entry['source_path']: entry['sha256'] for entry in captured_tools.values()},
        captured_tools=captured_tools, current_engine_snapshot=source_snapshot,
        historical_baseline_binary_sha256=HISTORICAL_BINARIES,
        historical_baseline_binary_matches={name: sha256(baseline_bins / name) == expected
                                            for name, expected in HISTORICAL_BINARIES.items()},
        baseline_binary_source_ref=str(source_ref) if source_ref.exists() else None,
        baseline_binary_provenance=baseline_provenance,
        repetitions=args.repetitions, random_seed=RANDOM_SEED, arms=list(ARMS),
        variants=list(VARIANTS), execution_order=[], seeds=[], samples=[], gates=[],
        construction=build_export_resources(manifest),
        economic_rule='For both early-definition and unrelated-definition: native-incremental '
        'median wall < current-direct-full median wall, strict paired-win majority, '
        'and deterministic paired-bootstrap 95% upper ratio-of-medians bound < 1.')
    baseline_export = Path(manifest['variants']['baseline']['path'])
    rng = random.Random(RANDOM_SEED)
    try:
        for repetition in range(args.repetitions):
            seeded = {}
            backend_order = ['baseline-python', 'native']
            rng.shuffle(backend_order)
            report['execution_order'].append(dict(repetition=repetition, phase='seed', order=backend_order))
            for backend in backend_order:
                seed_dir = out / 'seeds' / str(repetition) / backend
                seed_dir.mkdir(parents=True, exist_ok=True)
                script = baseline_source if backend == 'baseline-python' else HERE / 'engine.py'
                checker = old_selected if backend == 'baseline-python' else selected
                native_indexer = None if backend == 'baseline-python' else indexer
                key = authority / f'{repetition}-{backend}.key'
                initialized = run([sys.executable, str(script), '--init-key', str(key)], seed_dir / 'init-key')
                if initialized['returncode']:
                    raise RuntimeError('fresh authority initialization failed')
                output, cache = seed_dir / 'baseline.json', seed_dir / 'cache'
                command = engine_command(script, baseline_export, checker, cache, key,
                                         output, indexer=native_indexer, disable=True)
                seed, _ = measure_engine(command, output)
                seed.update(repetition=repetition, backend=backend, key_initialization=initialized)
                report['seeds'].append(seed)
                passed = seed['protocol_valid'] and seed['status'] == 'VERIFIED' and bool(seed['evidence_id'])
                report['gates'].append(dict(name=f'{repetition}-{backend}-seed', passed=passed))
                if not passed:
                    write(out / 'partial.json', report)
                    raise RuntimeError('baseline seeding failed; inspect retained process evidence')
                seeded[backend] = dict(script=script, checker=checker, indexer=native_indexer,
                                       cache=cache, key=key, previous=seed['evidence_id'])
            jobs = [(variant, arm) for variant in VARIANTS for arm in ARMS]
            rng.shuffle(jobs)
            report['execution_order'].append(dict(repetition=repetition, phase='measurement',
                                                  order=[dict(variant=v, arm=a) for v, a in jobs]))
            semantics = {}
            for position, (variant, arm) in enumerate(jobs):
                export = Path(manifest['variants'][variant]['path'])
                expected = 'REJECTED' if variant in ('invalid-proof', 'axiom-type') else 'VERIFIED'
                directory = out / 'samples' / str(repetition) / variant / arm
                directory.mkdir(parents=True, exist_ok=True)
                if arm.endswith('direct-full'):
                    config_path = directory / 'config.json'
                    write(config_path, configuration(export))
                    binary = old_full if arm == 'baseline-direct-full' else full
                    resources = run([str(binary), str(config_path)], directory / 'process', timeout=900)
                    protocol = not resources['timed_out'] and resources['returncode'] in (0, 1)
                    sample = dict(resources=resources, protocol_valid=protocol,
                                  status={0: 'VERIFIED', 1: 'REJECTED'}.get(resources['returncode'], 'UNKNOWN'))
                else:
                    backend = 'baseline-python' if arm.startswith('baseline-python') else 'native'
                    seed = seeded[backend]
                    incremental = arm.endswith('incremental')
                    output = directory / 'result.json'
                    command = engine_command(seed['script'], export, seed['checker'],
                        seed['cache'] if incremental else directory / 'fresh-cache', seed['key'],
                        output, indexer=seed['indexer'],
                        previous=seed['previous'] if incremental else None, disable=not incremental)
                    sample, semantics[(variant, arm)] = measure_engine(command, output)
                    sample['seed_evidence_id'] = seed['previous'] if incremental else None
                    sample['cache_path'] = str(seed['cache'] if incremental else directory / 'fresh-cache')
                sample.update(repetition=repetition, position=position, variant=variant,
                              arm=arm, expected=expected)
                report['samples'].append(sample)
                report['gates'].append(dict(name=f'{repetition}-{variant}-{arm}-outcome',
                    passed=sample['protocol_valid'] and sample['status'] == expected and
                    (expected != 'REJECTED' or not sample.get('evidence_id'))))
            for variant in VARIANTS:
                for mode in ('full', 'incremental'):
                    old = semantics[(variant, 'baseline-python-' + mode)]
                    new = semantics[(variant, 'native-' + mode)]
                    same = old == new
                    report['gates'].append(dict(name=f'{repetition}-{variant}-{mode}-decision-equality', passed=same,
                        original_projection_sha256=object_hash(old), native_projection_sha256=object_hash(new)))
                    if not same:
                        write(out / 'disagreements' / f'{repetition}-{variant}-{mode}.json',
                              dict(original=old, native=new))
            write(out / 'partial.json', report)
        report['medians'] = measurement_table(report['samples'])
        report['economics'] = {}
        for offset, variant in enumerate(PRIMARY):
            by_arm = {(sample['repetition'], sample['arm']): sample
                      for sample in report['samples'] if sample['variant'] == variant}
            pairs = [dict(repetition=repetition,
                          native_wall_seconds=by_arm[(repetition, 'native-incremental')]['resources']['wall_seconds'],
                          direct_wall_seconds=by_arm[(repetition, 'current-direct-full')]['resources']['wall_seconds'],
                          native_position=by_arm[(repetition, 'native-incremental')]['position'],
                          direct_position=by_arm[(repetition, 'current-direct-full')]['position'])
                     for repetition in range(args.repetitions)]
            report['economics'][variant] = paired_economics(pairs, RANDOM_SEED + offset)
        report['component_addition_totals'] = {
            variant: {arm: {metric: entry['resources'][metric] +
                           report['construction'][variant]['construction_sum'][metric]
                           for metric in ('wall_seconds', 'cpu_seconds')}
                      for arm, entry in arms.items()}
            for variant, arms in report['medians'].items()}
        report['export_plus_verification_subtotals'] = {
            variant: {arm: {metric: entry['resources'][metric] + export_resources[metric]
                           if export_resources else None
                           for metric in ('wall_seconds', 'cpu_seconds')}
                      for arm, entry in arms.items()}
            for variant, arms in report['medians'].items()
            for export_resources in [report['construction'][variant]['processes'].get('export_process')]}
        report['gates'].append(dict(name='current-engine-source-stable',
            passed=sha256(HERE / 'engine.py') == source_snapshot['sha256'],
            initial_sha256=source_snapshot['sha256'], final_sha256=sha256(HERE / 'engine.py')))
        report['correctness_passed'] = all(gate['passed'] for gate in report['gates'])
        report['economic_passed'] = all(value['passed'] for value in report['economics'].values())
        report['economic_status'] = 'SPEEDUP' if report['economic_passed'] else 'NO_SPEEDUP'
        report['status'] = ('CORRECTNESS_FAILED' if not report['correctness_passed'] else
                            report['economic_status'])
        write(out / 'summary.json', report)
        (out / 'summary.md').write_text(markdown(report))
        print(json.dumps({name: report[name] for name in
                          ('status', 'correctness_passed', 'economic_passed')}), flush=True)
        return 0 if report['correctness_passed'] and (report['economic_passed'] or not args.require_speedup) else 1
    finally:
        if authority_temp is not None:
            authority_temp.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workloads', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--baseline-bin', type=Path, required=True)
    parser.add_argument('--baseline-ref', default=BASELINE_REF)
    parser.add_argument('--checker', type=Path, default=REPO / 'target/release/check-selected')
    parser.add_argument('--full-checker', type=Path, default=REPO / 'target/release/sokonanoda')
    parser.add_argument('--indexer', type=Path, default=REPO / 'target/release/export-index')
    parser.add_argument('--authority-dir', type=Path)
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--require-speedup', action='store_true')
    args = parser.parse_args()
    if not 5 <= args.repetitions <= 7:
        parser.error('--repetitions must be between 5 and 7')
    return benchmark(args)


if __name__ == '__main__':
    raise SystemExit(main())
