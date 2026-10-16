#!/usr/bin/env python3
"""Independent arithmetic review. Does not import the benchmark implementation."""
import collections
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess

SOURCE = Path('/workspace/kernel-audit/native-benchmark-final/summary.json')
OUT = Path('/workspace/kernel-audit/native-benchmark-independent-review.json')
ROOT = SOURCE.parent
REPO = Path('/workspace/mathgraph-lean-kernel')
raw = SOURCE.read_bytes()
report = json.loads(raw)
checks = []

def check(name, condition, **details):
    checks.append(dict(name=name, passed=bool(condition), **details))

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()

def equal(left,right):
    if type(left) is float or type(right) is float:
        return math.isclose(left,right,rel_tol=1e-12,abs_tol=1e-12)
    return left == right

def projection(result):
    return dict(status=result.get('status'),counts=result.get('counts'),
        decisions=[{name: item.get(name) for name in ('name','index','status','reason','dependency_witness')}
                   for item in result.get('decisions',[])],
        selected_indices=[item['index'] for item in result.get('decisions',[])
                          if item['status'] != 'VERIFIED_REUSED'],
        checker_code=result.get('checker_result',{}).get('code'))

variants = ('baseline','early-definition','unrelated-definition','theorem-leaf','invalid-proof','axiom-type')
arms = ('baseline-python-full','baseline-python-incremental','native-full','native-incremental',
        'baseline-direct-full','current-direct-full')
metrics = ('wall_seconds','cpu_seconds','max_rss_kib')
check('exact_matrix_180_unique_samples',len(report['samples'])==180 and
      len({(s['repetition'],s['variant'],s['arm']) for s in report['samples']})==180)
check('ten_seeds',len(report['seeds'])==10)
check('five_repetitions',report['repetitions']==5)
check('exact_variants_and_arms',report['variants']==list(variants) and report['arms']==list(arms))
expected_old = subprocess.check_output(['git','show',
    '9ac04033b51703fb135ec3c28621d44b183944fe:experiments/incremental/engine.py'],cwd=REPO)
check('baseline_is_exact_9ac_engine',Path(report['baseline_source_path']).read_bytes()==expected_old and
      hashlib.sha256(expected_old).hexdigest()==report['baseline_source_sha256'])
check('historical_baseline_binaries_exact',all(report['historical_baseline_binary_matches'].values()))
for name, info in report['captured_tools'].items():
    check('captured_binary_'+name,digest(info['captured_path'])==info['sha256'])
check('captured_current_engine_exact',digest(report['current_engine_snapshot']['captured_path'])==
      report['current_engine_snapshot']['sha256'])
manifest_path=Path('/workspace/kernel-audit/workloads-final/manifest.json')
manifest=json.loads(manifest_path.read_bytes())
check('exact_workload_manifest',digest(manifest_path)==report['workload_manifest_sha256'])
for variant in variants:
    info=manifest['variants'][variant]
    check('exact_export_'+variant,digest(info['path'])==info['sha256']==report['pins']['export_sha256'][variant])

# Check the archived per-command record, result hash, protocol and phase data.
recomputed_outcomes=[]
selection_counts=collections.defaultdict(set)
projections={}
for sample in report['seeds']+report['samples']:
    resources=sample['resources']
    direct=sample.get('arm','').endswith('direct-full')
    process_path=Path(resources['stdout_path']).with_suffix('.json')
    check('raw_resource_'+str(process_path.relative_to(ROOT)),
          json.loads(process_path.read_bytes())==resources)
    expected='REJECTED' if sample.get('variant') in ('invalid-proof','axiom-type') else 'VERIFIED'
    protocol=not resources['timed_out'] and resources['returncode']==(1 if expected=='REJECTED' else 0)
    if not direct:
        result=json.loads(Path(sample['result_path']).read_bytes())
        check('result_hash_'+str(Path(sample['result_path']).relative_to(ROOT)),
              digest(sample['result_path'])==sample['result_sha256'])
        numeric={name:value for name,value in result['timings'].items() if type(value) in (int,float)}
        check('phase_copy_'+str(Path(sample['result_path']).relative_to(ROOT)),numeric==sample['phases'])
        check('projection_hash_'+str(Path(sample['result_path']).relative_to(ROOT)),
              hashlib.sha256(canonical(projection(result))).hexdigest()==sample['projection_sha256'])
        protocol=protocol and result['status']==expected and sample['status']==expected
        check('receipt_on_accept_only_'+str(Path(sample['result_path']).relative_to(ROOT)),
              bool(result['evidence_id'])==(expected=='VERIFIED'))
        if expected=='VERIFIED':
            if result['checker_result'].get('stdout'):
                kernel=json.loads(result['checker_result']['stdout'])
                check('actual_checked_count_'+str(Path(sample['result_path']).relative_to(ROOT)),
                      kernel['checked']==result['counts']['rechecked']==result['counts']['scheduled'] and
                      kernel['total_declarations']==result['counts']['total'])
            else:
                check('only_exact_bytes_skip_parser_'+str(Path(sample['result_path']).relative_to(ROOT)),
                      result['counts']['scheduled']==0 and
                      all(d['reason']=='exact_export' for d in result['decisions']))
        else:
            check('failed_checks_count_unknown_'+str(Path(sample['result_path']).relative_to(ROOT)),
                  result['counts']['rechecked'] is None)
        if 'variant' in sample:
            key=(sample['repetition'],sample['variant'],sample['arm'])
            projections[key]=projection(result)
            selection_counts[(sample['variant'],sample['arm'])].add(tuple(result['counts'][key]
                for key in ('scheduled','rechecked','reused','total')))
    else:
        config=json.loads(Path(resources['command'][1]).read_bytes())
        check('direct_configuration_'+str(process_path.relative_to(ROOT)),
              config['permitted_axioms']==['propext','Classical.choice','Quot.sound'] and
              config['unpermitted_axiom_hard_error'] is True and config['num_threads']==1 and
              config['nat_extension'] is True and config['string_extension'] is True and
              not config.get('parse_only',False) and
              config['export_file_path']==manifest['variants'][sample['variant']]['path'])
    check('expected_protocol_'+str(process_path.relative_to(ROOT)),protocol==sample['protocol_valid']==True)
    recomputed_outcomes.append(protocol)

