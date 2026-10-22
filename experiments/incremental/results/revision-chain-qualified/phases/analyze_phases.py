#!/usr/bin/env python3
"""Contextual cost arithmetic from actual revision-chain evidence; no certification.

Reads the compact ZIP in place, without extracting large witnesses. Local-summary
development input is always labeled UNQUALIFIED. JSON decimals are added exactly;
display rounding does not replace the preserved raw values.
"""
import argparse
import csv
from decimal import Decimal, getcontext, localcontext
import hashlib
import json
from pathlib import Path
import zipfile

getcontext().prec = 100
ZERO = Decimal(0)
PHASES = ('producer_seconds', 'baseline_validation_seconds', 'identity_update_seconds',
          'materialization_and_hash_seconds', 'checking_seconds', 'persistence_seconds')
CONSUMER_PHASES = PHASES[1:]
MEMORY_FIELDS = ('VmRSS', 'VmHWM', 'RssAnon', 'RssFile')


def require(value, message):
    if not value:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, Decimal), 'expected stored JSON numeric measurement')
    value = Decimal(value)
    require(value.is_finite(), 'nonfinite measurement')
    return value


def total(values):
    return sum((number(value) for value in values), ZERO)


def statistics(values):
    values = sorted(number(value) for value in values)
    if not values:
        return dict(count=0, minimum=None, median=None, maximum=None, sum=ZERO)
    middle = len(values) // 2
    median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
    return dict(count=len(values), minimum=values[0], median=median, maximum=values[-1], sum=total(values))


def ratio(numerator, denominator):
    numerator, denominator = number(numerator), number(denominator)
    if denominator == 0:
        return None
    with localcontext() as context:
        context.prec = 50
        return numerator / denominator


def partition_wall(timings):
    phases = {field:number(timings[field]) for field in PHASES}
    consumer = number(timings['consumer_seconds'])
    apply = number(timings['end_to_end_seconds'])
    named_consumer = total(phases[field] for field in CONSUMER_PHASES)
    consumer_gap = consumer - named_consumer
    apply_gap = apply - phases['producer_seconds'] - consumer
    promotion = number(timings['chain_promotion_seconds'])
    named = total(phases.values())
    return dict(**phases, consumer_seconds=consumer, apply_seconds=apply,
                chain_promotion_nested_seconds=promotion,
                receipt_persistence_before_promotion_seconds=phases['persistence_seconds'] - promotion,
                named_disjoint_sum_seconds=named,
                consumer_unclassified_seconds=consumer_gap, apply_unclassified_seconds=apply_gap,
                reconstructed_apply_seconds=named + consumer_gap + apply_gap,
                has_negative_residual=consumer_gap < 0 or apply_gap < 0)


def cpu_partition(timings):
    fields = [field.replace('_seconds', '_cpu_seconds') for field in CONSUMER_PHASES]
    if any(field not in timings for field in fields + ['consumer_cpu_seconds', 'end_to_end_cpu_seconds']):
        return dict(available=False)
    phases = {field:number(timings[field]) for field in fields}
    consumer = number(timings['consumer_cpu_seconds'])
    apply = number(timings['end_to_end_cpu_seconds'])
    return dict(available=True, phases=phases, apply_cpu_seconds=apply,
                consumer_cpu_seconds=consumer,
                before_consumer_prepare_and_wrapper_cpu_seconds=apply - consumer,
                consumer_unclassified_cpu_seconds=consumer - total(phases.values()),
                chain_promotion_nested_cpu_seconds=number(timings['chain_promotion_cpu_seconds']))


def sum_cpu_partitions(rows):
    partitions = [row['cpu'] for row in rows]
    if not all(partition['available'] for partition in partitions):
        return dict(available=False)
    fields = ('apply_cpu_seconds', 'consumer_cpu_seconds', 'before_consumer_prepare_and_wrapper_cpu_seconds',
              'consumer_unclassified_cpu_seconds', 'chain_promotion_nested_cpu_seconds')
    return dict(available=True, **{field:total(partition[field] for partition in partitions) for field in fields},
                phases={field:total(partition['phases'][field] for partition in partitions)
                        for field in partitions[0]['phases']})


def plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key:plain(item) for key,item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_input(args):
    if args.artifact:
        artifact = args.artifact.resolve()
        with zipfile.ZipFile(artifact) as archive:
            members = [entry.filename for entry in archive.infolist()
                       if entry.filename.endswith('revision-chain/summary.json')]
            member = args.summary_member
            if member is None:
                require(len(members) == 1, 'select one exact revision-chain/summary.json member explicitly')
                member = members[0]
            require(sum(entry.filename == member for entry in archive.infolist()) == 1,
                    'summary member is absent or duplicated')
            raw = archive.read(member)
        provenance = dict(kind=('UNQUALIFIED_LOCAL_ZIP_FIXTURE' if args.unqualified_fixture else 'actual_supplied_compact_zip'),
                          path=str(artifact), bytes=artifact.stat().st_size,
                          sha256=file_hash(artifact), summary_member=member)
    else:
        path = args.local_summary.resolve()
        raw = path.read_bytes()
        provenance = dict(kind='UNQUALIFIED_LOCAL_DEVELOPMENT_SUMMARY', path=str(path), bytes=len(raw))
    report = json.loads(raw, parse_float=Decimal)
    require(report.get('schema') == 'mathgraph.authenticated-revision-chain-lifecycle.v1', 'unrecognized source report schema')
    if args.expected_source:
        require(len(args.expected_source) >= 8 and report['source_sha'].startswith(args.expected_source),
                'source report does not match explicit expected source')
    provenance.update(summary_sha256=hashlib.sha256(raw).hexdigest(), source_sha=report['source_sha'],
                      declared_ci_run=args.ci_run,
                      analysis_helper_sha256=file_hash(__file__),
                      measured_source_hashes={path:identity for path,identity in report.get('source_sha256', {}).items()
                          if path in ('experiments/incremental/producer_delta.py','experiments/incremental/revision_chain.py',
                                      'experiments/incremental/benchmark_revision_chain.py','src/identity.rs','src/bin/index_session.rs')},
                      source_tracked_clean=report.get('source_tracked_clean'),
                      observed_report_flags={key:report.get(key) for key in
                          ('completed', 'correctness_passed', 'qualified', 'qualification_status', 'source_and_binary_stable')})
    return report, provenance


def sum_partitions(rows):
    fields = PHASES + ('apply_seconds', 'consumer_seconds', 'chain_promotion_nested_seconds',
        'receipt_persistence_before_promotion_seconds', 'named_disjoint_sum_seconds',
        'consumer_unclassified_seconds', 'apply_unclassified_seconds', 'reconstructed_apply_seconds')
    sums = {field:total(row['wall'][field] for row in rows) for field in fields}
    sums['phase_shares_of_update_sum'] = {field:ratio(sums[field], sums['apply_seconds']) for field in PHASES}
    sums['consumer_gap_share_of_update_sum'] = ratio(sums['consumer_unclassified_seconds'], sums['apply_seconds'])
    sums['apply_gap_share_of_update_sum'] = ratio(sums['apply_unclassified_seconds'], sums['apply_seconds'])
    sums['largest_named_phase'] = max(PHASES, key=lambda field:sums[field])
    sums['negative_residual_revisions'] = [row['revision'] for row in rows if row['wall']['has_negative_residual']]
    return sums


def memory_summary(rows):
    grouped = {}
    missing = []
    for row in rows:
        for phase,sample in row.get('raw_memory', {}).items():
            if not isinstance(sample, dict):
                missing.append(dict(revision=row['revision'], phase=phase, observation=sample)); continue
            for process,fields in sample.get('processes', {}).items():
                if not isinstance(fields, dict) or not fields:
                    missing.append(dict(revision=row['revision'], phase=phase, process=process)); continue
                for field in MEMORY_FIELDS:
                    if field in fields:
                        grouped.setdefault(process, {}).setdefault(field, []).append(fields[field])
    endpoints = {}
    for row in rows:
        sample = row.get('raw_memory', {}).get('persistence')
        if not isinstance(sample, dict):
            continue
        for process,fields in sample.get('processes', {}).items():
            if not isinstance(fields, dict) or not fields:
                continue
            observation = dict(revision=row['revision'], values={key:fields[key] for key in MEMORY_FIELDS if key in fields})
            endpoints.setdefault(process, dict(first=observation))['last'] = observation
    for observations in endpoints.values():
        first, last = observations['first']['values'], observations['last']['values']
        observations['last_minus_first_recorded_kib'] = {key:last[key] - first[key] for key in first.keys() & last.keys()}
    return dict(units='KiB as read from procfs',
                scope='Interleaved post-phase per-process observations only; VmHWM is cumulative including startup. '
                      'Adapter includes references/report history and prior oracles. No sum across processes, aggregate peak, '
                      'continuous-arm memory measurement or phase-peak claim.',
                observed_sample_statistics={process:{field:{key:value for key,value in statistics(values).items() if key != 'sum'}
                                                       for field,values in fields.items()}
                                            for process,fields in grouped.items()},
                same_pair_post_persistence_endpoints=endpoints,
                missing_observations=missing)


