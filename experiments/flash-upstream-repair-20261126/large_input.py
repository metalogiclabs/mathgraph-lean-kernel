"""Verify one unchanged large Arena input and preserve the raw checker verdict."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


root = Path(os.environ['RUNNER_TEMP'])
out = root / 'large-evidence'
out.mkdir(exist_ok=True)
name = os.environ['CASE']
manifest = json.loads(Path('experiments/flash-upstream-repair-20261126/official-inputs.json').read_text())
matches = [t for t in manifest['tests'] if t['name'] == name]
assert len(matches) == 1
meta = matches[0]
assert meta['size'] > 10 * 1024**2 and meta['outcome'] == 'accept'
fixture = root / 'large-input' / 'test.ndjson'
h = hashlib.sha256()
with fixture.open('rb') as f:
    for b in iter(lambda: f.read(1024 * 1024), b''):
        h.update(b)
identity = {'name': name, 'size': fixture.stat().st_size, 'sha256': h.hexdigest()}
(out / 'input.json').write_text(json.dumps(identity, indent=2) + '\n')
assert identity['size'] == meta['size'] and identity['sha256'] == meta['sha256'], identity
binary = Path('target/release/sokonanoda').resolve()
command = [str(binary), '--stdin', '--threads', '2', '--nat-extension',
    '--string-extension', '--axiom-allow-all']
start = time.monotonic()
try:
    with fixture.open('rb') as inp:
        result = subprocess.run(['/usr/bin/time', '-v', '-o', str(out / 'resources.txt')] + command,
            stdin=inp, capture_output=True, timeout=meta['timeout'])
    code, stdout, stderr = result.returncode, result.stdout, result.stderr
except subprocess.TimeoutExpired as e:
    code, stdout, stderr = 'TIMEOUT', e.stdout or b'', e.stderr or b''
(out / 'stdout.txt').write_bytes(stdout)
(out / 'stderr.txt').write_bytes(stderr)
counts = re.findall(rb'[Cc]hecked (\d+) declarations', stdout)
row = {'name': name, 'input_sha256': identity['sha256'],
    'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
    'threads': 2, 'raw_exit': code, 'elapsed_s': time.monotonic() - start,
    'checked_declarations': int(counts[-1]) if counts else None,
    'boundary': 'Exact complete input compatibility; native resources are not an Arena instruction score.'}
(out / 'verdict.json').write_text(json.dumps(row, indent=2) + '\n')
print('LARGE_VERDICT', json.dumps(row), flush=True)
assert code == 0 and row['checked_declarations'] is not None, row
