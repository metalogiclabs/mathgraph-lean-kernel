#!/usr/bin/env python3
"""Recompute archived measurements without importing either qualification engine."""
import hashlib
import json
import math
from pathlib import Path
import random
import statistics as stats
import zipfile

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'retained-index-summaries.zip'
SOURCE = 'ef434eb2477fb64d7fd90fdf23f55bd0b35a0243'
EXPECTED_SHA = '685bb4892c3ceb71a0b23da6159712d72885bc76fbfd13907310b5c41ea7cb13'
assert ARCHIVE.stat().st_size == 37239728
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == EXPECTED_SHA
archive = zipfile.ZipFile(ARCHIVE)
members = {}


def read(name):
    raw = archive.read(name)
    members[name] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    return json.loads(raw)


def median(values):
    return stats.median(values)


def paired(left, right):
    assert len(left) == len(right) and len(left) >= 5
    assert all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in left + right)
    rng = random.Random(20261016)
    boot = []
    for _ in range(10000):
        indices = [rng.randrange(len(left)) for _ in left]
        boot.append(median([left[i] for i in indices]) / median([right[i] for i in indices]))
    boot.sort()
    ratio = median(left) / median(right)
    wins = sum(a < b for a, b in zip(left, right))
    interval = [boot[int(q * 9999)] for q in (.025, .975)]
    passed = ratio < 1 and wins > len(left) / 2 and interval[1] < 1
    return dict(numerator_median_seconds=median(left), denominator_median_seconds=median(right),
        median_ratio=ratio, improvement_percent=(1-ratio)*100,
        wins=wins, pairs=len(left), bootstrap_ratio_interval_95=interval,
        status='SPEEDUP' if passed else 'NO_SPEEDUP', raw_numerator=left, raw_denominator=right)


def same(a, b):
    assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15), (a, b)


retained = read('retained-qualification/summary.json')
assert retained['source_sha'] == SOURCE and retained['source_worktree_tracked_clean'] is True
assert retained['run_completed'] and retained['correctness_passed'] and retained['qualification_status'] == 'PASS'
assert len(retained['gates']) == 181 and all(g['passed'] is True for g in retained['gates'])
expected = {(p, v, i) for p in ('original', 'expanded')
            for v in ('early-definition', 'unrelated-definition') for i in range(5)}
assert len(retained['samples']) == 20
assert {(s['profile'], s['variant'], s['repetition']) for s in retained['samples']} == expected
result = dict(schema='mathgraph.independent-retained-economics-audit.v1',
    source_sha=SOURCE, archive_sha256=EXPECTED_SHA, archive_bytes=ARCHIVE.stat().st_size,
    method='Independent standard-library recomputation from raw compact-archive samples; no engine/harness imports.',
    profiles={}, isolated_same_parsed_microbenchmarks={}, cold_replay={}, sparse_storage={},
    scope=['Warm apply includes real producer, authenticated baseline read, index roundtrip, complete selected parser, decisions, and full accepted-record persistence.',
           'One-update API component sum is the measured constructor-through-apply interval plus measured supported shutdown for that same sample. It is not a sum of medians or a multi-update estimate.',
           'Standalone core and wholefinish exclude row parsing and full-index JSON transport. Forced-full wholefinish includes additional observation-only counters; preserved449 is the actual historical adapter comparator.',
           'Memory is postidentity procfs KiB and cumulative startup-inclusive VmHWM, never aggregate RSS or an exact phase peak.',
           'Only the compact artifact was downloaded and inspected; the full artifact was not downloaded.'])