def pair_analysis(profile, pair, repetitions, cycles):
    continuous = pair['continuous']; candidate = continuous['candidate']; direct = continuous['direct']
    expected_count = 4 * cycles
    require(len(candidate['steps']) == expected_count and len(pair['steps']) == expected_count,
            'contextual analysis requires the complete reported revision sequence')
    continuous_rows, interleaved_rows = [], []
    for revision, (actual, observed) in enumerate(zip(candidate['steps'], pair['steps']), 1):
        require(actual['export_sha256'] == observed['snapshot']['sha256'], 'timing arms name different input bytes')
        counts = actual['counts']; representation = actual['representation']
        base = dict(profile=profile, repetition=pair['repetition'], revision=revision,
                    state=observed['state'], cycle=observed['cycle'], name=observed['name'],
                    export_sha256=actual['export_sha256'], export_bytes=representation['export_bytes'],
                    delta_bytes=representation['delta_bytes'], full_export_disk_bytes_written=representation['full_export_disk_bytes_written'],
                    actual_counts=counts)
        continuous_rows.append(dict(base, arm='continuous_candidate', raw_timings=actual['timings'],
                                    wall=partition_wall(actual['timings']), cpu=cpu_partition(actual['timings']),
                                    native_nested_report=actual['native_kernel_report']))
        typed = observed['typed_update']
        observed_partition = observed['partition_audit']
        observed_counts = dict(total=observed_partition['actual_kernel_total'], rechecked=observed_partition['actual_kernel_checked'],
                               reused=observed_partition['independently_replayed_reused'])
        require(all(counts[field] == value for field,value in observed_counts.items()), 'timing arms have different actual obligation counts')
        observed_base = dict(base, export_bytes=observed['snapshot']['bytes'], delta_bytes=observed['receipt_audit']['delta_bytes'],
                             full_export_disk_bytes_written=None, actual_counts=observed_counts)
        interleaved_rows.append(dict(observed_base, arm='interleaved_candidate', raw_timings=observed['phases'],
                                     wall=partition_wall(observed['phases']), cpu=cpu_partition(observed['phases']),
                                     apply_external_wall_seconds=observed['apply_wall_seconds'],
                                     raw_memory=observed.get('memory', {}),
                                     native_identity_observation={key:value for key,value in typed.items()
                                         if key in ('finish_nanos', 'recomputed_sccs', 'retained_graph_used', 'rows_processed', 'dag_rows', 'finish_mode', 'index_wire')},
                                     native_nested_report=observed['kernel_report']))
    sums = sum_partitions(continuous_rows)
    interleaved_sums = sum_partitions(interleaved_rows)
    native_finish_seconds = total(number(row['native_identity_observation']['finish_nanos']) / Decimal(1000000000)
                                  for row in interleaved_rows)
    identity_observations = dict(native_finish_seconds_sum=native_finish_seconds,
        broader_identity_update_seconds_sum=interleaved_sums['identity_update_seconds'],
        native_finish_fraction_of_broader_identity=ratio(native_finish_seconds, interleaved_sums['identity_update_seconds']),
        recomputed_sccs_sum=sum(row['native_identity_observation']['recomputed_sccs'] for row in interleaved_rows),
        dag_rows_sum=sum(row['native_identity_observation']['dag_rows'] for row in interleaved_rows),
        all_delta_rows_sum=sum(row['native_identity_observation']['rows_processed'] for row in interleaved_rows),
        scope='Interleaved arm only. Native finish includes all-component root advancement/full-index cloning, '
              'but excludes sparse-patch comparison/serialization/transport and Python reconstruction.')
    ready = candidate['genesis']['ready']
    outer = number(candidate['wall_seconds']); start = number(ready['wall_seconds'])
    outer_cpu = number(candidate['cpu_seconds'])
    update_cpu = total(row['cpu']['apply_cpu_seconds'] for row in continuous_rows)
    export_bytes = sum(row['export_bytes'] for row in continuous_rows)
    delta_bytes = sum(row['delta_bytes'] for row in continuous_rows)
    work = dict(accepted_updates=len(continuous_rows), declaration_schedules_total=sum(row['actual_counts']['total'] for row in continuous_rows),
                actual_selected_checked_total=sum(row['actual_counts']['rechecked'] for row in continuous_rows),
                reused_total=sum(row['actual_counts']['reused'] for row in continuous_rows),
                genesis_checked_from_interleaved_baseline=pair['setup']['baseline_result'].get('counts', {}).get('rechecked'),
                materialized_and_hashed_logical_export_bytes=export_bytes, authenticated_delta_bytes=delta_bytes,
                promotion_full_successor_readback_logical_bytes=export_bytes,
                full_export_disk_bytes_written=sum(row['full_export_disk_bytes_written'] for row in continuous_rows),
                full_export_over_delta_byte_ratio=ratio(export_bytes, delta_bytes),
                combined_materialize_hash_export_bytes_per_second=ratio(export_bytes, sums['materialization_and_hash_seconds']),
                byte_scope='Export bytes are logical bytes written to sealed memfd and hashed by materialization, '
                           'not total physical memory traffic. Promotion reads the successor again inside persistence. '
                           'Zero full-export disk writes excludes memfd movement, baseline IO and small durable objects.')
    shares = {field:ratio(sums[field], outer) for field in PHASES}
    residuals = dict(update_api_wall_sum=sums['apply_seconds'], start_report_wall_seconds=start,
                     outside_update_apis_wall_seconds=outer - sums['apply_seconds'],
                     constructor_close_compact_recording_wall_residual=outer - sums['apply_seconds'] - start,
                     update_api_cpu_sum=update_cpu, start_report_cpu_seconds=ready.get('cpu_seconds'),
                     outside_update_apis_cpu_seconds=outer_cpu - update_cpu,
                     constructor_close_compact_recording_cpu_residual=outer_cpu - update_cpu - number(ready['cpu_seconds']),
                     scope='Continuous outer residuals cannot isolate constructor or supported close; start is same-arm observed ready.wall. '
                           'Do not substitute timings from the separate interleaved arm.')
    cold = pair.get('cold_replay')
    cold_analysis = None
    if cold:
        cold_ready = cold['ready']
        cold_analysis = dict(raw=cold,
            setup_plus_close_observed_component_sum=number(cold['setup_wall_seconds']) + number(cold['close_wall_seconds']),
            constructor_call_overhead_residual=number(cold['setup_wall_seconds']) - number(cold_ready['wall_seconds']),
            replay_history_chain_overhead_over_baseline_start=number(cold_ready['wall_seconds']) - number(cold_ready['baseline_start_seconds']),
            scope='Cold setup and close components have independent snapshot/index checks between them; this is not uninterrupted cold elapsed. '
                  'Baseline is authenticated prior evidence, while accepted revisions are genuinely replayed. No full cold CPU/close CPU is recorded.')
    return dict(repetition=pair['repetition'], expected_update_count=expected_count, actual_update_count=len(continuous_rows),
                continuous=dict(order=continuous['order'], outer_wall_seconds=outer, outer_cpu_seconds=outer_cpu,
                    same_arm_start_report={key:ready.get(key) for key in ('wall_seconds','cpu_seconds','baseline_start_seconds','replayed_revisions')},
                    sums=sums, cpu_sums=sum_cpu_partitions(continuous_rows), phase_shares_of_outer_wall=shares, residuals=residuals, work=work,
                    direct_outer_wall_seconds=direct['wall_seconds'], direct_outer_cpu_seconds=direct['cpu_seconds'],
                    direct_command_wall_sum=total(command['wall_seconds'] for command in direct['commands']),
                    direct_outer_wrapper_wall_residual=number(direct['wall_seconds']) - total(command['wall_seconds'] for command in direct['commands']),
                    direct_completed_child_cpu_sum=total(command['completed_child_cpu_seconds'] for command in direct['commands']),
                    direct_outer_parent_cpu_residual=number(direct['cpu_seconds']) - total(command['completed_child_cpu_seconds'] for command in direct['commands']),
                    rows=continuous_rows),
                interleaved=dict(sums=interleaved_sums, cpu_sums=sum_cpu_partitions(interleaved_rows),
                    native_identity_observations=identity_observations,
                    raw_components=pair['components'], raw_cpu_components=pair['cpu_components'],
                    setup={key:pair['setup'].get(key) for key in ('wall_seconds','cpu_seconds','constructor_wall_seconds','start_wall_seconds')},
                    observed_constructor_through_close_wall_seconds=pair['observed_constructor_through_close_wall_seconds'],
                    oracle_evidence_harness_elapsed_residual=number(pair['observed_constructor_through_close_wall_seconds']) - number(pair['components']['api_component_sum_wall_seconds']),
                    memory=memory_summary(interleaved_rows), rows=interleaved_rows), cold_replay=cold_analysis)


