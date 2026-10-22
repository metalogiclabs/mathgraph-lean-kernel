#!/usr/bin/env python3
"""Compact contextual review of the independently recomputed actual costs."""
from decimal import Decimal
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent


def D(value):
    return Decimal(str(value))


def stat(values):
    values = list(map(D, values))
    return dict(min=str(min(values)), median=str(statistics.median(values)), max=str(max(values)))


def run():
    assert stat(iter([1, 2, 3])) == dict(min='1', median='2', max='3')
    report = json.loads((HERE / 'analysis.json').read_bytes())
    brief = dict(schema='mathgraph.authenticated-state.actual-cost-review.v1',
        status='ACTUAL_EXACT_SOURCE_ARITHMETIC_PASS', source_sha=report['source_sha'],
        ci_run=39709067518, source_summary_sha256=report['summary_sha256'],
        helper_sha256=report['provenance']['helper_sha256'],
        all_28_published_economic_series_recomputed_exactly=True, profiles={},
        correctness_boundary='Arithmetic and measurement-scope review; semantic acceptance correctness remains '
            'the separate actual CI and independent root replay boundary.',
        limits=['Five paired lifetimes per profile on one host with warm OS caches; ten actual same-kind edits per paired warm sum.',
            'Lifecycle includes initialization, forty updates and close; direct arm is forty-one fresh Rust commands with input preparation excluded.',
            'Sampled per-process memory is not an aggregate peak. Logical session size is not allocated blocks or shared physical artifact size.',
            'No constant-cone or asymptotic claim: whole-index applicability/copy loops and cold admission remain O(N).'])
    for name, profile in report['profiles'].items():
        result = dict(lifecycle=profile['economics'], warm={}, cold_replay=profile['cold'], arms={})
        for edit, observations in profile['warm_edits'].items():
            result['warm'][edit] = {}
            for comparator, metric in observations['comparisons'].items():
                result['warm'][edit][comparator] = dict(metric,
                    state_median_seconds_per_update=metric['apply_median_wall_seconds'] / observations['updates_per_pair'],
                    comparator_median_seconds_per_update=metric['direct_median_wall_seconds'] / observations['updates_per_pair'],
                    updates_per_pair=observations['updates_per_pair'])
        for arm in ('state', 'full_export'):
            observations = [pair['arms'][arm] for pair in profile['pairs']]
            timing_keys = ('constructor_plus_start_wall_seconds', 'constructor_plus_start_cpu_seconds',
                'warm_update_sum_wall_seconds', 'warm_update_sum_cpu_seconds', 'close_wall_seconds',
                'close_cpu_seconds', 'outer_recording_sampling_residual_wall_seconds',
                'outer_recording_sampling_residual_cpu_seconds')
            timings = {key: stat(item[key] for item in observations) for key in timing_keys}
            phases = {unit: {key: stat(item['phases'][unit][key] for item in observations)
                for key in observations[0]['phases'][unit]} for unit in ('wall', 'cpu')}
            pooled = {unit: {key: str(sum(D(item['phases'][unit][key]) for item in observations))
                for key in observations[0]['phases'][unit]} for unit in ('wall', 'cpu')}
            denominator = sum(D(item['phases']['wall']['apply_seconds']) for item in observations)
            shares = {key: str(100 * sum(D(item['phases']['wall'][key]) for item in observations) / denominator)
                for key in ('producer_seconds', 'identity_update_seconds', 'materialization_and_hash_seconds',
                    'checking_seconds', 'persistence_seconds', 'consumer_gap_seconds', 'before_consumer_gap_seconds')}
            memory = {}
            for process in ('adapter', 'producer', 'index', 'retained_kernel'):
                memory[process] = {}
                for field in ('VmRSS', 'VmHWM'):
                    values = [entry['kib'] for item in observations for entry in item['memory']['observations']
                        if entry['process'] == process and entry['field'] == field]
                    memory[process][field] = stat(values) if values else None
            result['arms'][arm] = dict(timing_statistics=timings, phase_statistics=phases,
                pooled_phase_totals=pooled, pooled_wall_shares_percent=shares,
                work_per_40update_pair=observations[0]['warm_work'],
                logical_persisted_session_bytes=stat(item['cache']['logical_runtime_file_bytes'] for item in observations),
                sampled_memory_kib=memory,
                negative_cpu_phase_residuals=sum(row['cpu']['has_negative_residual'] for item in observations for row in item['updates']),
                negative_wall_phase_residuals=sum(row['wall']['has_negative_residual'] for item in observations for row in item['updates']))
        brief['profiles'][name] = result
    (HERE / 'contextual-brief.json').write_text(json.dumps(brief, indent=2) + '\n')
    for name, profile in brief['profiles'].items():
        print(name)
        for key in ('state_vs_direct_wall_seconds', 'state_vs_full_export_wall_seconds',
                    'state_vs_direct_cpu_seconds', 'state_vs_full_export_cpu_seconds'):
            metric = profile['lifecycle'][key]
            print(key, 'candidate', metric['apply_median_wall_seconds'], 'control', metric['direct_median_wall_seconds'],
                'speedup', metric['speedup'], 'reduction', metric['reduction_percent'], 'pass', metric['passed'],
                'CI', metric['bootstrap_ratio_interval_95'])
        for edit in ('early-definition', 'unrelated-definition'):
            for comparator, metric in profile['warm'][edit].items():
                print(edit, comparator, 'state', metric['state_median_seconds_per_update'],
                    'control', metric['comparator_median_seconds_per_update'], 'speedup', metric['speedup'],
                    'reduction', metric['reduction_percent'], 'pass', metric['passed'],
                    'CI', metric['bootstrap_ratio_interval_95'])
        for arm, observed in profile['arms'].items():
            print(arm, 'timing_medians', {key: value['median'] for key, value in observed['timing_statistics'].items()})
            print(arm, 'wall_phase_medians', {key: value['median'] for key, value in observed['phase_statistics']['wall'].items()})
            print(arm, 'pooled_wall_shares_percent', observed['pooled_wall_shares_percent'],
                'cache', observed['logical_persisted_session_bytes'], 'negative_cpu_residuals', observed['negative_cpu_phase_residuals'])
        print('cold_replay', profile['cold_replay'])


if __name__ == '__main__':
    run()
