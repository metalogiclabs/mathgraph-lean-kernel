"""Calibrate the attribution counter, then profile the unchanged complete input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--drrun', type=Path, required=True)
p.add_argument('--prepared', type=Path, required=True)
p.add_argument('--binary', type=Path, required=True)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--whole', action='store_true')
a = p.parse_args()
for name in ('drrun', 'prepared', 'binary', 'fixture', 'out'):
    setattr(a, name, getattr(a, name).resolve())
a.out.mkdir(parents=True, exist_ok=True)
assert hashlib.sha256(a.binary.read_bytes()).hexdigest() == '09fe7ecf7421be7ad7f7c57596c214bcd6e7c0d912d6d555cb5749b17202bd5b'
prefix = [str(a.drrun), '-c', str(a.prepared / 'profile-counter.so'), '--']
marker = rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)'
calibration = []
for n in (1, 17, 1000000):
    assembly = a.out / f'loop-{n}.S'
    binary = assembly.with_suffix('.bin')
    assembly.write_text('.global _start\n.text\n_start:\n' + f' movl ${n}, %ecx\n xorl %eax, %eax\n' +
        'again:\n addl $1, %eax\n decl %ecx\n jnz again\n movl $60, %eax\n xorl %edi, %edi\n syscall\n')
    subprocess.run(['gcc', '-nostdlib', '-no-pie', str(assembly), '-o', str(binary)], check=True)
    r = subprocess.run(prefix + [str(binary)], capture_output=True, timeout=30)
    (a.out / f'loop-{n}.stderr').write_bytes(r.stderr)
    hits = re.findall(marker, r.stderr)
    parts = re.findall(rb'MATHGRAPH_SYMBOL (\d+) (\d+)', r.stderr)
    observed = int(hits[0]) if len(hits) == 1 else None
    calibration.append({'iterations': n, 'expected': 3*n + 5, 'observed': observed, 'raw_exit': r.returncode})
    (a.out / 'calibration.json').write_text(json.dumps(calibration, indent=2) + '\n')
    assert r.returncode == 0 and observed == 3*n + 5 and sum(int(x[1]) for x in parts) == observed
expected = (6326141213, 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec', 739167) if a.whole else (
    134232002, 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a', 25131)
h = hashlib.sha256()
with a.fixture.open('rb') as f:
    for b in iter(lambda: f.read(1024 * 1024), b''):
        h.update(b)
assert a.fixture.stat().st_size == expected[0] and h.hexdigest() == expected[1]
start = time.monotonic()
with a.fixture.open('rb') as inp:
    process = subprocess.Popen(prefix + [str(a.binary), '--stdin', '--threads', '1', '--nat-extension', '--string-extension', '--axiom-allow-all'],
        stdin=inp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    stop = None
    try:
        stdout, stderr = process.communicate(timeout=1200 if a.whole else 180)
    except subprocess.TimeoutExpired:
        stop = 'UNKNOWN_TIME_DIAGNOSTIC_BUDGET'
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
(a.out / 'stdout').write_bytes(stdout)
(a.out / 'stderr').write_bytes(stderr)
result = {'raw_exit': process.returncode, 'diagnostic_stop': stop, 'elapsed_s': time.monotonic() - start,
    'input_sha256': expected[1], 'input_size': expected[0], 'threads': 1,
    'checked_declarations': expected[2] if re.search(rb'checked ' + str(expected[2]).encode() + rb' declarations', stdout) else None}
(a.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
assert result['raw_exit'] == 0 and stop is None and result['checked_declarations'] == expected[2], result
hits = re.findall(marker, stderr)
assert len(hits) == 1
total = int(hits[0])
parts = [(int(i), int(n)) for i, n in re.findall(rb'MATHGRAPH_SYMBOL (\d+) (\d+)', stderr)]
assert len(parts) == len({i for i, _ in parts}) and sum(n for _, n in parts) == total
mapping = json.loads((a.prepared / 'symbol-map.json').read_text())['symbols']
names = [r['name'] for r in mapping] + ['[shared libraries / other code]', '[main executable without a sized text symbol]']
assert all(i < len(names) for i, _ in parts)
rows = sorted([{'symbol_index': i, 'name': names[i], 'instructions': n, 'share': n / total} for i, n in parts], key=lambda r: -r['instructions'])
(a.out / 'exclusive-symbols.json').write_text(json.dumps(rows, indent=2) + '\n')
summary = {'state': 'WARRANTED_BOUNDED_COMPILED_SYMBOL_DIAGNOSTIC', 'total_dynamic_instructions': total,
    'active_symbols_or_buckets': len(parts), 'top': rows[:30],
    'boundary': 'Same basic-block estimate as the preceding complete diagnostic. Inlined work belongs to its containing compiled symbol; symbol attribution is exclusive, not call-tree time. REP and asynchronous-interruption limitations remain. Not an Arena score or new checker qualification.'}
(a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'total': total, 'top': rows[:10], 'elapsed_s': result['elapsed_s']}, indent=2), flush=True)
