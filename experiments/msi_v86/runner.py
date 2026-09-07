#!/usr/bin/env python3
"""v86: measure canonical-spine work, then replay-gated causal tournament."""
import difflib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('v85', HERE.parent / 'msi_v85' / 'optimizer.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

CANON = '''    fn canon_spine(&mut self, spine: S<'t>) -> S<'t> {
        match spine {
            Spine::Empty => spine,
            Spine::Snoc { prev, elim, .. } => {
                let cprev = self.canon_spine(prev);
                let celim = match elim.view() {
                    ElimView::App(a) => {
                        let ca = self.canonicalize_for_spine(a);
                        Elim::app(ca)
                    }
                    ElimView::Proj { ty_name, idx } => Elim::proj(ty_name, idx),
                };
                self.spine_snoc_hc(cprev, celim)
            }
        }
    }
'''
SNOC = '                let s = value::spine_snoc(arena, prev, elim);'
STATS = '''// v86 diagnostic counters. Only present in counted binaries.
struct V86Stats { counts: std::cell::Cell<[u64; 5]> }
impl Drop for V86Stats {
    fn drop(&mut self) {
        let c = self.counts.get();
        eprintln!("V86_METRICS calls={} canonical={} visited={} snoc_calls={} allocations={}", c[0], c[1], c[2], c[3], c[4]);
    }
}
std::thread_local! {
    static V86_STATS: V86Stats = const { V86Stats { counts: std::cell::Cell::new([0; 5]) } };
}
#[inline]
fn v86_count(i: usize) {
    V86_STATS.with(|s| {
        let mut c = s.counts.get();
        c[i] += 1;
        s.counts.set(c);
    });
}
'''

def patch(text, recipes):
    if not recipes:
        return text
    if len(recipes) != 1 or recipes[0] not in ('canon-fast', 'canon-control', 'count-base', 'count-fast', 'count-control'):
        raise m.Rejected('INCOMPATIBLE_RECIPES')
    recipe = recipes[0]
    counted = recipe.startswith('count-')
    fast = recipe.endswith('fast')
    if text.count(CANON) != 1:
        raise m.Rejected('SOURCE_ANCHOR_MISMATCH:canon_spine')
    if counted and text.count(SNOC) != 1:
        raise m.Rejected('SOURCE_ANCHOR_MISMATCH:spine_snoc_hc')
    prefix = ''
    if recipe != 'count-base':
        prefix = '        if spine.is_canonical() {\n'
        if counted:
            prefix += '            v86_count(1);\n'
        if fast:
            prefix += '            return spine;\n'
        else:
            prefix += '            std::hint::black_box(spine);\n'
        prefix += '        }\n'
    elif counted:
        prefix = '        if spine.is_canonical() { v86_count(1); }\n'
    if counted:
        prefix = '        v86_count(0);\n' + prefix
    body = CANON
    body = body.replace('        match spine {', prefix + '        match spine {', 1)
    if counted:
        body = body.replace('                let cprev =', '                v86_count(2);\n                let cprev =', 1)
        body = body.replace('                self.spine_snoc_hc(cprev, celim)', '                v86_count(3);\n                self.spine_snoc_hc(cprev, celim)', 1)
    text = text.replace(CANON, body, 1)
    if counted:
        text = STATS + text
        text = text.replace(SNOC, '                v86_count(4);\n' + SNOC, 1)
    return text

m.apply_recipes = patch
m.RECIPES = {'canon-fast': ('canonical predicate', 'return canonical spine')}
m.CONFLICTS = {}
m.MAX_BUILDS = 7
m.MAX_FULL = 1
m.WALL_BUDGET = 150 * 60
NAMES = ('calls', 'canonical', 'visited', 'snoc_calls', 'allocations')

def metrics(path):
    totals = dict.fromkeys(NAMES, 0)
    found = 0
    for line in path.read_text(errors='replace').splitlines():
        if 'V86_METRICS ' not in line:
            continue
        values = dict((k, int(v)) for k, v in re.findall(r'\b(\w+)=(\d+)', line))
        if not all(k in values for k in NAMES):
            raise m.Infrastructure('MALFORMED_METRICS')
        for k in NAMES:
            totals[k] += values[k]
        found += 1
    if not found:
        raise m.Infrastructure('MISSING_METRICS:' + str(path))
    return totals

def measure(t, corpora, passes, phase):
    arms = ('base', 'candidate', 'control', 'aa')
    mapping = {'base': (), 'candidate': ('canon-fast',), 'control': ('canon-control',), 'aa': ()}
    rows = {c: {a: [] for a in arms} for c in corpora}
    for p in range(passes):
        for corpus in corpora:
            for arm in arms[p % len(arms):] + arms[:p % len(arms)]:
                seconds, _ = t.run_binary(mapping[arm], corpus, f'{phase}-{p}-{corpus}-{arm}')
                rows[corpus][arm].append(seconds)
                t.record('timing', phase=phase, pass_index=p, corpus=corpus, arm=arm, seconds=seconds)
    scores = {name: m.score(rows, a, b, corpora) for name, a, b in (
        ('candidate', 'candidate', 'base'), ('control', 'control', 'base'),
        ('separation', 'candidate', 'control'), ('aa', 'aa', 'base'))}
    t.record('v86_scores', phase=phase, scores=scores)
    return scores

def acceptable(scores, threshold):
    return (scores['candidate']['geomean'] <= -threshold
            and scores['separation']['geomean'] <= -threshold
            and all(r <= 1.01 for r in scores['candidate']['ratios'].values())
            and abs(scores['aa']['geomean']) <= 0.01)

def run(root, source, arena):
    t = m.Tournament(root, source, arena, budget=m.WALL_BUDGET)
    result = {'base': m.BASE, 'arena': m.ARENA, 'decision': 'RUNNING', 'promotion': None, 'metrics': {}, 'scores': {}}
    try:
        t.prepare()
        t.build(())
        for corpus in m.CORPORA:
            t.replay((), corpus)
        # Counted binaries are diagnostic only; never benchmark or promote them.
        for arm in ('count-base', 'count-control', 'count-fast'):
            t.build((arm,))
            result['metrics'][arm] = {}
            for corpus in m.CORPORA:
                t.replay((arm,), corpus)
                path = t.root / 'logs' / ('replay-' + arm + '-' + corpus + '.stderr')
                result['metrics'][arm][corpus] = metrics(path)
        for corpus in m.CORPORA:
            base = result['metrics']['count-base'][corpus]
            control = result['metrics']['count-control'][corpus]
            fast = result['metrics']['count-fast'][corpus]
            if control['canonical'] != fast['canonical']:
                t.record('count_difference', corpus=corpus, control=control, candidate=fast)
            if fast['visited'] > control['visited'] or fast['snoc_calls'] > control['snoc_calls']:
                t.record('work_regression', corpus=corpus, control=control, candidate=fast)
        total_fast = sum(result['metrics']['count-fast'][c]['canonical'] for c in m.CORPORA)
        saved = sum(result['metrics']['count-control'][c]['visited'] - result['metrics']['count-fast'][c]['visited'] for c in m.CORPORA)
        t.record('structural_attachment', canonical_hits=total_fast, saved_visits=saved, metrics=result['metrics'])
        if total_fast == 0 or saved <= 0:
            result['decision'] = 'NO_MEASURED_WORK_REDUCTION__DO_NOT_RETAIN'
            return result
        t.build(('canon-control',))
        t.build(('canon-fast',))
        if m.digest(t.binaries[('canon-fast',)]) == m.digest(t.binaries[()]):
            result['decision'] = 'NO_BINARY_DELTA__DO_NOT_RETAIN'
            return result
        for corpus in m.CORPORA:
            t.replay(('canon-control',), corpus)
            t.replay(('canon-fast',), corpus)
        for phase, corpora, passes, threshold in (
            ('screen', ('std', 'cedar'), 2, .005),
            ('mathlib-screen', ('mathlib',), 1, .005),
            ('full', m.CORPORA, 5, .01),
            ('confirm', m.CORPORA, 3, .01)):
            if phase == 'full':
                t.full_evaluations += 1
            scores = measure(t, corpora, passes, phase)
            result['scores'][phase] = scores
            if not acceptable(scores, threshold):
                result['decision'] = 'NO_ISOLATED_REPEATABLE_GAIN__DO_NOT_RETAIN'
                result['rejected_at'] = phase
                return result
        result['decision'] = 'PROVISIONAL_BENCHMARK_CHAMPION__CAUSAL_CONTROL_SEPARATED'
        result['promotion'] = 'canon-fast'
        old = (Path(source) / 'src/eval.rs').read_text()
        new = patch(old, ('canon-fast',))
        (t.root / 'champion.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='a/src/eval.rs', tofile='b/src/eval.rs')))
        shutil.copy2(t.binaries[('canon-fast',)], t.root / 'champion.bin')
        t.record('promotion', candidate='canon-fast', scope='FROZEN_THREE_CORPORA', status=result['decision'])
        return result
    except Exception as exc:
        result['decision'] = 'INFRASTRUCTURE_OR_REPLAY_FAILURE'
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        result['builds'] = t.builds
        result['full_evaluations'] = t.full_evaluations
        (t.root / 'summary.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        t.record('v86_final', decision=result['decision'], summary=str(t.root / 'summary.json'))

def selftest():
    sample = 'prefix\n' + CANON + '\n' + SNOC + '\n'
    for recipe in ('canon-fast', 'canon-control', 'count-base', 'count-fast', 'count-control'):
        out = patch(sample, (recipe,))
        assert out != sample
        assert out.count('fn canon_spine(') == 1
        assert ('return spine;' in out) == recipe.endswith('fast')
        assert ('V86_METRICS' in out) == recipe.startswith('count-')
    assert patch(sample, ()) == sample
    for bad in (('canon-fast', 'canon-control'), ('missing',)):
        try:
            patch(sample, bad)
        except m.Rejected:
            pass
        else:
            raise AssertionError('invalid recipe accepted')
    try:
        patch('changed source', ('canon-fast',))
    except m.Rejected:
        pass
    else:
        raise AssertionError('missing anchor accepted')
    assert acceptable({'candidate': {'geomean': -.02, 'ratios': {'std': .98}}, 'separation': {'geomean': -.02}, 'aa': {'geomean': 0}}, .01)
    assert not acceptable({'candidate': {'geomean': -.02, 'ratios': {'std': .98}}, 'separation': {'geomean': 0}, 'aa': {'geomean': 0}}, .01)
    assert not acceptable({'candidate': {'geomean': -.02, 'ratios': {'std': .98}}, 'separation': {'geomean': -.02}, 'aa': {'geomean': .02}}, .01)
    print('V86_SELFTEST=PASS')

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='/tmp/v86/results')
    p.add_argument('--source')
    p.add_argument('--arena')
    p.add_argument('--selftest', action='store_true')
    args = p.parse_args()
    if args.selftest:
        selftest()
    else:
        if not args.source or not args.arena:
            p.error('--source and --arena are required')
        run(args.root, args.source, args.arena)
