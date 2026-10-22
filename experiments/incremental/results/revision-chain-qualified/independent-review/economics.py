"""Independent standard-library checks of lifecycle arithmetic and statistics.

No production adapter, benchmark, verifier, or issuer code is imported. These
checks establish consistency of the recorded observations, not elapsed-time
authenticity or kernel acceptance. Historical issuer HMACs are outside scope.
"""
import json
import math
import random
import statistics


PRIMARY = 'Sum of measured constructor/start, all accepted apply APIs, supported shutdown. No projected amortization.'
DIRECT = 'Sum of actual fresh full Rust command wall durations at genesis and every exact sealed revision; process creation and exit included.'
CONTINUOUS = 'Uninterrupted constructor/start through all accepted applies and supported close; no intervening independent oracles or evidence packaging.'
CONTINUOUS_DIRECT = 'Uninterrupted fresh full Rust commands at genesis and every identical accepted revision; exact input preparation is outside timing.'
COMPONENT_SCOPE = ('Observed constructor/start + every production apply + supported close API intervals; '
                   'intervening independent oracles and harness evidence packaging are excluded. '
                   'Direct comparator is a fresh full Rust command at genesis and every exact accepted revision.')
CPU_SCOPE = ('Adapter + completed-child resource CPU + live producer/index/kernel procfs CPU; '
             'SC_CLK_TCK granularity applies to live daemons. Separately summed observed API intervals; '
             'direct full Rust uses completed-child CPU per actual fresh command.')
CLOSE_SCOPE = 'Supported adapter close terminates/waits daemons and removes private files; no Rust EOF/destructor guarantee.'
WARM_SCOPE = 'warm authenticated session update versus fresh full Rust command'


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode()


def same(actual, expected, label):
    require(canonical(actual) == canonical(expected), label + ' changed')


def duration(value, label, *, positive=False):
    require(type(value) in (int, float) and math.isfinite(value) and
            (value > 0 if positive else value >= 0), 'invalid ' + label)
    return value


def integer(value, label, *, minimum=0):
    require(type(value) is int and value >= minimum, 'invalid ' + label)
    return value


def paired_statistics(candidate, direct, *, seed, bootstrap_repetitions=10000):
    """Paired resampling of median ratios, independently recomputed in full."""
    require(type(candidate) is list and type(direct) is list and
            len(candidate) == len(direct) and len(candidate) > 0, 'missing paired durations')
    for label, observations in (('candidate', candidate), ('direct', direct)):
        for value in observations:
            duration(value, label + ' observation', positive=True)
    integer(seed, 'bootstrap seed')
    integer(bootstrap_repetitions, 'bootstrap count', minimum=1)
    count = len(candidate)
    ratio = statistics.median(candidate) / statistics.median(direct)
    generator = random.Random(seed)
    resampled_ratios = []
    for _ in range(bootstrap_repetitions):
        indices = [generator.randrange(count) for _ in range(count)]
        candidate_median = statistics.median(candidate[i] for i in indices)
        direct_median = statistics.median(direct[i] for i in indices)
        resampled_ratios.append(candidate_median / direct_median)
    resampled_ratios.sort()
    interval = [resampled_ratios[int(quantile * (bootstrap_repetitions - 1))]
                for quantile in (0.025, 0.975)]
    wins = sum(left < right for left, right in zip(candidate, direct))
    speedup = ratio < 1 and wins > count / 2 and interval[1] < 1
    return dict(passed=speedup, status='SPEEDUP' if speedup else 'NO_SPEEDUP',
                apply_median_wall_seconds=statistics.median(candidate),
                direct_median_wall_seconds=statistics.median(direct), median_ratio=ratio,
                paired_wins=wins, paired_count=count,
                bootstrap_ratio_interval_95=interval,
                bootstrap_repetitions=bootstrap_repetitions, bootstrap_seed=seed,
                setup_in_timed_update=False, scope=WARM_SCOPE)


def incomplete(expected, count):
    if count < 5:
        expected.update(observed_status=expected['status'],
                        status='INCOMPLETE_FEWER_THAN_FIVE_PAIRS', passed=False)
    return expected


def economic_series(candidate, direct, seed, extras=None):
    expected = paired_statistics(candidate, direct, seed=seed)
    expected.update(extras or {})
    return incomplete(expected, len(candidate))


def _seconds_mapping(mapping, label):
    require(type(mapping) is dict, label + ' is missing')
    for field, value in mapping.items():
        if field.endswith('_seconds'):
            duration(value, label + '.' + field)


