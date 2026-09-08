#!/usr/bin/env python3
"""v96: test empty-result canonicalization against a frozen kernel.

The v95 LLVM counts are diagnostic only: duplicate function entries and
mismatched-data warnings prevent using their sum as a call count. This run
uses independent, conservation-checked counters. No kernel change is promoted
by the driver; the measured candidate remains isolated until reviewed.
"""
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import time

BASE = '08ddb26718c86213262943ca19ae8cf1b03fa922'
ARENA = '91f376e4baacf2df0c478e7173bccb2a6adac5c5'
REPO = 'https://github.com/metalogiclabs/mathgraph-lean-kernel'
SOURCE_BLOB = 'c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
CORPORA = ('std', 'cedar', 'mathlib')
ROOT = Path(os.environ.get('V96_ROOT', '/tmp/v96')).resolve()

# Exactly one source-level change: an empty retained environment uses the
# already-existing lsub_base representation. No mask, slot, or cache key is
# otherwise changed. The source guard prevents applying this to another kernel.
OLD = """        let r = self.intern_frame(hash, out_mask, slots, lsub);
        self.tc_cache.prune_dm[slot] = (e as *const value::Env<'t> as usize, mask, Some(r));
"""
NEW = """        let r = if out_mask == 0 {
            self.lsub_base(lsub)
        } else {
            self.intern_frame(hash, out_mask, slots, lsub)
        };
        self.tc_cache.prune_dm[slot] = (e as *const value::Env<'t> as usize, mask, Some(r));
"""

# Diagnostic-only, per-thread counters. Worker threads are joined by
# check_all_declars before dump is called. The mutex is used only at thread
# exit, not on the hot path. No probe code is present in timed binaries.
PROBE = r'''use std::cell::Cell;
use std::sync::Mutex;
const N: usize = 8;
static TOTAL: Mutex<[u64; N]> = Mutex::new([0; N]);
struct Local(Cell<[u64; N]>);
impl Drop for Local {
    fn drop(&mut self) {
        let mut total = TOTAL.lock().unwrap();
        for (dst, src) in total.iter_mut().zip(self.0.get()) {
            *dst = dst.checked_add(src).expect("probe counter overflow");
        }
    }
}
thread_local! { static LOCAL: Local = const { Local(Cell::new([0; N])) }; }
#[inline]
pub fn record(index: usize) {
    LOCAL.with(|local| {
        let mut counts = local.0.get();
        counts[index] = counts[index].checked_add(1).expect("probe counter overflow");
        local.0.set(counts);
    });
}
pub fn dump() {
    let mut counts = *TOTAL.lock().unwrap();
    LOCAL.with(|local| {
        for (dst, src) in counts.iter_mut().zip(local.0.get()) {
            *dst = dst.checked_add(src).expect("probe counter overflow");
        }
    });
    eprintln!("V96_PROBE={}", serde_json::json!({
        "cold": counts[0], "framed": counts[1],
        "one_cons": counts[2], "other_cons": counts[3],
        "nil": counts[4], "empty": counts[5],
        "empty_framed": counts[6], "empty_cons": counts[7]
    }));
}
'''


def run(*args, cwd=None, env=None, stdin=None, stdout=None, stderr=None):
    return subprocess.run(args, cwd=cwd, env=env, stdin=stdin,
                          stdout=stdout, stderr=stderr, check=True)


def shell(script, cwd):
    run('nix', 'develop', '-c', 'bash', '-euo', 'pipefail', '-c', script, cwd=cwd)


def checkout(url, path, sha):
    if not path.exists():
        run('git', 'clone', '-q', url, str(path))
    run('git', '-C', str(path), 'checkout', '-q', sha)
    actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    assert actual == sha, (actual, sha)


def replace_once(text, old, new):
    assert text.count(old) == 1, 'Source patch does not match exactly once'
    return text.replace(old, new, 1)


def guarded_source(path):
    raw = path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    assert blob == SOURCE_BLOB, (blob, SOURCE_BLOB)
    return raw.decode()


