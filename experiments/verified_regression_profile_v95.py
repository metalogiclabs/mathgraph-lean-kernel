#!/usr/bin/env python3
"""Recover the missing v94 residual using source coverage, not perf privileges.

This is a diagnostic experiment. It never promotes a kernel implementation.
All checkouts, inputs and expected outcomes are pinned. A missing profile is a
failure, not an empty successful result. Coverage counts are not timings.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = '08ddb26718c86213262943ca19ae8cf1b03fa922'
ARENA = '91f376e4baacf2df0c478e7173bccb2a6adac5c5'
REPO = 'https://github.com/metalogiclabs/mathgraph-lean-kernel'
SOURCE_BLOB = 'c1c49a644c1475d6f433d32f553a70a1d5fb8f99'
CORPORA = ('std', 'cedar', 'mathlib')
ROOT = Path(os.environ.get('V95_ROOT', '/tmp/v95')).resolve()


def run(*args, cwd=None, env=None, output=None):
    with open(output, 'w') if output else open(os.devnull, 'w') as out:
        subprocess.run(args, cwd=cwd, env=env, stdout=out if output else None, check=True)


def shell(script, cwd):
    run('nix', 'develop', '-c', 'bash', '-euo', 'pipefail', '-c', script, cwd=cwd)


def checkout(url, path, sha):
    if not path.exists():
        run('git', 'clone', '-q', url, str(path))
    run('git', '-C', str(path), 'checkout', '-q', sha)
    actual = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    assert actual == sha, (actual, sha)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'source'
    arena = ROOT / 'arena'
    checkout(REPO, source, BASE)
    checkout('https://github.com/leanprover/lean-kernel-arena', arena, ARENA)
    raw = (source / 'src/eval.rs').read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    assert blob == SOURCE_BLOB
    print('V95_SOURCE_GUARD=PASS', flush=True)
    for corpus in CORPORA:
        shell('./lka.py build-test ' + corpus + ' >/dev/null', arena)
    # Instrumented release build retains the exact source; it is not used for
    # performance comparisons. LLVM coverage supplies counts without perf_event.
    shell('cd ' + str(source) + " && RUSTFLAGS='-C instrument-coverage -C target-cpu=native' cargo build --release --locked -q", arena)
    binary = source / 'target/release/sokonanoda'
    config = ROOT / 'config.json'
    config.write_text(json.dumps(dict(use_stdin=True, nat_extension=True,
        string_extension=True, unpermitted_axiom_hard_error=False,
        unsafe_permit_all_axioms=True, num_threads=4, print_success_message=False)))
    profile_dir = ROOT / 'profile'
    profile_dir.mkdir(exist_ok=True)
    result = {'source': BASE, 'arena': ARENA, 'corpora': {}}
    for corpus in CORPORA:
        input_path = arena / '_build/tests' / (corpus + '.ndjson')
        env = os.environ.copy()
        env['LLVM_PROFILE_FILE'] = str(profile_dir / (corpus + '-%p-%m.profraw'))
        with input_path.open('rb') as inp, (ROOT / (corpus + '.out')).open('wb') as out, (ROOT / (corpus + '.err')).open('wb') as err:
            p = subprocess.run([str(binary), str(config)], stdin=inp, stdout=out, stderr=err, env=env)
        assert p.returncode == 0, (corpus, p.returncode)
        # The v94 control produced no output; preserve this exact replay check,
        # but do not confuse it with an independently established soundness test.
        for ext in ('out', 'err'):
            assert (ROOT / (corpus + '.' + ext)).read_bytes() == b''
        raw_files = sorted(profile_dir.glob(corpus + '-*.profraw'))
        assert raw_files, 'No LLVM coverage file for ' + corpus
        profdata = profile_dir / (corpus + '.profdata')
        shell('llvm-profdata merge -sparse ' + ' '.join(map(str, raw_files)) + ' -o ' + str(profdata), arena)
        exported = profile_dir / (corpus + '.json')
        shell('llvm-cov export -format=text -instr-profile=' + str(profdata) + ' ' + str(binary) + ' > ' + str(exported), arena)
        data = json.loads(exported.read_text())
        functions = []
        for unit in data['data']:
            filenames = unit['files']
            for fn in unit['functions']:
                if 'prune_env_cold' not in fn['name']:
                    continue
                regions = [r for r in fn['regions'] if r[4] > 0]
                functions.append({'name': fn['name'], 'count': fn['count'],
                    'regions': regions, 'filenames': [f['filename'] for f in filenames]})
        assert functions and sum(f['count'] for f in functions) > 0, 'No usable cold-prune coverage: ' + corpus
        result['corpora'][corpus] = {'functions': functions, 'raw_profiles': len(raw_files)}
        print('V95_' + corpus.upper() + '_COVERAGE_CALLS=' + str(sum(f['count'] for f in functions)), flush=True)
    (ROOT / 'residual-profile.json').write_text(json.dumps(result, indent=2))
    print('V95_PROFILE_COMPLETE=PASS', flush=True)
    print('V95_SOURCE_COVERAGE_NOT_TIMING=PASS', flush=True)


if __name__ == '__main__':
    main()