comparisons = 0
for profile in ('original', 'expanded'):
    result['profiles'][profile] = {}
    for variant in ('early-definition', 'unrelated-definition'):
        rows = sorted((s for s in retained['samples'] if s['profile'] == profile and s['variant'] == variant), key=lambda s:s['repetition'])
        assert all(s['passed'] for s in rows)
        for row in rows:
            assert set(row['arms']) == {'qualified449', 'full', 'retained'}
            assert len({a['delta_sha256'] for a in row['arms'].values()}) == 1
            assert len({a['index_sha256'] for a in row['arms'].values()}) == 1
            assert len({a['sealed_snapshot']['sha256'] for a in row['arms'].values()}) == 1
            for arm in row['arms'].values():
                assert arm['result_status'] == 'VERIFIED' and arm['direct_rust']['returncode'] == 0
                assert arm['receipt_audit']['issuer_hmac_valid'] and arm['receipt_audit']['all_content_addresses_valid']
                same(arm['one_update_api_component_sum_wall_seconds'], arm['constructor_through_apply_wall_seconds'] + arm['close_wall_seconds'])
                same(arm['one_update_api_component_sum_cpu_seconds'], arm['constructor_through_apply_cpu_seconds'] + arm['close_cpu_seconds'])
        recomputed = {}
        for key, reported in retained['economics'][profile][variant].items():
            if key == 'phase_medians':
                continue
            if key.startswith('retained_vs_qualified449:'):
                field = key.split(':', 1)[1]
                left = [s['arms']['retained'][field] for s in rows]
                right = [s['arms']['qualified449'][field] for s in rows]
            elif key == 'retained_vs_direct_fresh_rust':
                left = [s['arms']['retained']['apply_wall_seconds'] for s in rows]
                right = [s['arms']['retained']['direct_rust']['wall_seconds'] for s in rows]
            elif key.startswith('retained_vs_full:'):
                field = key.split(':', 1)[1]
                if field == 'index_roundtrip':
                    left = [s['standalone']['retained']['roundtrip_wall_seconds'] for s in rows]
                    right = [s['standalone']['full']['roundtrip_wall_seconds'] for s in rows]
                elif field in ('compute_wall_seconds', 'compute_cpu_seconds', 'finish_wall_seconds', 'finish_cpu_seconds'):
                    left = [s['standalone']['retained']['finish_stats'][field] for s in rows]
                    right = [s['standalone']['full']['finish_stats'][field] for s in rows]
                else:
                    left = [s['arms']['retained'][field] for s in rows]
                    right = [s['arms']['full'][field] for s in rows]
            else:
                raise AssertionError('unknown reported comparison: ' + key)
            independent = paired(left, right)
            same(independent['numerator_median_seconds'], reported['apply_median_wall_seconds'])
            same(independent['denominator_median_seconds'], reported['direct_median_wall_seconds'])
            same(independent['median_ratio'], reported['median_ratio'])
            for a,b in zip(independent['bootstrap_ratio_interval_95'], reported['bootstrap_ratio_interval_95']): same(a,b)
            assert independent['status'] == reported['status'] and independent['wins'] == reported['paired_wins']
            recomputed[key] = independent
            comparisons += 1
        costs, memory, standalone = {}, {}, {}
        for arm in ('qualified449', 'full', 'retained'):
            fields = ('constructor_wall_seconds', 'start_wall_seconds', 'apply_wall_seconds',
                'close_wall_seconds', 'close_cpu_seconds', 'constructor_through_apply_wall_seconds',
                'constructor_through_apply_cpu_seconds', 'one_update_api_component_sum_wall_seconds',
                'one_update_api_component_sum_cpu_seconds')
            costs[arm] = {f:median([s['arms'][arm][f] for s in rows]) for f in fields}
            memory[arm] = {p:{f:median([s['arms'][arm]['memory']['identity']['processes'][p][f] for s in rows])
                for f in ('VmRSS','VmHWM')} for p in ('adapter','producer','index')}
        for arm in ('full','retained'):
            fields = ('setup_wall_seconds','baseline_prepare_wall_seconds','roundtrip_wall_seconds','roundtrip_minus_finish_wall_seconds')
            standalone[arm] = {f:median([s['standalone'][arm][f] for s in rows]) for f in fields}
            standalone[arm]['stats'] = {f:median([s['standalone'][arm]['finish_stats'][f] for s in rows])
                for f in ('compute_wall_seconds','compute_cpu_seconds','finish_wall_seconds','finish_cpu_seconds')}
        units = [s['standalone']['retained']['finish_stats'] for s in rows]
        result['profiles'][profile][variant] = dict(comparisons=recomputed, costs=costs,
            standalone=standalone, postidentity_memory_KiB=memory,
            operation_counts={f:sorted({u[f] for u in units}) for f in ('affected_declarations','affected_sccs','closure_hashes','touched_declarations','dependency_edges_touched')},
            graph_declarations=units[0]['total_declarations'], cone_keys=rows[0]['cone_keys'],
            actual_kernel_checked=sorted({s['arms']['retained']['partition']['actual_kernel_checked'] for s in rows}))
        name=f'retained-microbenchmark-{profile}-{variant}.log'
        raw=archive.read(name); members[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        records=[]
        for line in raw.decode().splitlines():
            if 'RETAINED_BENCH ' in line:
                record,end=json.JSONDecoder().raw_decode(line.split('RETAINED_BENCH ',1)[1]);records.append(record)
        assert len(records)==1 and records[0]['repetitions']==7 and len(records[0]['samples'])==7
        micro=records[0];assert all(s['parity'] is True for s in micro['samples'])
        result['isolated_same_parsed_microbenchmarks'][profile+':'+variant]=dict(
            scope=micro['scope'], repetitions=7, prepare_wall_seconds=micro['prepare_wall_seconds'],
            retained={f:median([s['retained'][f] for s in micro['samples']]) for f in ('compute_wall_seconds','compute_cpu_seconds','finish_wall_seconds','finish_cpu_seconds')},
            full={f:median([s['full_'+f] for s in micro['samples']]) for f in ('compute_wall_seconds','compute_cpu_seconds','finish_wall_seconds','finish_cpu_seconds')})

result['same_cone_scaling']={}
for variant in ('early-definition','unrelated-definition'):
    original=result['profiles']['original'][variant];expanded=result['profiles']['expanded'][variant]
    assert original['cone_keys']==expanded['cone_keys'] and original['operation_counts']==expanded['operation_counts']
    result['same_cone_scaling'][variant]=dict(operation_counts=original['operation_counts'],
        graph_size_ratio=expanded['graph_declarations']/original['graph_declarations'],
        standalone_core_wall_ratio=expanded['standalone']['retained']['stats']['compute_wall_seconds']/original['standalone']['retained']['stats']['compute_wall_seconds'],
        standalone_whole_finish_wall_ratio=expanded['standalone']['retained']['stats']['finish_wall_seconds']/original['standalone']['retained']['stats']['finish_wall_seconds'],
        isolated_core_wall_ratio=result['isolated_same_parsed_microbenchmarks']['expanded:'+variant]['retained']['compute_wall_seconds']/result['isolated_same_parsed_microbenchmarks']['original:'+variant]['retained']['compute_wall_seconds'],
        isolated_whole_finish_wall_ratio=result['isolated_same_parsed_microbenchmarks']['expanded:'+variant]['retained']['finish_wall_seconds']/result['isolated_same_parsed_microbenchmarks']['original:'+variant]['retained']['finish_wall_seconds'])

for profile,folder in [('original','delta-qualification'),('expanded','delta-expanded-qualification')]:
    phases=read(folder+'/compact-phases.json')
    cold=[s for s in phases['samples'] if s['cold_replay']]
    assert len(cold)==1
    s=cold[0]
    result['cold_replay'][profile]=dict(setup_wall_seconds=s['setup_wall_seconds'],
        outer_replay_wall_seconds=s['apply_wall_seconds'], setup_plus_outer_replay_component_sum=s['setup_wall_seconds']+s['apply_wall_seconds'],
        inner_validate_apply_wall_seconds=s['timings']['end_to_end_seconds'],
        direct_rust_wall_seconds=s['direct_wall_seconds'],
        scope='Single observed restart/replay, not new-source production. Outer replay includes receipt/object authentication absent from inner validation timer. Shutdown not measured by this older qualification path.')

sparse=read('sparse-receipt-benchmark/summary.json')
assert sparse['source_sha']==SOURCE and sparse['scope']=='storage_only_not_acceptance'
assert sparse['run_completed'] and sparse['correctness_passed'] and sparse['qualification_status']=='PASS'
assert len(sparse['samples'])==20 and sum(len(c) for c in sparse['controls'].values())==44
for case,reported in sparse['economics'].items():
    profile,variant=case.split(':');rows=[s for s in sparse['samples'] if s['profile']==profile and s['variant']==variant]
    independent={}
    for phase in ('write','read'):
        independent[phase]=paired([s['sparse'][phase]['wall_seconds'] for s in rows],[s['full'][phase]['wall_seconds'] for s in rows])
        same(independent[phase]['median_ratio'],reported[phase]['sparse_over_full_median_ratio'])
        assert independent[phase]['wins']==reported[phase]['paired_wins']
        for a,b in zip(independent[phase]['bootstrap_ratio_interval_95'],reported[phase]['bootstrap_ratio_interval_95']): same(a,b)
        assert independent[phase]['status']==reported[phase]['status']=='NO_SPEEDUP'
    result['sparse_storage'][case]=dict(comparisons=independent,
        full_bytes=rows[0]['full']['bytes'],sparse_bytes=rows[0]['sparse']['bytes'],patches=rows[0]['sparse']['patches'])
result['recomputed_retained_comparisons']=comparisons
result['status']='PASS_INDEPENDENT_RECOMPUTATION'
result['member_hashes']=members
(ROOT/'independent-economics-review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(status=result['status'],retained_comparisons=comparisons,sparse_comparisons=8,
    cases=4,paired_samples=20,adapter_arms=60,isolated_microbench_samples=28),indent=2))