def apply_candidate(path):
    original = guarded_source(path)
    path.write_text(replace_once(original, OLD, NEW))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_probe(source):
    p = source / 'src/eval.rs'
    text = guarded_source(p)
    start = """    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        let mut buf:"""
    insert = """    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        #[cfg(feature = "regression-probe")]
        {
            crate::regression_probe::record(0);
            match e {
                value::Env::Framed { .. } => crate::regression_probe::record(1),
                value::Env::Cons { parent, .. } if matches!(*parent, value::Env::Framed { .. }) => crate::regression_probe::record(2),
                value::Env::Cons { .. } => crate::regression_probe::record(3),
                value::Env::Nil { .. } => crate::regression_probe::record(4),
            }
        }
        let mut buf:"""
    text = replace_once(text, start, insert)
    end = """        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };
        let lsub = e.lsub();"""
    replacement = """        #[cfg(feature = "regression-probe")]
        if out_mask == 0 {
            crate::regression_probe::record(5);
            match e {
                value::Env::Framed { .. } => crate::regression_probe::record(6),
                value::Env::Cons { .. } => crate::regression_probe::record(7),
                value::Env::Nil { .. } => {},
            }
        }
        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };
        let lsub = e.lsub();"""
    p.write_text(replace_once(text, end, replacement))
    (source / 'src/regression_probe.rs').write_text(PROBE)
    lib = source / 'src/lib.rs'
    lib.write_text(lib.read_text() + '\n#[cfg(feature = "regression-probe")]\npub mod regression_probe;\n')
    manifest = source / 'Cargo.toml'
    manifest.write_text(replace_once(manifest.read_text(), '[features]\n', '[features]\nregression-probe = []\n'))
    main = source / 'src/main.rs'
    main.write_text(replace_once(main.read_text(), '    export_file.check_all_declars();\n',
        '    export_file.check_all_declars();\n    #[cfg(feature = "regression-probe")]\n    sokonanoda::regression_probe::dump();\n'))


def validate_probe(d):
    names = ('cold', 'framed', 'one_cons', 'other_cons', 'nil', 'empty', 'empty_framed', 'empty_cons')
    assert set(d) == set(names)
    assert all(type(d[k]) is int and d[k] >= 0 for k in names)
    assert d['cold'] > 0
    assert d['cold'] == sum(d[k] for k in ('framed', 'one_cons', 'other_cons', 'nil'))
    assert d['empty'] == d['empty_framed'] + d['empty_cons']
    assert d['empty'] <= d['cold']
    assert d['empty_framed'] <= d['framed']
    assert d['empty_cons'] <= d['one_cons'] + d['other_cons']
    return d


