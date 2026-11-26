"""Qualify one exact complete large export with the frozen batch candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


p = argparse.ArgumentParser(description=__doc__)
for key in ['binary', 'fixture', 'identity', 'out']:
    p.add_argument('--' + key, type=Path, required=True)
p.add_argument('--case', required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
identity = json.loads(a.identity.read_text())
assert identity['candidate_commit'] == '4816054e2331c3cd6b57cbcd51d3e265b48c68e7'
assert identity['candidate_source_tree'] == 'fa9f0de20650f28f63f1d01d7dab50397e167bcf'
binary_hash = digest(a.binary)
assert binary_hash == identity['candidate_binary_sha256']
manifest = json.loads(Path('experiments/flash-upstream-repair-20261126/official-inputs.json').read_text())
meta = next(t for t in manifest['tests'] if t['name'] == a.case)
expected = json.loads(Path(__file__).with_name('expected-large.json').read_text())[a.case]
input_identity = {'name': a.case, 'size': a.fixture.stat().st_size, 'sha256': digest(a.fixture)}
(a.out / 'input.json').write_text(json.dumps(input_identity, indent=2) + '\n')
assert meta['outcome'] == 'accept' and meta['size'] == input_identity['size']
assert meta['sha256'] == expected['input_sha256'] == input_identity['sha256']
with a.fixture.open('rb') as inp:
    try:
        result = subprocess.run([str(a.binary.resolve()), '--stdin', '--threads', '2',
                                 '--nat-extension', '--string-extension', '--axiom-allow-all'],
                                stdin=inp, capture_output=True, timeout=meta['timeout'])
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = 'UNKNOWN_TIME_BUDGET', exc.stdout or b'', exc.stderr or b''
(a.out / 'stdout.txt').write_bytes(stdout)
(a.out / 'stderr.txt').write_bytes(stderr)
found = re.search(rb'[Cc]hecked (\d+) declarations', stdout)
row = {'case': a.case, 'raw_exit': code, 'checked_declarations': int(found[1]) if found else None,
       'binary_sha256': binary_hash, 'input': input_identity, 'threads': 2,
       'expected_declarations': expected['declarations'],
       'boundary': 'Frozen generic candidate, unchanged original export and timeout; no Arena score.'}
(a.out / 'verdict.json').write_text(json.dumps(row, indent=2) + '\n')
print(json.dumps(row), flush=True)
assert code == 0 and row['checked_declarations'] == expected['declarations']
assert digest(a.binary) == binary_hash
