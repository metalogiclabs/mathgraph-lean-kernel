"""Bounded controls for the raw-TLS prototype; no kernel performance claim."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

root = Path(__file__).resolve().parent
work = root.parent
dr = work.parent / 'diagnostics/dynamorio/bin64/drrun'
clients = {'reference': work.parent / 'diagnostics/counter-v1.so',
           'tls': root / 'counter.so'}
rows = []

def run(arm, name, binary, args, expected, exact=True):
    before = time.monotonic()
    p = subprocess.run([str(dr), '-c', str(clients[arm]), '--', str(binary), *args],
                       capture_output=True, timeout=45)
    elapsed = time.monotonic() - before
    tag = arm + '-' + name
    (root / (tag + '.stdout')).write_bytes(p.stdout)
    (root / (tag + '.stderr')).write_bytes(p.stderr)
    found = re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)', p.stderr)
    observed = int(found[0]) if len(found) == 1 else None
    counts = re.findall(rb'MATHGRAPH_COUNTER_THREADS (\d+)', p.stderr)
    row = {'arm': arm, 'control': name, 'raw_exit': p.returncode,
           'expected': expected, 'observed': observed, 'exact': exact,
           'elapsed_s': elapsed, 'argv': [str(binary), *args],
           'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
           'client_sha256': hashlib.sha256(clients[arm].read_bytes()).hexdigest(),
           'threads_aggregated': int(counts[0]) if len(counts) == 1 else None}
    rows.append(row)
    (root / 'rows.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(row), flush=True)
    assert p.returncode == 0 and observed is not None, row
    assert observed == expected if exact else expected <= observed <= expected * 1.02, row
    if arm == 'tls':
        assert row['threads_aggregated'] is not None and row['threads_aggregated'] >= 1

for n in [1, 17, 1000000]:
    run('tls', f'loop-{n}', work / f'chunk512-prefix/loop-{n}.bin', [], 3 * n + 5)
    for family in ['', 'carry-one/']:
        run('tls', ('carry-one-' if family else 'carry-zero-') + str(n),
            work / f'counter-register-pressure/{family}pressure-{n}.bin', [], 3 * n + 49)
for workers in [1, 2, 4]:
    for arm in ['reference', 'tls']:
        run(arm, f'workers-{workers}', work / 'worker-prefix/worker-control.bin',
            [str(workers), '20000000'], workers * 60000000, exact=False)
        if arm == 'tls':
            assert rows[-1]['threads_aggregated'] >= workers + 1
print('All 15 bounded controls passed')