def run_binary(binary, config, input_path, stdout=None, stderr=None):
    with input_path.open('rb') as inp:
        return run(str(binary), str(config), stdin=inp, stdout=stdout, stderr=stderr)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    source, arena = ROOT / 'control', ROOT / 'arena'
    checkout(REPO, source, BASE)
    checkout('https://github.com/leanprover/lean-kernel-arena', arena, ARENA)
    guarded_source(source / 'src/eval.rs')
    print('V96_SOURCE_GUARD=PASS', flush=True)
    candidate, probe = ROOT / 'candidate', ROOT / 'probe'
    for dst in (candidate, probe):
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(source, dst, ignore=shutil.ignore_patterns('.git', 'target'))
    candidate_hash = apply_candidate(candidate / 'src/eval.rs')
    apply_probe(probe)
    (ROOT / 'candidate-eval.rs').write_bytes((candidate / 'src/eval.rs').read_bytes())
    (ROOT / 'candidate-diff.txt').write_text(''.join(difflib.unified_diff(
        (source / 'src/eval.rs').read_text().splitlines(keepends=True),
        (candidate / 'src/eval.rs').read_text().splitlines(keepends=True),
        fromfile='control/src/eval.rs', tofile='candidate/src/eval.rs')))
    config = ROOT / 'config.json'
    config.write_text(json.dumps(dict(use_stdin=True, nat_extension=True, string_extension=True,
        unpermitted_axiom_hard_error=False, unsafe_permit_all_axioms=True,
        num_threads=4, print_success_message=False)))
    for corpus in CORPORA:
        shell('./lka.py build-test ' + corpus + ' >/dev/null', arena)
    # First repair the observation: independent counters, not LLVM estimates.
    shell('cd ' + str(probe) + " && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked --features regression-probe -q", arena)
    result = {'base': BASE, 'arena': ARENA, 'candidate_sha256': candidate_hash,
              'candidate': 'empty-result-canonicalization', 'corpora': {}, 'profile': {}}
    for corpus in CORPORA:
        inp = arena / '_build/tests' / (corpus + '.ndjson')
        with (ROOT / ('probe-' + corpus + '.out')).open('wb') as out, (ROOT / ('probe-' + corpus + '.err')).open('wb') as err:
            run_binary(probe / 'target/release/sokonanoda', config, inp, out, err)
        assert (ROOT / ('probe-' + corpus + '.out')).read_bytes() == b''
        lines = (ROOT / ('probe-' + corpus + '.err')).read_text().splitlines()
        payloads = [json.loads(s[len('V96_PROBE='):]) for s in lines if s.startswith('V96_PROBE=')]
        assert len(payloads) == 1, (corpus, payloads)
        assert all(s.startswith('V96_PROBE=') for s in lines), (corpus, lines)
        result['profile'][corpus] = validate_probe(payloads[0])
        print('V96_' + corpus.upper() + '_COLD=' + str(payloads[0]['cold']), flush=True)
        print('V96_' + corpus.upper() + '_EMPTY=' + str(payloads[0]['empty']), flush=True)
    print('V96_CONSERVATION=PASS', flush=True)
    (ROOT / 'profile.json').write_text(json.dumps(result['profile'], indent=2))
    # Timed binaries are uninstrumented, identical-build-flags siblings.
    flags = "RUSTFLAGS='-C target-cpu=native'"
    for arm in (source, candidate):
        shell('cd ' + str(arm) + ' && ' + flags + ' cargo test --release --locked -q', arena)
        shell('cd ' + str(arm) + ' && ' + flags + ' cargo build --release --locked -q', arena)
    print('V96_RUST_TESTS=PASS', flush=True)
    for corpus in CORPORA:
        inp = arena / '_build/tests' / (corpus + '.ndjson')
        outputs = {}
        for arm in (source, candidate):
            name = 'control' if arm == source else 'candidate'
            with (ROOT / (name + '-' + corpus + '.out')).open('wb') as out, (ROOT / (name + '-' + corpus + '.err')).open('wb') as err:
                run_binary(arm / 'target/release/sokonanoda', config, inp, out, err)
            outputs[name] = [(ROOT / (name + '-' + corpus + '.' + ext)).read_bytes() for ext in ('out', 'err')]
        assert outputs['control'] == outputs['candidate']
        assert outputs['control'] == [b'', b'']
        print('V96_' + corpus.upper() + '_EXACT_REPLAY=PASS', flush=True)
        measurements = {'control': [], 'candidate': []}
        for i in range(7):
            order = (source, candidate) if i % 2 == 0 else (candidate, source)
            for arm in order:
                name = 'control' if arm == source else 'candidate'
                t = time.perf_counter()
                run_binary(arm / 'target/release/sokonanoda', config, inp, subprocess.DEVNULL, subprocess.DEVNULL)
                measurements[name].append(time.perf_counter() - t)
        cm, xm = (statistics.median(measurements[k]) for k in ('control', 'candidate'))
        delta = (xm / cm - 1) * 100
        result['corpora'][corpus] = dict(measurements, control_median=cm, candidate_median=xm, delta_percent=delta)
        print('V96_' + corpus.upper() + '_DELTA_PERCENT=' + f'{delta:.6f}', flush=True)
    gm = (math.prod(result['corpora'][c]['candidate_median'] / result['corpora'][c]['control_median'] for c in CORPORA) ** (1/3) - 1) * 100
    worst = max(result['corpora'][c]['delta_percent'] for c in CORPORA)
    retain = gm <= -0.50 and worst <= 0.50
    result.update(geomean_delta_percent=gm, worst_delta_percent=worst, retain_candidate=retain,
                  decision='RETAIN_FOR_REVIEW' if retain else 'REJECT_OR_MORE_EVIDENCE')
    (ROOT / 'results.json').write_text(json.dumps(result, indent=2))
    print('V96_GEOMEAN_DELTA_PERCENT=' + f'{gm:.6f}', flush=True)
    print('V96_WORST_DELTA_PERCENT=' + f'{worst:.6f}', flush=True)
    print('V96_RETAIN_CANDIDATE=' + ('YES' if retain else 'NO'), flush=True)
    print('V96_COMPLETE=PASS', flush=True)


if __name__ == '__main__':
    main()
