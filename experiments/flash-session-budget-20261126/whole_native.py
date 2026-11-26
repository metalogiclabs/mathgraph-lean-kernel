"""Matched exact whole-Mathlib verdict and native resource comparison.

CPU seconds are diagnostics, never Arena instruction scores.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--binaries', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
a.out = a.out.resolve()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def save(name, value):
    (a.out / name).write_text(json.dumps(value, indent=2) + '\n')


identity = {'size': a.fixture.stat().st_size, 'sha256': digest(a.fixture)}
assert identity == {'size': 6326141213, 'sha256': 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'}
bins = {n: (a.binaries / (n + '.bin')).resolve() for n in ['baseline', 'strict']}
hashes = {n: digest(b) for n,b in bins.items()}
assert len(set(hashes.values())) == 2, 'Duplicate executables invalidate comparison'
save('identity.json', {'input': identity, 'binary_sha256': hashes, 'threads': 2,
    'boundary': 'Complete exact Mathlib and matched native CPU; no Arena ranking or hardware instruction claim.'})
cfg = a.out / 'baseline-config.json'
cfg.write_text(json.dumps({'use_stdin': True, 'num_threads': 2, 'nat_extension': True,
    'string_extension': True, 'unsafe_permit_all_axioms': True, 'unpermitted_axiom_hard_error': False,
    'print_success_message': True, 'print_axioms': False}))
rows = []
for round_no in range(2):
    for name in ['baseline', 'strict'] if round_no == 0 else ['strict', 'baseline']:
        tag = f'{name}-{round_no}'
        timing = a.out / (tag + '.time')
        cmd = ['/usr/bin/time', '-f', '%e\t%U\t%S\t%M', '-o', str(timing), str(bins[name])]
        cmd += ['--stdin', '--threads', '2', '--nat-extension', '--string-extension', '--axiom-allow-all']
        start = time.monotonic()
        with a.fixture.open('rb') as inp, (a.out / (tag + '.stdout')).open('wb') as out, (a.out / (tag + '.stderr')).open('wb') as err:
            try:
                r = subprocess.run(cmd, stdin=inp, stdout=out, stderr=err, timeout=600)
                code = r.returncode
            except subprocess.TimeoutExpired:
                code = 'TIMEOUT'
        output = (a.out / (tag + '.stdout')).read_bytes()
        count = re.search(rb'[Cc]hecked (\d+) declarations', output)
        row = {'arm': name, 'round': round_no, 'observed': code,
            'declarations': int(count.group(1)) if count else None, 'elapsed_s': time.monotonic() - start}
        if timing.exists():
            fields = timing.read_text().splitlines()[-1].split('\t')
            if len(fields) == 4:
                row.update(wall_s=float(fields[0]), cpu_s=float(fields[1])+float(fields[2]), max_rss_kb=int(fields[3]))
        rows.append(row)
        save('rows.json', rows)
        print(json.dumps(row), flush=True)
        assert {n: digest(b) for n,b in bins.items()} == hashes, 'Executable changed during measurement'
        if code != 0 or row['declarations'] != 739167:
            save('summary.json', {'state': 'UNRESOLVED_FULL_INPUT', 'rows': rows,
                'stderr_tail': (a.out / (tag + '.stderr')).read_text(errors='replace')[-2500:]})
            raise SystemExit(1)
medians = {n: statistics.median(r['cpu_s'] for r in rows if r['arm'] == n) for n in bins}
summary = {'state': 'WARRANTED_BOUNDED_FULL_MATHLIB_ACCEPT', 'observations': 4,
    'cpu_medians': medians, 'candidate_over_baseline_cpu': medians['strict']/medians['baseline'],
    'boundary': 'Exact complete Mathlib, two alternating native rounds; CPU time is not an Arena score.'}
save('summary.json', summary)
print('SUMMARY', json.dumps(summary), flush=True)
