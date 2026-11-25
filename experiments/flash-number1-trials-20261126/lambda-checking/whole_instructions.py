"""Single-arm, matched-method Cachegrind instruction diagnostic on exact Mathlib.

Compare only results using this same method. Its counts differ slightly from
Callgrind and must not be substituted into the Arena scoreboard.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

spec = importlib.util.spec_from_file_location('bounded', Path(__file__).with_name('native_mathlib.py'))
bounded = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bounded)

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--arm', required=True)
p.add_argument('--build-head', default='ae176b7b486366b204a844d321e2a6d8cd3a9e97')
p.add_argument('--fixture', required=True, type=Path)
p.add_argument('--binaries', required=True, type=Path)
p.add_argument('--out', required=True, type=Path)
a = p.parse_args()
assert re.fullmatch(r'[a-z][a-z0-9_]*', a.arm)
assert re.fullmatch(r'[0-9a-f]{40}', a.build_head)
a.out.mkdir(parents=True, exist_ok=True)
actual = {'size': a.fixture.stat().st_size, 'sha256': bounded.digest(a.fixture)}
assert actual == {'size': 6326141213, 'sha256': 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'}
builds = json.loads((a.binaries / 'validated-builds.json').read_text())
build = next(r for r in builds if r['name'] == a.arm)
binary = (a.binaries / (a.arm + '.bin')).resolve()
assert bounded.digest(binary) == build['binary_sha256']
assert len({r['binary_sha256'] for r in builds}) == len(builds)
assert (a.binaries / 'commit.txt').read_text().strip() == a.build_head
version = subprocess.check_output(['valgrind', '--version'], text=True).strip()
assert version == 'valgrind-3.22.0', version
cfg = (a.out / 'config.json').resolve()
bounded.save(cfg, {'use_stdin': True, 'num_threads': 1, 'parse_only': False,
    'nat_extension': True, 'string_extension': True, 'unsafe_permit_all_axioms': True,
    'unpermitted_axiom_hard_error': False, 'print_success_message': True, 'print_axioms': False})
bounded.save(a.out / 'identity.json', {'input': actual, 'build': build, 'valgrind': version,
    'method': 'Cachegrind, cache-sim=no, branch-sim=no, generic x86-64, one worker',
    'build_evidence_head': a.build_head,
    'boundary': 'Matched-method diagnostic; not Callgrind counts, ten-large-input qualification or official Arena rank.'})
profile = a.out / 'mathlib.cachegrind'
cmd = ['valgrind', '--tool=cachegrind', '--cache-sim=no', '--branch-sim=no',
       '--cachegrind-out-file=' + str(profile.resolve()), str(binary), str(cfg)]
row = bounded.run_bounded(cmd, a.fixture, a.out / 'stdout', a.out / 'stderr', 2700, 13631488)
row.update({'arm': a.arm, 'input_sha256': actual['sha256'], 'binary_sha256': build['binary_sha256'],
    'success_message': re.fullmatch(rb'Checked \d+ declarations with no errors\s*',
                                  (a.out / 'stdout').read_bytes()) is not None})
if row['raw_exit'] == 0 and row['diagnostic_stop'] is None and row['success_message'] and profile.exists():
    counts = re.findall(r'^summary:\s*(\d+)', profile.read_text(), re.M)
    if counts:
        row['guest_Ir'] = int(counts[-1])
row['state'] = 'WARRANTED_BOUNDED_MATCHED_METHOD' if 'guest_Ir' in row else 'UNKNOWN_OR_FAILED'
bounded.save(a.out / 'result.json', row)
print(json.dumps(row), flush=True)
if 'guest_Ir' not in row:
    raise SystemExit(1)