def analyze(report, provenance):
    profiles = {}
    for name, source in report['profiles'].items():
        pairs = [pair_analysis(name, pair, report['repetitions'], report['cycles']) for pair in source['pairs']]
        require(bool(pairs), 'no measured complete sequences')
        continuous_summary = {field:statistics([pair['continuous']['sums'][field] for pair in pairs])
                              for field in PHASES + ('apply_seconds', 'consumer_unclassified_seconds', 'apply_unclassified_seconds',
                                  'chain_promotion_nested_seconds', 'receipt_persistence_before_promotion_seconds')}
        phase_shares = {field:statistics([pair['continuous']['sums']['phase_shares_of_update_sum'][field] for pair in pairs]) for field in PHASES}
        pooled_update = total(pair['continuous']['sums']['apply_seconds'] for pair in pairs)
        pooled_phase_shares = {field:ratio(total(pair['continuous']['sums'][field] for pair in pairs), pooled_update) for field in PHASES}
        pooled_gaps = {field:ratio(total(pair['continuous']['sums'][field] for pair in pairs), pooled_update)
                       for field in ('consumer_unclassified_seconds','apply_unclassified_seconds')}
        profiles[name] = dict(sequence_count=len(pairs), updates_per_sequence=4 * report['cycles'],
            source_dimensions=dict(declarations=pairs[0]['continuous']['rows'][0]['actual_counts']['total'],
                baseline_producer_stats=source['pairs'][0]['setup']['ready']['producer'].get('stats'),
                distinct_checked_counts_by_state={str(state):sorted({row['actual_counts']['rechecked'] for pair in pairs
                    for row in pair['continuous']['rows'] if row['state'] == state}) for state in (0,1,2,3)},
                distinct_export_bytes=sorted({row['export_bytes'] for pair in pairs for row in pair['continuous']['rows']})),
            continuous_per_sequence_sum_statistics=continuous_summary,
            continuous_per_sequence_phase_share_statistics=phase_shares,
            continuous_pooled_update_phase_shares=pooled_phase_shares,
            continuous_pooled_update_gap_shares=pooled_gaps,
            measured_disjoint_update_bucket_order=sorted(dict(pooled_phase_shares, **pooled_gaps),
                key=lambda field:dict(pooled_phase_shares, **pooled_gaps)[field], reverse=True),
            continuous_pooled_update_phase_share_exact_inputs={field:dict(numerator_seconds=total(pair['continuous']['sums'][field] for pair in pairs),
                                                                         denominator_seconds=pooled_update) for field in PHASES},
            largest_named_phase_per_sequence=[pair['continuous']['sums']['largest_named_phase'] for pair in pairs],
            sequences=pairs)
    return dict(schema='mathgraph.contextual-revision-phase-analysis.v1', provenance=provenance,
        analysis_scope='Contextual exact arithmetic only. Does not certify source correctness, HMACs, selected sets or overall economic qualification.',
        classification='UNQUALIFIED_LOCAL_DEVELOPMENT_ONLY' if provenance['kind'].startswith('UNQUALIFIED') else 'ACTUAL_ZIP_CONTEXTUAL_ANALYSIS_ONLY',
        arithmetic=dict(input='Stored JSON numeric decimals parsed exactly with Decimal', additions='100-digit base-10 arithmetic preserves the observed finite clock values; numeric outputs are decimal strings',
                        ratios='50-digit decimal division; display rounding is separate',
                        statistics='Median/min/max of actual sequence sums and per-sequence ratios, never sums of phase medians',
                        uncertainty='Observed same-host ranges only, no new confidence intervals or asymptotic claim; clock and live CPU tick precision remain limited'),
        source_timing_rules=dict(disjoint='A=P+V+I+M+K+R+Gconsumer+Gapply',
            consumer_gap='C-(V+I+M+K+R)', apply_gap='A-P-C', promotion='Q is nested in R; show Q and R-Q without adding Q again',
            cpu='A_cpu-C_cpu includes preparation and outer wrappers, not pure producer CPU'),
        source_grounded_cost_limits=[
            'Materialization/hash processes the complete logical successor export every update.',
            'Chain promotion combines receipt reauthentication/reconstruction/applicability, full successor readback/layout, source/head persistence; its internals are not separately timed.',
            'Chained native finish_nanos includes a loop over all retained components and full-index cache cloning, not only affected-cone reclosure.',
            'Sparse patch comparison/serialization/IPC/Python reconstruction lie inside broader identity_update but outside native finish_nanos.',
            'Consumer gaps include unsplit reuse scans/configuration/index writes and instrumentation/authentication/assembly; no GC attribution is supported.',
            'The two profiles differ in full byte/DAG size and checked obligation cones (early413 vs672, unrelated1 vs260); they are not a controlled asymptotic scaling experiment.',
            'Interleaved post-phase RSS/cumulative VmHWM do not establish continuous memory, aggregate peaks or peak-memory savings.'],
        profiles=profiles)


