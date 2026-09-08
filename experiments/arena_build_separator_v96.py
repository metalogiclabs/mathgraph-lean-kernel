#!/usr/bin/env python3
"""v96: isolate the v93/v94 build residual under the Arena's real score.

No production source is changed. No candidate is promoted by this experiment.
A missing hardware counter is UNKNOWN, never an instruction-count gain.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import statistics
import subprocess
import sys
import time
import traceback

REPO = 'https://github.com/metalogiclabs/mathgraph-lean-kernel'
BASE = '08ddb26718c86213262943ca19ae8cf1b03fa922'
SOURCE_BLOB = 'c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
ARENA = '4803515a59ecb1931814a16d3e8acabd1d9c8256'
CORPORA = ('std', 'cedar', 'mathlib')
ROOT = Path(os.environ.get('V96_ROOT', '/tmp/v96')).resolve()
STATE = {'base': BASE, 'arena': ARENA, 'status': 'incomplete', 'builds': {}, 'measurements': {}}
CONFIG = dict(use_stdin=True, nat_extension=True, string_extension=True,
              unpermitted_axiom_hard_error=False, unsafe_permit_all_axioms=True,
              num_threads=4)
NEEDLE = """    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
"""
FAST = """    #[inline(never)]
    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {
        if let value::Env::Framed { mask: fmask, slots, .. } = e {
            let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
            let mut slots_hash = e.lsub().map_or(0, |l| l as *const value::LevelSub<'t> as usize as u64);
            let m2 = mask & *fmask;
            let out_mask = m2;
            let mut n = 0usize;
            let mut sel = select_ranks(m2, *fmask);
            while sel != 0 {
                let i = sel.trailing_zeros() as usize;
                sel &= sel - 1;
                let sv = slots[i];
                buf[n].write(sv);
                slots_hash = slots_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(sv as *const Value<'t> as usize as u64);
                n += 1;
            }
            let picked: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };
            let lsub = e.lsub();
            let hash = out_mask.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(slots_hash);
            let r = self.intern_frame(hash, out_mask, picked, lsub);
            self.tc_cache.prune_dm[slot] = (e as *const value::Env<'t> as usize, mask, Some(r));
            if let value::Env::Framed { prune, .. } = e { prune.set((mask, Some(r))); }
            return r;
        }
        let mut buf: [std::mem::MaybeUninit<V<'t>>; 64] = [const { std::mem::MaybeUninit::uninit() }; 64];
"""


def run(args, cwd=None, env=None, stdout=None):
    return subprocess.run(args, cwd=cwd, env=env, stdout=stdout, check=True)


def shell(script, cwd):
    run(['nix', 'develop', '-c', 'bash', '-euo', 'pipefail', '-c', script], cwd=cwd)


def checkout(url, path, sha):
    run(['git', 'clone', '-q', url, str(path)])
    run(['git', '-C', str(path), 'checkout', '-q', sha])
    assert subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip() == sha


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def save():
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'results.json').write_text(json.dumps(STATE, indent=2, sort_keys=True))


def build(root, arm, mode, arena):
    src = root / arm
    q = shlex.quote
    if mode == 'native':
        flags = '-C target-cpu=native'
        shell('cd ' + q(str(src)) + ' && RUSTFLAGS=' + q(flags) + ' cargo build --release --locked -q', arena)
    else:
        # These are the exact two PGO build commands and training input from
        # the Arena's mathgraph.yaml, with --locked added for dependency safety.
        pgo = src / 'pgo'
        pgo.mkdir(exist_ok=True)
        shell('cd ' + q(str(src)) + ' && RUSTFLAGS="-C target-cpu=native -Cprofile-generate=$PWD/pgo" cargo build --release --locked -q', arena)
        with (arena / '_build/tests/init-prelude.ndjson').open('rb') as inp, open(os.devnull, 'wb') as out:
            run([str(src / 'target/release/sokonanoda'), str(ROOT / 'config.json')], cwd=src, stdout=out, env=None)
        # Re-run training with the actual stdin: the first invocation above is
        # not used as evidence and is intentionally omitted from the profile.
        with (arena / '_build/tests/init-prelude.ndjson').open('rb') as inp, open(os.devnull, 'wb') as out:
            subprocess.run([str(src / 'target/release/sokonanoda'), str(ROOT / 'config.json')], stdin=inp, stdout=out, check=True)
        shell('cd ' + q(str(src)) + ' && llvm-profdata merge -o pgo/merged.profdata pgo', arena)
        shell('cd ' + q(str(src)) + ' && RUSTFLAGS="-C target-cpu=native -Cprofile-use=$PWD/pgo/merged.profdata" cargo build --release --locked -q', arena)
    binary = ROOT / (mode + '-' + arm + '.bin')
    shutil.copy2(src / 'target/release/sokonanoda', binary)
    STATE['builds'][mode + '-' + arm] = {'sha256': digest(binary), 'mode': mode, 'source': arm}
    save()
    print('V96_BUILD=' + mode + '-' + arm + ' PASS', flush=True)
    return binary


def execute(binary, corpus, output=False):
    inp = ROOT / 'arena/_build/tests' / (corpus + '.ndjson')
    start = time.perf_counter_ns()
    with inp.open('rb') as f:
        p = subprocess.run([str(binary), str(ROOT / 'config.json')], stdin=f,
                           stdout=subprocess.PIPE if output else subprocess.DEVNULL,
                           stderr=subprocess.PIPE if output else subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError(str(binary) + ' ' + corpus + ' exited ' + str(p.returncode))
    return (time.perf_counter_ns() - start) / 1e9, p


def measure(mode, binaries):
    results = {}
    n = 3 if mode == 'native' else 5
    for corpus in CORPORA:
        # Check actual bytes and exit codes before any timing comparison.
        _, control = execute(binaries['control'], corpus, True)
        _, candidate = execute(binaries['candidate'], corpus, True)
        assert (control.stdout, control.stderr) == (candidate.stdout, candidate.stderr), 'REPLAY_MISMATCH ' + corpus
        print('V96_' + mode.upper() + '_' + corpus.upper() + '_EXACT_REPLAY=PASS', flush=True)
        samples = {'control': [], 'candidate': []}
        for i in range(n):
            for arm in (('control', 'candidate') if i % 2 == 0 else ('candidate', 'control')):
                elapsed, _ = execute(binaries[arm], corpus)
                samples[arm].append(elapsed)
        cm = statistics.median(samples['control'])
        xm = statistics.median(samples['candidate'])
        delta = (xm / cm - 1) * 100
        results[corpus] = {'samples': samples, 'control_median': cm, 'candidate_median': xm, 'wall_delta_percent': delta}
        print('V96_' + mode.upper() + '_' + corpus.upper() + '_WALL_DELTA_PERCENT=' + f'{delta:.6f}', flush=True)
        save()
    gm = (math.prod(results[c]['candidate_median'] / results[c]['control_median'] for c in CORPORA) ** (1/3) - 1) * 100
    worst = max(results[c]['wall_delta_percent'] for c in CORPORA)
    results['geomean_wall_delta_percent'] = gm
    results['worst_wall_delta_percent'] = worst
    results['wall_retain'] = gm <= -0.5 and worst <= 0.5
    STATE['measurements'][mode] = results
    save()
    return results


def official_metrics(arena, binaries):
    spec = importlib.util.spec_from_file_location('lka_v96', arena / 'lka.py')
    lka = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = lka
    spec.loader.exec_module(lka)
    tests = {t['name']: t for t in lka.load_tests()}
    out = {}
    for corpus in CORPORA:
        if corpus not in tests:
            raise RuntimeError('Missing Arena test metadata: ' + corpus)
        pair = {}
        for arm in ('control', 'candidate'):
            checker = {'name': 'v96-' + arm, 'run': shlex.quote(str(binaries[arm])) + ' ' + shlex.quote(str(ROOT / 'config.json')) + ' < "$IN"'}
            try:
                r = lka.run_checker_on_test(checker, tests[corpus], arena / '_build/checkers', arena / '_build/tests', ROOT / 'arena-results')
                pair[arm] = r
            except Exception as exc:
                pair[arm] = {'error': repr(exc), 'instructions': 0}
        ci = pair['control'].get('instructions', 0)
        xi = pair['candidate'].get('instructions', 0)
        if ci > 0 and xi > 0:
            pair['instruction_delta_percent'] = (xi / ci - 1) * 100
            print('V96_' + corpus.upper() + '_INSTRUCTION_DELTA_PERCENT=' + f"{pair['instruction_delta_percent']:.6f}", flush=True)
        else:
            pair['instruction_delta_percent'] = None
            print('V96_' + corpus.upper() + '_INSTRUCTIONS=UNAVAILABLE', flush=True)
        out[corpus] = pair
        save()
    return out


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    STATE['host'] = {'platform': platform.platform(), 'machine': platform.machine(), 'processor': platform.processor()}
    (ROOT / 'config.json').write_text(json.dumps(CONFIG, sort_keys=True))
    arena = ROOT / 'arena'
    checkout('https://github.com/leanprover/lean-kernel-arena', arena, ARENA)
    for arm in ('control', 'candidate'):
        checkout(REPO, ROOT / arm, BASE)
        source = ROOT / arm / 'src/eval.rs'
        assert git_blob(source.read_bytes()) == SOURCE_BLOB
        if arm == 'candidate':
            text = source.read_text()
            assert text.count(NEEDLE) == 1
            source.write_text(text.replace(NEEDLE, FAST, 1))
            (ROOT / 'direct-framed.patch').write_text(subprocess.check_output(['git', '-C', str(ROOT / arm), 'diff', '--', 'src/eval.rs'], text=True))
    STATE['source_guard'] = True
    print('V96_SOURCE_GUARD=PASS', flush=True)
    shell('./lka.py build-test init-prelude && ./lka.py build-test std && ./lka.py build-test cedar && ./lka.py build-test mathlib', arena)
    STATE['inputs'] = {c: digest(arena / '_build/tests' / (c + '.ndjson')) for c in ('init-prelude',) + CORPORA}
    save()
    native = {arm: build(ROOT, arm, 'native', arena) for arm in ('control', 'candidate')}
    measure('native', native)
    pgo = {arm: build(ROOT, arm, 'arena-pgo', arena) for arm in ('control', 'candidate')}
    measured = measure('arena-pgo', pgo)
    STATE['official_metrics'] = official_metrics(arena, pgo)
    primary = STATE['official_metrics']['mathlib'].get('instruction_delta_percent')
    STATE['decision'] = ('CANDIDATE_FOR_FULL_QUALIFICATION' if measured['wall_retain'] and primary is not None and primary < 0 else 'REJECT_OR_INCONCLUSIVE')
    STATE['status'] = 'complete'
    print('V96_GEOMEAN_WALL_DELTA_PERCENT=' + f"{measured['geomean_wall_delta_percent']:.6f}", flush=True)
    print('V96_WORST_WALL_DELTA_PERCENT=' + f"{measured['worst_wall_delta_percent']:.6f}", flush=True)
    print('V96_DECISION=' + STATE['decision'], flush=True)
    save()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        STATE['status'] = 'failed'
        STATE['error'] = traceback.format_exc()
        save()
        traceback.print_exc()
        sys.exit(1)