def validate_economics(report):
    """Validate all recorded component sums and all bootstrap output series.

    The outer reviewer must validate raw command/result bytes and the positive
    exact-source qualification/smoke contract. This helper independently checks
    counts, durations, component arithmetic, continuous interval lower bounds,
    metadata describing the measured comparator, and every statistical field.
    """
    repetitions = integer(report['repetitions'], 'repetitions', minimum=1)
    revisions = 4 * integer(report['cycles'], 'cycles', minimum=1)
    profiles = report['profiles']
    require(type(profiles) is dict and len(profiles) > 0, 'missing economic profiles')
    policy = report['measurement_policy']
    for field, expected in (('primary', PRIMARY), ('direct', DIRECT),
                            ('continuous_primary', CONTINUOUS),
                            ('continuous_direct', CONTINUOUS_DIRECT)):
        same(policy[field], expected, 'measurement policy ' + field)
    counters = dict(profiles=0, pairs=0, accepted_revisions=0, economic_series=0,
                    bootstrap_resamples=0)
    for profile, evidence in profiles.items():
        pairs = evidence['pairs']
        require(type(pairs) is list and len(pairs) == repetitions,
                'incomplete economic pairs for ' + profile)
        for pair_number, pair in enumerate(pairs):
            label = profile + ':' + str(pair_number)
            require(pair['completed'] is True and pair['correctness_passed'] is True,
                    label + ' incomplete pair')
            same(pair['repetition'], pair_number, label + ' repetition')
            same(pair['accepted_revisions'], revisions, label + ' accepted count')
            steps = pair['steps']
            require(type(steps) is list and len(steps) == revisions, label + ' missing revisions')
            setup, genesis = pair['setup'], pair['genesis']['direct_rust']
            _seconds_mapping(setup, label + ' setup')
            for field in ('wall_seconds', 'completed_child_cpu_seconds'):
                duration(genesis[field], label + ' direct genesis ' + field,
                         positive=field == 'wall_seconds')
            require(setup['wall_seconds'] >= setup['constructor_wall_seconds'] + setup['start_wall_seconds'],
                    label + ' setup excludes constructor/start')
            wall_applies, cpu_applies, wall_directs, cpu_directs = [], [], [], []
            for index, step in enumerate(steps, 1):
                same(step['revision'], index, label + ' revision')
                wall_applies.append(duration(step['apply_wall_seconds'], label + ' apply wall', positive=True))
                cpu_applies.append(duration(step['apply_cpu_seconds'], label + ' apply CPU'))
                direct = step['direct_rust']
                wall_directs.append(duration(direct['wall_seconds'], label + ' direct wall', positive=True))
                cpu_directs.append(duration(direct['completed_child_cpu_seconds'], label + ' direct CPU'))
                _seconds_mapping(step['phases'], label + ' phases')
                require(step['apply_wall_seconds'] >= step['phases']['end_to_end_seconds'],
                        label + ' apply outer interval excludes production API')
            components = pair['components']
            close_wall = duration(components['close_wall_seconds'], label + ' close wall')
            expected = dict(setup_wall_seconds=setup['wall_seconds'], apply_wall_seconds=wall_applies,
                            close_wall_seconds=close_wall,
                            direct_genesis_wall_seconds=genesis['wall_seconds'],
                            direct_revision_wall_seconds=wall_directs, accepted_revisions=revisions,
                            api_component_sum_wall_seconds=setup['wall_seconds'] + sum(wall_applies) + close_wall,
                            direct_full_rust_component_sum_wall_seconds=genesis['wall_seconds'] + sum(wall_directs),
                            scope=COMPONENT_SCOPE, close_scope=CLOSE_SCOPE)
            same(components, expected, label + ' wall components')
            cpu_components = pair['cpu_components']
            close_cpu = duration(cpu_components['close_cpu_seconds'], label + ' close CPU')
            expected_cpu = dict(setup_cpu_seconds=setup['cpu_seconds'], apply_cpu_seconds=cpu_applies,
                                close_cpu_seconds=close_cpu,
                                direct_genesis_cpu_seconds=genesis['completed_child_cpu_seconds'],
                                direct_revision_cpu_seconds=cpu_directs,
                                api_component_sum_cpu_seconds=setup['cpu_seconds'] + sum(cpu_applies) + close_cpu,
                                direct_full_rust_component_sum_cpu_seconds=genesis['completed_child_cpu_seconds'] + sum(cpu_directs),
                                scope=CPU_SCOPE)
            same(cpu_components, expected_cpu, label + ' CPU components')
            elapsed = duration(pair['observed_constructor_through_close_wall_seconds'], label + ' observed elapsed', positive=True)
            require(elapsed >= expected['api_component_sum_wall_seconds'] + expected['direct_full_rust_component_sum_wall_seconds'],
                    label + ' observed elapsed excludes measured interleaving')
            if pair_number == 0:
                cold = pair['cold_replay']
                duration(cold['setup_wall_seconds'], label + ' cold setup', positive=True)
                duration(cold['close_wall_seconds'], label + ' cold close')
                _seconds_mapping(cold['ready'], label + ' cold ready')
                require(cold['setup_wall_seconds'] >= cold['ready']['wall_seconds'],
                        label + ' cold setup excludes replay API')
            continuous = pair['continuous']
            same(continuous['order'], ['candidate', 'direct'] if pair_number % 2 == 0 else ['direct', 'candidate'],
                 label + ' continuous order')
            require(continuous['completed'] is True, label + ' incomplete continuous pair')
            candidate, direct = continuous['candidate'], continuous['direct']
            for name, arm in (('candidate', candidate), ('direct', direct)):
                require(arm['completed'] is True, label + ' continuous ' + name + ' incomplete')
                duration(arm['wall_seconds'], label + ' continuous ' + name + ' wall', positive=True)
                duration(arm['cpu_seconds'], label + ' continuous ' + name + ' CPU', positive=True)
            require(len(candidate['steps']) == revisions and len(direct['commands']) == revisions + 1,
                    label + ' continuous revision/command count')
            command_walls, command_cpus = [], []
            for revision, command in enumerate(direct['commands']):
                same(command['revision'], revision, label + ' continuous direct revision')
                command_walls.append(duration(command['wall_seconds'], label + ' continuous direct command wall', positive=True))
                command_cpus.append(duration(command['completed_child_cpu_seconds'], label + ' continuous direct command CPU'))
            require(direct['wall_seconds'] >= sum(command_walls), label + ' continuous direct interval excludes commands')
            require(direct['cpu_seconds'] + 1e-9 >= sum(command_cpus), label + ' continuous direct CPU excludes children')
            candidate_apis = []
            for actual in candidate['steps']:
                _seconds_mapping(actual['timings'], label + ' continuous timings')
                candidate_apis.append(actual['timings']['end_to_end_seconds'])
            _seconds_mapping(candidate['genesis']['ready'], label + ' continuous ready')
            require(candidate['wall_seconds'] >= candidate['genesis']['ready']['wall_seconds'] + sum(candidate_apis),
                    label + ' continuous candidate interval excludes APIs')
            counters['pairs'] += 1
            counters['accepted_revisions'] += revisions

        wall = economic_series([p['components']['api_component_sum_wall_seconds'] for p in pairs],
                               [p['components']['direct_full_rust_component_sum_wall_seconds'] for p in pairs],
                               20261022, dict(scope=PRIMARY, comparator=DIRECT, setup_in_timed_update=True,
                               accepted_revisions_per_pair=revisions, paired_sequences=repetitions,
                               claim_status='QUALIFICATION_REQUIRES_FIVE_EXACT_PAIRED_LIFETIMES' if repetitions < 5 else 'OBSERVED_COMPONENT_SUMS'))
        same(evidence['economics'], wall, profile + ' lifetime wall economics')
        cpu = economic_series([p['cpu_components']['api_component_sum_cpu_seconds'] for p in pairs],
                              [p['cpu_components']['direct_full_rust_component_sum_cpu_seconds'] for p in pairs],
                              20261023, dict(scope=CPU_SCOPE, measurement='cpu_seconds', setup_in_timed_update=True))
        same(evidence['cpu_economics'], cpu, profile + ' lifetime CPU economics')
        for name, field, seed in (('continuous_economics', 'wall_seconds', 20261024),
                                  ('continuous_cpu_economics', 'cpu_seconds', 20261025)):
            continuous_expected = economic_series([p['continuous']['candidate'][field] for p in pairs],
                                                  [p['continuous']['direct'][field] for p in pairs], seed,
                                                  dict(scope=CONTINUOUS, comparator=CONTINUOUS_DIRECT, measurement=field,
                                                       setup_in_timed_update=True, accepted_revisions_per_pair=revisions,
                                                       paired_sequences=repetitions))
            same(evidence[name], continuous_expected, profile + ' ' + name)
        require(len(evidence['revision_economics']) == revisions, profile + ' missing revision economics')
        for index, observation in enumerate(evidence['revision_economics']):
            expected = economic_series([p['steps'][index]['apply_wall_seconds'] for p in pairs],
                                       [p['steps'][index]['direct_rust']['wall_seconds'] for p in pairs], 20261022 + index)
            same(observation, dict(revision=index + 1, economics=expected), profile + ' revision economics')
        counters['profiles'] += 1
        counters['economic_series'] += revisions + 4
        counters['bootstrap_resamples'] += (revisions + 4) * 10000
    return counters
