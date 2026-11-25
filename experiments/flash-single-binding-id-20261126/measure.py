"""Predeclared bounded gate; source-derived prefix only, never an Arena score."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
for n in ('baseline', 'candidate', 'fixture', 'drrun', 'client', 'out'):
    p.add_argument('--' + n, type=Path, required=True)
a = p.parse_args()
for n in vars(a):
    setattr(a, n, getattr(a, n).resolve())
a.out.mkdir(parents=True, exist_ok=True)
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert a.fixture.stat().st_size == 134232002 and digest(a.fixture) == 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a'
hashes = {n: digest(getattr(a, n)) for n in ('baseline', 'candidate')}
assert len(set(hashes.values())) == 2
(a.out / 'identity.json').write_text(json.dumps({'binary_sha256': hashes, 'client_sha256': digest(a.client), 'input_sha256': digest(a.fixture), 'threads': 1}, indent=2) + '\n')
rows = []
for round_no, order in enumerate([('baseline', 'candidate'), ('candidate', 'baseline')]):
    for arm in order:
        tag = f'{arm}-{round_no}'
        command = [str(a.drrun), '-c', str(a.client), '--', str(getattr(a, arm)), '--stdin', '--threads', '1', '--nat-extension', '--string-extension', '--axiom-allow-all']
        start = time.monotonic()
        with a.fixture.open('rb') as f:
            r = subprocess.run(command, stdin=f, capture_output=True, timeout=180)
        (a.out / (tag + '.stdout')).write_bytes(r.stdout)
        (a.out / (tag + '.stderr')).write_bytes(r.stderr)
        hits = re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)', r.stderr)
        row = {'arm': arm, 'round': round_no, 'raw_exit': r.returncode,
            'complete_count': b'25131 declarations' in r.stdout,
            'instructions': int(hits[0]) if len(hits) == 1 else None,
            'elapsed_s': time.monotonic() - start}
        rows.append(row)
        (a.out / 'rows.json').write_text(json.dumps(rows, indent=2) + '\n')
        print(json.dumps(row), flush=True)
        assert row['raw_exit'] == 0 and row['complete_count'] and row['instructions'] is not None, row
cost = {(r['arm'], r['round']): r['instructions'] for r in rows}
ratios = [cost['candidate', n] / cost['baseline', n] for n in (0, 1)]
ratio = math.sqrt(math.prod(ratios))
passed = all(r <= 0.99 for r in ratios)
summary = {'state': 'CANDIDATE_PREFIX_GATE_PASSED' if passed else 'REJECTED_FOR_PERFORMANCE_PROMOTION',
    'candidate_over_baseline': ratio, 'paired_ratios': ratios, 'passed': passed,
    'gate': 'Both alternating pairs <=0.99 before broad qualification',
    'boundary': 'Exact 25131-declaration prefix, matched generic local builds, software basic-block instructions with documented limitations. Not complete Mathlib, native wall time, an Arena score or a release.'}
(a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2), flush=True)
