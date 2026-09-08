#!/usr/bin/env python3
"""Compare independent v88 timing with the frozen first run; never promote."""
import hashlib
import json
import math
import statistics
import sys
import zipfile
from pathlib import Path

FIRST_ARTIFACT = 10036840243
FIRST_SHA256 = '3e2bf2036962f99578eafa3cb0350006bda8884e1b6c82b3140ac4e310a0e4b3'
FIRST_RUN = 34172621188
CORPORA = {'std': 'fc440bd35aa4ecb244836eef0c2e31c578ac4460f42665f4e8305cbc2cd2104d',
           'cedar': '757e3638420e8850e451b3950e8504be650cae47270b9e4b41cc31abcb00b2d2',
           'mathlib': 'ca2ec20fd063b61e71867b2975c81bd989af9f879b4886b8f08cd23c767a47bb'}
BASE = '08ddb26718c86213262943ca19ae8cf1b03fa922'
ARENA = '91f376e4baacf2df0c478e7173bccb2a6adac5c5'
BUILD = 'native-fresh-pgo-4threads'

def require(condition, message):
    if not condition:
        raise ValueError(message)

def validate(d):
    require(d['status'] == 'COMPLETE', 'incomplete benchmark')
    require((d['base'], d['arena'], d['build']) == (BASE, ARENA, BUILD), 'benchmark scope changed')
    require(set(d['corpora']) == set(CORPORA), 'corpus set changed')
    for name, expected in CORPORA.items():
        e = d['corpora'][name]
        require(e['input_sha256'] == expected, 'corpus hash changed: ' + name)
        require(e['exact_replay'] == 'PASS', 'missing exact replay: ' + name)
        ref, cand = e['reference'], e['candidate']
        require(ref['rc'] == cand['rc'] == 0, 'reference failed: ' + name)
        for arm in (ref, cand):
            require(arm['stdout_sha256'] == ref['stdout_sha256'] and
                    arm['stderr_sha256'] == ref['stderr_sha256'], 'output mismatch: ' + name)
        runs = e['runs']
        require(len(runs) == 10, 'missing timing passes: ' + name)
        for i in range(5):
            pair = [r for r in runs if r['pass'] == i]
            require(len(pair) == 2 and {r['arm'] for r in pair} == {'control', 'candidate'}, 'unbalanced pass')
            require([r['arm'] for r in pair] == (['control', 'candidate'] if i % 2 == 0 else ['candidate', 'control']), 'order changed')
        for arm in ('control', 'candidate'):
            xs = [r for r in runs if r['arm'] == arm]
            require(all(r['rc'] == 0 and r['stdout_sha256'] == ref['stdout_sha256'] and
                        r['stderr_sha256'] == ref['stderr_sha256'] and
                        math.isfinite(r['seconds']) and r['seconds'] > 0 for r in xs), 'timing/replay failure')
            median = statistics.median(r['seconds'] for r in xs)
            require(math.isclose(median, e[arm + '_median'], rel_tol=1e-10), 'median mismatch')
        delta = 100 * (e['candidate_median'] / e['control_median'] - 1)
        require(math.isclose(delta, e['delta_percent'], abs_tol=1e-8), 'delta mismatch')
    geo = 100 * (math.prod(1 + d['corpora'][c]['delta_percent']/100 for c in CORPORA)**(1/3)-1)
    require(math.isclose(geo, d['geomean_delta_percent'], abs_tol=1e-8), 'geomean mismatch')
    return d

def decide(first, repeat, ablation):
    validate(first)
    validate(repeat)
    require(ablation['source_ablation'] == 'EXACT' and ablation['control_is_ablated_candidate'], 'ablation not established')
    require(ablation['control_tree_sha256'] == ablation['restored_tree_sha256'], 'ablation tree mismatch')
    rows = {}
    for name in CORPORA:
        a, b = first['corpora'][name], repeat['corpora'][name]
        rows[name] = {'first_delta_percent': a['delta_percent'],
                      'repeat_delta_percent': b['delta_percent'],
                      'repeat_control_median': b['control_median'],
                      'repeat_candidate_median': b['candidate_median']}
    large = ('cedar', 'mathlib')
    repeated = all(rows[c]['first_delta_percent'] < 0 and rows[c]['repeat_delta_percent'] < 0 for c in large)
    geo = 100 * (math.prod(1 + rows[c]['repeat_delta_percent']/100 for c in large)**.5 - 1)
    strong = repeated and all(rows[c]['repeat_delta_percent'] <= -1 for c in large) and geo <= -1
    decision = 'STRONG_REPEAT__RELEASE_GATE_STILL_REQUIRED' if strong else ('SMALL_GAIN_REPEATED__NO_PROMOTION' if repeated else 'REPEAT_NOT_CONFIRMED__NO_PROMOTION')
    return {'decision': decision, 'large_corpus_repeat_geomean_percent': geo,
            'large_corpus_gain_repeated': repeated, 'corpora': rows,
            'first_run': FIRST_RUN, 'first_artifact': FIRST_ARTIFACT,
            'ablation': ablation, 'release_promoted': False,
            'next': 'Independent decisive-boundary repeat and official release qualification' if strong else 'Retain incumbent; diagnose or seek a measured separator'}

def main():
    if len(sys.argv) == 2 and sys.argv[1] == '--self-test':
        fixture = {'source_ablation':'EXACT', 'control_is_ablated_candidate':True,
                   'control_tree_sha256':'x', 'restored_tree_sha256':'x'}
        # Test the decision logic with explicit fake data; never report it as measured.
        globals()['validate'] = lambda d: d
        a = {'corpora': {c:{'delta_percent':-.3, 'control_median':1, 'candidate_median':.997} for c in CORPORA}}
        require(decide(a,a,fixture)['decision'] == 'SMALL_GAIN_REPEATED__NO_PROMOTION', 'small-gain decision')
        b = {'corpora': {c:{'delta_percent':.3, 'control_median':1, 'candidate_median':1.003} for c in CORPORA}}
        require(decide(a,b,fixture)['decision'] == 'REPEAT_NOT_CONFIRMED__NO_PROMOTION', 'negative decision')
        require(decide(a,a,fixture)['release_promoted'] is False, 'unexpected promotion')
        print('V89_DECISION_TESTS=PASS')
        return
    root = Path(sys.argv[1])
    raw = (root/'out'/'first-run.zip').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == FIRST_SHA256, 'first artifact digest mismatch')
    with zipfile.ZipFile(root/'out'/'first-run.zip') as z:
        first = json.loads(z.read('results.json'))
    repeat = json.loads((root/'out'/'results.json').read_text())
    ablation = json.loads((root/'out'/'ablation.json').read_text())
    result = decide(first, repeat, ablation)
    (root/'out'/'repeat-decision.json').write_text(json.dumps(result,indent=2)+'\n')
    print('V89_INDEPENDENT_REPEAT=PASS')
    print('V89_DECISION='+result['decision'])
    print('V89_LARGE_CORPUS_GEOMEAN_PERCENT=%.4f'%result['large_corpus_repeat_geomean_percent'])
    print('V89_RELEASE_PROMOTED=false')

if __name__ == '__main__':
    main()
