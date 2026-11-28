"""Observe evaluator work; counts and elapsed time are not an Arena score."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary', type=Path, required=True)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--threads', type=int, choices=[1, 2], default=2)
p.add_argument('--whole', action='store_true')
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
expected = (6326141213, 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec', 739167) if a.whole else (
    134232002, 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a', 25131)
assert (a.fixture.stat().st_size, digest(a.fixture)) == expected[:2]
binary_hash = digest(a.binary)
with a.fixture.open('rb') as inp:
    r = subprocess.run([str(a.binary.resolve()), '--stdin', '--threads', str(a.threads),
        '--nat-extension', '--string-extension', '--axiom-allow-all'], stdin=inp,
        capture_output=True, timeout=900 if a.whole else 120)
(a.out / 'stdout').write_bytes(r.stdout)
(a.out / 'stderr').write_bytes(r.stderr)
counts = [0] * 48
records = 0
for line in r.stderr.decode().splitlines():
    if line.startswith('EVAL_COST_CENSUS '):
        row = json.loads(line.split(' ', 1)[1])['counts']
        assert len(row) == len(counts)
        counts = [x+y for x, y in zip(counts, row)]
        records += 1
result = {'state': 'OBSERVED', 'raw_exit': r.returncode, 'threads': a.threads,
    'binary_sha256': binary_hash, 'input_sha256': expected[1], 'input_size': expected[0],
    'expected_declarations': expected[2], 'counter_records': records, 'counts': counts,
    'kind_order': ['Var', 'Sort', 'Const', 'App', 'Lambda', 'Pi', 'Let', 'Proj', 'NatLit', 'StringLit'],
    'counter_ranges': {'eval_entries': [0, 10], 'eval_computations': [10, 20],
        'closed_hit_miss': [20, 22], 'level_substituted_hit_miss': [22, 24],
        'open_hit_miss': [24, 26], 'prune_calls': 26, 'prune_zero_mask': 27,
        'prune_already_projected': 28, 'prune_memo_hit': 29, 'prune_cold': 30,
        'infer_entries': 31, 'infer_cache_hit': 32, 'infer_cache_miss': 33,
        'known_closed_checks': 35, 'fresh_final_frames': 36, 'reused_final_frames': 37},
    'boundary': 'Observation-only native build. Counts may be scheduling dependent. '
        'Instrumented elapsed time is not a performance comparison or an Arena score.'}
(a.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
assert digest(a.binary) == binary_hash
assert r.returncode == 0 and f'checked {expected[2]} declarations'.encode() in r.stdout
assert records > 0
assert sum(counts[1:10]) == sum(counts[20:26]), 'Every nonvariable evaluation takes one cache path'
assert sum(counts[10:20]) == counts[21]+counts[23]+counts[25], 'Every miss computes one root'
assert counts[26] == sum(counts[27:31]), 'Pruning paths partition all pruning calls'
assert counts[30] == counts[36]+counts[37], 'Cold pruning returns a fresh or reused frame'
print(json.dumps(result))
