#!/usr/bin/env python3
"""Qualify the frozen v93 direct-Framed candidate on independent held-out cases.

This is a diagnostic gate, not a kernel promotion. Reuse the exact v98 source
patch, the v97 repaired rejection tests, and the pinned Arena. A binary-identical
control estimates timing noise. Missing evidence is a failure, never a pass.
"""
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import time

ROOT = Path('/tmp/v98-holdout')
REPO = 'metalogiclabs/mathgraph-lean-kernel'
BASE = '08ddb26718c86213262943ca19ae8cf1b03fa922'
ARENA = '91f376e4baacf2df0c478e7173bccb2a6adac5c5'
SCRIPT_BLOB = '0aecf32847525751b7a6551acf82e34dc3ac9f55'
SOURCE_BLOB = 'c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
HELPER_BLOB = 'eebb80944e94dc8dc80173b9cf47204a010a7648'
FIXTURE_HASHES = {
    'RuleDomainMismatch': 'fbf6bb379da79d0df0d31daaa7f8ed5fcab038b729917935f9d7fbc292208565',
    'UnlistedRecursor': '36e799154fbd29dd09f9060da5b70ec0b387f28a401ba58384243d4d6570f17b',
}
RESULT = {'base': BASE, 'arena': ARENA, 'candidate': 'v93-direct-framed-only',
          'source_script_blob': SCRIPT_BLOB, 'decision': 'INCOMPLETE', 'heldout': {}}


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save():
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'results.json').write_text(json.dumps(RESULT, indent=2) + '\n')


def run(args, cwd=None, **kwargs):
    p = subprocess.run(args, cwd=cwd, **kwargs)
    if p.returncode:
        raise RuntimeError(f'Command failed ({p.returncode}): {args}\n{p.stderr if isinstance(p.stderr, str) else ""}')
    return p


def nix(command):
    return run(['nix', 'develop', str(ROOT / 'arena'), '-c', 'bash', '-euo', 'pipefail', '-c', command],
               capture_output=True, text=True)


def input_info(path):
    data = path.read_bytes()
    records = [json.loads(line) for line in data.splitlines() if line.strip()]
    assert records and 'meta' in records[0]
    return {'sha256': sha(data), 'bytes': len(data), 'records': len(records)}


def check_binary(binary, config, inp):
    with inp.open('rb') as f:
        return subprocess.run([str(binary), str(config)], stdin=f, capture_output=True)