def text_report(result):
    lines = [result['classification'], result['analysis_scope'],
             'Input SHA256: ' + result['provenance'].get('sha256', result['provenance']['summary_sha256']),
             'Source: ' + result['provenance']['source_sha'], '',
             'Sequence sums are calculated before medians. Promotion is nested in persistence. Signed gaps are retained.']
    for name, profile in result['profiles'].items():
        lines += ['', name + ': ' + str(profile['sequence_count']) + ' sequences x ' + str(profile['updates_per_sequence']) + ' actual updates']
        summary = profile['continuous_per_sequence_sum_statistics']
        lines.append('  Continuous update API sum median: ' + str(summary['apply_seconds']['median']) + ' s')
        for field in sorted(PHASES, key=lambda key:profile['continuous_pooled_update_phase_shares'][key], reverse=True):
            share = profile['continuous_pooled_update_phase_shares'][field]
            lines.append('  ' + field + ': sequence-sum median ' + str(summary[field]['median']) + ' s; pooled update share ' + format(share * 100, '.3f') + '%')
        for pair in profile['sequences']:
            c = pair['continuous']; w = c['work']; r = c['residuals']
            lines.append('  Rep ' + str(pair['repetition']) + ': continuous outer=' + str(c['outer_wall_seconds']) +
                ' s; start=' + str(r['start_report_wall_seconds']) + ' s; constructor/close/recording residual=' +
                str(r['constructor_close_compact_recording_wall_residual']) + ' s; checked/reused=' +
                str(w['actual_selected_checked_total']) + '/' + str(w['reused_total']) + '; materialized+hashed bytes=' +
                str(w['materialized_and_hashed_logical_export_bytes']))
        gaps = summary['consumer_unclassified_seconds']
        lines.append('  Consumer-gap sequence sums min/median/max: ' + '/'.join(str(gaps[key]) for key in ('minimum','median','maximum')) + ' s')
    lines += ['', 'No phase-median addition, GC diagnosis, continuous memory claim, or asymptotic scaling conclusion is warranted.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--artifact', type=Path)
    source.add_argument('--local-summary', type=Path)
    parser.add_argument('--summary-member')
    parser.add_argument('--expected-source')
    parser.add_argument('--ci-run', help='Declared provenance supplied by caller; this helper does not authenticate GitHub run metadata.')
    parser.add_argument('--unqualified-fixture', action='store_true', help='Explicitly label a local ZIP parser fixture as UNQUALIFIED.')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.artifact or args.expected_source, 'actual ZIP analysis requires explicit expected source SHA')
    require(not args.out.exists() or not any(args.out.iterdir()), 'use a fresh output directory')
    report, provenance = load_input(args)
    result = analyze(report, provenance)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'analysis.json').write_text(json.dumps(plain(result), indent=2, sort_keys=True) + '\n')
    (args.out / 'analysis.txt').write_text(text_report(result))
    fields = ('profile','repetition','arm','revision','state','export_bytes','delta_bytes') + PHASES + (
        'apply_seconds','consumer_unclassified_seconds','apply_unclassified_seconds','chain_promotion_nested_seconds')
    with (args.out / 'raw-update-arithmetic.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for profile in result['profiles'].values():
            for pair in profile['sequences']:
                for arm in ('continuous', 'interleaved'):
                    for row in pair[arm]['rows']:
                        values = {field:row[field] for field in fields if field in row}
                        values.update({field:row['wall'][field] for field in fields if field in row['wall']})
                        writer.writerow(plain(values))
    print(json.dumps(dict(classification=result['classification'], source_sha=provenance['source_sha'],
                         summary_sha256=provenance['summary_sha256'], profiles=list(result['profiles']),
                         contextual_only=True, output=str(args.out.resolve()))))


if __name__ == '__main__':
    main()
