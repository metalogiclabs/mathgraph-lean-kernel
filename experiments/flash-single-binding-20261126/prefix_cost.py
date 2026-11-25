"""Compare named executables on the fixed source-derived Mathlib prefix.

This input is not an Arena test. Names are harness metadata only and never reach
the checker. Every process status and software counter is retained unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--arm', action='append', required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--threads', type=int, default=1)
p.add_argument('--rounds', type=int, default=1)
p.add_argument('--seconds', type=int, default=120)
p.add_argument('--valgrind', default='valgrind')
a = p.parse_args()
assert a.threads > 0 and a.rounds > 0 and a.seconds > 0
assert a.fixture.stat().st_size == 134232002
assert digest(a.fixture) == 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a'
bins = dict((name, Path(path).resolve()) for name, path in (arg.split('=', 1) for arg in a.arm))
assert len(bins) == len(a.arm)
hashes = {name: digest(path) for name, path in bins.items()}
assert len(set(hashes.values())) == len(hashes), 'Shared executable invalidates comparison'
a.out.mkdir(parents=True, exist_ok=True)
cfg = (a.out / 'config.json').resolve()
cfg.write_text(json.dumps({'use_stdin': True, 'num_threads': a.threads, 'parse_only': False,
    'nat_extension': True, 'string_extension': True, 'unsafe_permit_all_axioms': True,
    'unpermitted_axiom_hard_error': False, 'print_success_message': True, 'print_axioms': False}))
(a.out / 'identity.json').write_text(json.dumps({'binary_sha256': hashes, 'threads': a.threads,
    'input_sha256': digest(a.fixture), 'fixture_archive': 15063957079,
    'fixture_archive_sha256': '4bb8bbb581665e2918b40eca3bd5108080b5ea69f72e7ad9c28e84d110ee3788',
    'method': 'Valgrind Cachegrind, cache-sim=no, branch-sim=no',
    'boundary': 'Source-derived Mathlib prefix, not full Mathlib or an official rank.'}, indent=2) + '\n')
rows = []
names = list(bins)
for round_no in range(a.rounds):
    for name in names if round_no % 2 == 0 else reversed(names):
        tag = f'{name}-{round_no}'
        profile = a.out / (tag + '.cachegrind')
        start = time.monotonic()
        cmd = [a.valgrind, '--tool=cachegrind', '--cache-sim=no', '--branch-sim=no',
               '--cachegrind-out-file=' + str(profile.resolve()), str(bins[name]), str(cfg)]
        with a.fixture.open('rb') as inp:
            try:
                r = subprocess.run(cmd, stdin=inp, capture_output=True, timeout=a.seconds)
                raw, stdout, stderr = r.returncode, r.stdout, r.stderr
            except subprocess.TimeoutExpired as e:
                raw, stdout, stderr = 'TIMEOUT', e.stdout or b'', e.stderr or b''
        (a.out / (tag + '.stdout')).write_bytes(stdout)
        (a.out / (tag + '.stderr')).write_bytes(stderr)
        counts = re.findall(r'^summary:\s*(\d+)', profile.read_text(), re.M) if profile.exists() else []
        row = {'arm': name, 'round': round_no, 'raw_exit': raw,
               'success': stdout.strip() == b'Checked 25131 declarations with no errors',
               'elapsed_s': time.monotonic() - start, 'guest_Ir': int(counts[-1]) if counts else None,
               'binary_sha256': hashes[name]}
        rows.append(row)
        (a.out / 'rows.json').write_text(json.dumps(rows, indent=2) + '\n')
        print(json.dumps(row), flush=True)
wrong = [r for r in rows if r['raw_exit'] != 0 or not r['success'] or r['guest_Ir'] is None]
summary = {'observations': len(rows), 'wrong_or_unknown': wrong, 'threads': a.threads,
           'boundary': 'Fixed source-derived 25,131-declaration prefix. Not official Arena scoring.'}
if not wrong and 'baseline' in bins:
    totals = {n: sum(r['guest_Ir'] for r in rows if r['arm'] == n) for n in bins}
    summary['ratios'] = {n: v / totals['baseline'] for n, v in totals.items() if n != 'baseline'}
(a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print('SUMMARY', json.dumps(summary), flush=True)
if wrong:
    raise SystemExit(1)