def timed(binary, config, inp):
    start = time.perf_counter()
    with inp.open('rb') as f:
        p = subprocess.run([str(binary), str(config)], stdin=f,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert p.returncode == 0, (binary, p.returncode)
    return time.perf_counter() - start


def main():
    here = Path.cwd()
    source = (here / 'experiments/run_direct_framed_qualification_v98.sh').read_bytes()
    assert blob(source) == SCRIPT_BLOB, 'Frozen v98 driver changed'
    for name, expected in FIXTURE_HASHES.items():
        assert sha((here / 'test_resources' / name / 'export').read_bytes()) == expected
    helper = (here / 'src/tests/util.rs').read_bytes()
    assert blob(helper) == HELPER_BLOB
    text = source.decode()
    parts = text.split('\nfor t in std cedar mathlib; do ', 1)
    assert len(parts) == 2, 'Cannot isolate the frozen setup'
    setup = parts[0].replace('ROOT=/tmp/v98\n', 'ROOT=/tmp/v98-holdout\n')
    assert setup != parts[0]
    run(['bash', '-euo', 'pipefail', '-c', setup], cwd=here)
    assert (ROOT / 'control/src/eval.rs').exists()
    control = ROOT / 'control'
    candidate = ROOT / 'candidate'
    assert blob((control / 'src/eval.rs').read_bytes()) == SOURCE_BLOB
    for arm in (control, candidate):
        (arm / 'src/tests/util.rs').write_bytes(helper)
    original = (control / 'src/eval.rs').read_text()
    changed = (candidate / 'src/eval.rs').read_text()
    assert original != changed and 'if let value::Env::Framed' in changed
    (ROOT / 'candidate-diff.txt').write_text(''.join(difflib.unified_diff(
        original.splitlines(keepends=True), changed.splitlines(keepends=True),
        fromfile='control/src/eval.rs', tofile='candidate/src/eval.rs')))
    RESULT['candidate_sha256'] = sha(changed.encode())
    RESULT['test_helper_blob'] = HELPER_BLOB
    save()
    print('V98_HOLDOUT_SOURCE_GUARD=PASS', flush=True)

    # CSLib was not one of the three corpora used to choose the v93 candidate.
    # The constant-level fixture is a separate, expected-reject correctness case.
    nix('cd ' + str(ROOT / 'arena') + ' && ./lka.py build-test cslib >/dev/null')
    positive = ROOT / 'arena/_build/tests/cslib.ndjson'
    negative = ROOT / 'arena/tests/constlevels.ndjson'
    assert positive.is_file() and negative.is_file()
    assert blob(negative.read_bytes()) == 'ca7ceaa9eced2598958975138e5bf4fc86e207cd'
    RESULT['heldout']['cslib'] = input_info(positive)
    RESULT['heldout']['constlevels'] = input_info(negative)
    save()

    flags = "RUSTFLAGS='-C target-cpu=native'"
    binaries = {}
    for name, arm in (('control', control), ('candidate', candidate)):
        tests = nix('cd ' + str(arm) + ' && ' + flags + ' cargo test --release --locked --lib -q')
        assert re.search(r'test result: ok\. 43 passed; 0 failed;', tests.stdout), tests.stdout
        (ROOT / (name + '-tests.log')).write_text(tests.stdout + tests.stderr)
        nix('cd ' + str(arm) + ' && ' + flags + ' cargo build --release --locked -q')
        binaries[name] = arm / 'target/release/sokonanoda'
    null = ROOT / 'control-identical.bin'
    shutil.copy2(binaries['control'], null)
    binaries['null'] = null
    hashes = {name: sha(path.read_bytes()) for name, path in binaries.items()}
    assert hashes['control'] == hashes['null']
    assert hashes['control'] != hashes['candidate']
    RESULT['binary_sha256'] = hashes
    RESULT['release_tests'] = '43/43 per arm'
    print('V98_HOLDOUT_RELEASE_TESTS=PASS', flush=True)

    config = ROOT / 'config.json'
    for label, inp, expected in (('cslib', positive, 0), ('constlevels', negative, 1)):
        outputs = {}
        for name, binary in binaries.items():
            p = check_binary(binary, config, inp)
            outputs[name] = (p.returncode, p.stdout, p.stderr)
            (ROOT / f'{name}-{label}.out').write_bytes(p.stdout)
            (ROOT / f'{name}-{label}.err').write_bytes(p.stderr)
        assert outputs['control'] == outputs['candidate'] == outputs['null']
        code, out, err = outputs['control']
        assert code == expected and out == b''
        assert err == (b'' if expected == 0 else err)
        if expected == 1:
            assert err, 'Rejection must have a diagnostic'
        RESULT['heldout'][label]['exact_replay'] = 'PASS'
        RESULT['heldout'][label]['exit_code'] = code
        print('V98_HOLDOUT_' + label.upper() + '_EXACT_REPLAY=PASS', flush=True)
    save()

    # Seven alternating, paired rounds; the null arm is a byte-identical
    # copy of control. No instrumentation, source mutation, or perf privileges.
    samples = {'control': [], 'candidate': [], 'null': []}
    for i in range(7):
        order = ('control', 'candidate', 'null') if i % 2 == 0 else ('null', 'candidate', 'control')
        for name in order:
            samples[name].append(timed(binaries[name], config, positive))
    ratios = {name: [(x / c - 1) * 100 for x, c in zip(samples[name], samples['control'])]
              for name in ('candidate', 'null')}
    median = {name: statistics.median(values) for name, values in ratios.items()}
    RESULT['timings'] = {'seconds': samples, 'paired_delta_percent': ratios,
                         'paired_median_delta_percent': median, 'rounds': 7}
    null_ok = abs(median['null']) <= 0.50
    holdout_ok = median['candidate'] <= 0.50
    RESULT['decision'] = 'PASS_FOR_REVIEW' if null_ok and holdout_ok else 'REJECT_OR_INCONCLUSIVE'
    RESULT['retain_candidate'] = False  # The separate core gate must also pass.
    RESULT['complete'] = True
    save()
    print('V98_HOLDOUT_CSLIB_DELTA_PERCENT=' + f"{median['candidate']:.6f}", flush=True)
    print('V98_HOLDOUT_NULL_DELTA_PERCENT=' + f"{median['null']:.6f}", flush=True)
    print('V98_HOLDOUT_DECISION=' + RESULT['decision'], flush=True)
    print('V98_HOLDOUT_COMPLETE=PASS', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        RESULT['error'] = repr(exc)
        save()
        raise
