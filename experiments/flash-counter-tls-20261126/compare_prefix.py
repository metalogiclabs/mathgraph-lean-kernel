"""Compare instrumentation overhead on the same frozen checker/input."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

root = Path(__file__).resolve().parent
work = root.parent
dr = work.parent / 'diagnostics/dynamorio/bin64/drrun'
binary = work.parent / 'build-upstream-repair/release/sokonanoda'
fixture = Path('/tmp/flash-mathlib-prefix-128m/mathlib-prefix-128m.ndjson')
clients = {'reference': work.parent / 'diagnostics/counter-v1.so', 'tls': root / 'counter.so'}
identity = {'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'input_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
            'input_bytes': fixture.stat().st_size,
            'clients': {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in clients.items()}}
assert identity['binary_sha256'] == 'e066a66a357b86cbeeeae96cfb01241f4287f79a1b333db488b9294b7534e50b'
assert identity['input_sha256'] == 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a'
(root / 'prefix-identity.json').write_text(json.dumps(identity, indent=2) + '\n')
rows = []
for arm, workers in [('reference', 1), ('tls', 1), ('tls', 2), ('reference', 2)]:
    tag = f'prefix-{arm}-{workers}'
    argv = [str(dr), '-c', str(clients[arm]), '--', str(binary), '--stdin',
            '--threads', str(workers), '--nat-extension', '--string-extension', '--axiom-allow-all']
    before = time.monotonic()
    with fixture.open('rb') as source:
        p = subprocess.run(argv, stdin=source, capture_output=True, timeout=180)
    elapsed = time.monotonic() - before
    (root / (tag + '.stdout')).write_bytes(p.stdout)
    (root / (tag + '.stderr')).write_bytes(p.stderr)
    found = re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)', p.stderr)
    match = re.search(rb'[Cc]hecked (\d+) declarations', p.stdout)
    row = {'arm': arm, 'workers': workers, 'raw_exit': p.returncode,
           'count': int(found[0]) if len(found) == 1 else None,
           'declarations': int(match[1]) if match else None, 'elapsed_s': elapsed}
    rows.append(row)
    (root / 'prefix-rows.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(row), flush=True)
    assert row['raw_exit'] == 0 and row['declarations'] == 25131 and row['count'] is not None
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == identity['binary_sha256']
    assert {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in clients.items()} == identity['clients']
reference = next(r['count'] for r in rows if r['arm'] == 'reference' and r['workers'] == 1)
candidate = next(r['count'] for r in rows if r['arm'] == 'tls' and r['workers'] == 1)
assert abs(candidate / reference - 1) < 0.00001, 'single-worker counting disagreement'