for repetition in range(5):
    for variant in variants:
        for mode in ('full','incremental'):
            old=projections[(repetition,variant,'baseline-python-'+mode)]
            new=projections[(repetition,variant,'native-'+mode)]
            check(f'decision_witness_equality_{repetition}_{variant}_{mode}',canonical(old)==canonical(new))

# Independently replay randomized job scheduling; all comparisons pair by repeat.
rng=random.Random(20261016)
for repetition in range(5):
    backends=['baseline-python','native'];rng.shuffle(backends)
    jobs=[(v,a) for v in variants for a in arms];rng.shuffle(jobs)
    seed_order=report['execution_order'][2*repetition]
    job_order=report['execution_order'][2*repetition+1]
    check(f'seed_order_{repetition}',seed_order['order']==backends)
    check(f'job_order_{repetition}',job_order['order']==[dict(variant=v,arm=a) for v,a in jobs])
    for sample in (s for s in report['samples'] if s['repetition']==repetition):
        check(f'position_{repetition}_{sample["variant"]}_{sample["arm"]}',
              jobs[sample['position']]==(sample['variant'],sample['arm']))

medians={}
comparisons={}
for variant in variants:
    medians[variant]={}
    for arm in arms:
        samples=[s for s in report['samples'] if s['variant']==variant and s['arm']==arm]
        values={metric:statistics.median(s['resources'][metric] for s in samples) for metric in metrics}
        medians[variant][arm]=values
        check(f'reported_medians_{variant}_{arm}',all(equal(values[m],report['medians'][variant][arm]['resources'][m]) for m in metrics))
        for phase in report['medians'][variant][arm]['phases']:
            median=statistics.median(s['phases'][phase] for s in samples if phase in s.get('phases',{}))
            check(f'reported_phase_{variant}_{arm}_{phase}',equal(median,report['medians'][variant][arm]['phases'][phase]))
    native=medians[variant]['native-incremental']
    comparisons[variant]={}
    for reference in ('baseline-python-full','baseline-python-incremental','native-full','baseline-direct-full','current-direct-full'):
        ref=medians[variant][reference]
        comparisons[variant][reference]={metric:dict(reference=ref[metric],native=native[metric],
            reduction_percent=100*(ref[metric]-native[metric])/ref[metric],
            reference_over_native=ref[metric]/native[metric]) for metric in metrics}

recomputed_economics={}
for offset,variant in enumerate(('early-definition','unrelated-definition')):
    samples={(s['repetition'],s['arm']):s for s in report['samples'] if s['variant']==variant}
    native=[samples[(rep,'native-incremental')]['resources']['wall_seconds'] for rep in range(5)]
    direct=[samples[(rep,'current-direct-full')]['resources']['wall_seconds'] for rep in range(5)]
    ratio=statistics.median(native)/statistics.median(direct)
    rng=random.Random(20261016+offset)
    boot=[]
    for _ in range(10000):
        indices=rng.choices(range(5),k=5) if False else [rng.randrange(5) for _ in range(5)]
        boot.append(statistics.median(native[i] for i in indices)/statistics.median(direct[i] for i in indices))
    boot.sort(); interval=[boot[int(.025*9999)],boot[int(.975*9999)]]
    wins=sum(a<b for a,b in zip(native,direct))
    passed=ratio<1 and wins>2.5 and interval[1]<1
    recorded=report['economics'][variant]
    check('economic_recalculation_'+variant,equal(ratio,recorded['median_ratio']) and
          wins==recorded['paired_wins'] and recorded['paired_count']==5 and
          all(equal(a,b) for a,b in zip(interval,recorded['bootstrap_ratio_interval_95'])) and
          passed==recorded['passed'])
    recomputed_economics[variant]=dict(paired_count=5,paired_wins=wins,median_ratio=ratio,
        bootstrap_ratio_interval_95=interval,passed=passed,
        pairs=[dict(repetition=rep,native_wall_seconds=native[rep],direct_wall_seconds=direct[rep]) for rep in range(5)])

