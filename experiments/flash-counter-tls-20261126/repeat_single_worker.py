"""Describe within-client variation after the original agreement gate failed.

This does not change or retry the original gate into a pass.
"""
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
ident = json.loads((root / 'prefix-identity.json').read_text())
assert hashlib.sha256(binary.read_bytes()).hexdigest() == ident['binary_sha256']
assert hashlib.sha256(fixture.read_bytes()).hexdigest() == ident['input_sha256']
rows = []
for round_no in [1, 2]:
    for arm in (['reference', 'tls'] if round_no == 1 else ['tls', 'reference']):
        tag = f'repeat-{arm}-{round_no}'
        argv = [str(dr), '-c', str(clients[arm]), '--', str(binary), '--stdin',
                '--threads', '1', '--nat-extension', '--string-extension', '--axiom-allow-all']
        before = time.monotonic()
        with fixture.open('rb') as source:
            p = subprocess.run(argv, stdin=source, capture_output=True, timeout=180)
        (root / (tag + '.stdout')).write_bytes(p.stdout)
        (root / (tag + '.stderr')).write_bytes(p.stderr)
        hits = re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)', p.stderr)
        match = re.search(rb'[Cc]hecked (\d+) declarations', p.stdout)
        row = {'arm': arm, 'workers': 1, 'round': round_no,
               'raw_exit': p.returncode, 'count': int(hits[0]) if len(hits) == 1 else None,
               'declarations': int(match[1]) if match else None,
               'elapsed_s': time.monotonic() - before}
        rows.append(row)
        (root / 'repeat-rows.json').write_text(json.dumps(rows, indent=2) + '\n')
        print(json.dumps(row), flush=True)
        assert p.returncode == 0 and row['declarations'] == 25131 and row['count'] is not None
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == ident['binary_sha256']
        assert {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in clients.items()} == ident['clients']