for variant in variants:
    construction=report['construction'][variant]
    sums={metric:sum(p[metric] for p in construction['processes'].values()) for metric in ('wall_seconds','cpu_seconds')}
    check('construction_sum_'+variant,all(equal(sums[m],construction['construction_sum'][m]) for m in sums))
    for arm in arms:
        check('component_addition_'+variant+'_'+arm,all(equal(medians[variant][arm][m]+sums[m],report['component_addition_totals'][variant][arm][m]) for m in sums))
        export=construction['processes'].get('export_process')
        check('export_addition_'+variant+'_'+arm,all(equal(medians[variant][arm][m]+export[m],report['export_plus_verification_subtotals'][variant][arm][m]) if export else report['export_plus_verification_subtotals'][variant][arm][m] is None for m in sums))
check('251_original_benchmark_gates_true',len(report['gates'])==251 and all(g['passed'] for g in report['gates']))
check('correctness_status_consistent',report['correctness_passed'] and all(recomputed_outcomes))
check('no_speedup_status_consistent',not any(e['passed'] for e in recomputed_economics.values()) and
      report['economic_passed'] is False and report['economic_status']=='NO_SPEEDUP' and report['status']=='NO_SPEEDUP')

review=dict(schema='mathgraph.native-benchmark-independent-review.v1',
    scope='Local host only; read-only recomputation, no benchmark code imported and no checker reruns.',
    exact_input=dict(path=str(SOURCE),sha256=hashlib.sha256(raw).hexdigest(),
        current_engine_sha256=report['current_engine_snapshot']['sha256'],baseline_engine_sha256=report['baseline_source_sha256'],
        baseline_commit=report['baseline_ref'],workload_manifest_sha256=report['workload_manifest_sha256']),
    sample_count=len(report['samples']),seed_count=len(report['seeds']),paired_repetitions=5,
    reported_correctness_gates=251,independent_checks=len(checks),checks_passed=all(c['passed'] for c in checks),
    failures=[c for c in checks if not c['passed']],checks=checks,medians=medians,comparisons=comparisons,
    economic_result='NO_SPEEDUP',economics=recomputed_economics,
    selection_counts={v:{a:[dict(zip(('scheduled','rechecked','reused','total'),x)) for x in counts]
        for (vv,a),counts in selection_counts.items() if vv==v} for v in variants},
    fairness=dict(matrix='Six arms, six variants, five fresh-process repetitions; deterministic shuffled jobs. Paired by repetition, not adjacent in time.',
        baseline='Exact Git 9ac engine and historically SHA-matching frozen Rust binaries; current raw Rust also measured. Fresh full adapters disable reuse and have separate caches. Each incremental call names its own baseline seed evidence.',
        provenance='Current and baseline binaries captured before measurement. Exact export pins and strict direct-kernel axiom/configuration policy validated.',
        evidence='All raw process records, adapter result hashes, copied phase data, status/exit-code outcomes, check counts, decision witnesses and negative no-receipt outcomes validated.',
        measurement_noise='Wall clock polling resolution about10ms. Later samples show drift; five pairs and bootstrap rule do not establish cross-host speedup. No primary paired economic gate passes.'),
    memory=dict(definition='Linux wait4 ru_maxrss in KiB for the waited command, including any propagated pre-exec inherited peak/children accounting; not sampled post-exec steady-state and not aggregate simultaneous process-tree RSS.',
        contamination='Visible inherited harness RSS: all repeat1 samples have a258568KiB floor and almost all repeat3/4 samples have268480KiB. Raw Rust and native arms share it as the parent retains parsed projections.',
        reductions_usable_for_optimization_claim=False,
        note='RSS reductions above preserve arithmetic on reported raw medians only. They are not valid claims of native memory savings; separate isolated post-exec measurement is needed.'),
    construction_costs=dict(definition='Preserved source build and export commands measured once outside repeated verification. Component totals add those observed times to verification medians.',
        actual_single_command_end_to_end_measurement=False,
        note='No component-addition total or export-plus-verification subtotal is a newly timed end-to-end command. Invalid NDJSON mutation cases lack source construction/export and are labeled accordingly.'),
    conclusion='Native identity substantially reduces adapter time versus Python and reduces checking work, but changed-input incremental verification is slower than direct fresh Rust for both primary edits; do not promote the requested direct-check speedup.')
OUT.write_text(json.dumps(review,indent=2)+'\n')
print(json.dumps(dict(path=str(OUT),sha256=digest(OUT),checks=review['independent_checks'],passed=review['checks_passed'],failures=review['failures'],economics=recomputed_economics),indent=2))
