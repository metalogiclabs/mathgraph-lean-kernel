"""Calibrated full-input software instruction diagnostic; never an Arena score."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--drrun', type=Path, required=True)
p.add_argument('--client', type=Path, required=True)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--binaries', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--whole', action='store_true')
p.add_argument('--rounds', type=int, default=2)
p.add_argument('--baseline-cli', action='store_true', help='Use flag arguments for a reconciled-core baseline.')
a = p.parse_args()
for name in ['drrun', 'client', 'fixture', 'binaries', 'out']:
    setattr(a, name, getattr(a, name).resolve())
a.out.mkdir(parents=True, exist_ok=True)
marker = rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)'
base_command = [str(a.drrun), '-c', str(a.client), '--']
controls = []
for n in [1, 17, 1000000]:
    assembly = a.out / f'loop-{n}.S'
    binary = a.out / f'loop-{n}.bin'
    assembly.write_text('.global _start\n.text\n_start:\n'
        f' movl ${n}, %ecx\n xorl %eax, %eax\n'
        'again:\n addl $1, %eax\n decl %ecx\n jnz again\n'
        ' movl $60, %eax\n xorl %edi, %edi\n syscall\n')
    subprocess.run(['gcc', '-nostdlib', '-no-pie', str(assembly), '-o', str(binary)], check=True)
    r = subprocess.run(base_command + [str(binary)], capture_output=True, timeout=30)
    (a.out / f'loop-{n}.stderr').write_bytes(r.stderr)
    hits = re.findall(marker, r.stderr)
    observed = int(hits[-1]) if hits else None
    row = {'iterations': n, 'expected': 3*n + 5, 'observed': observed,
        'raw_exit': r.returncode, 'binary_sha256': digest(binary)}
    controls.append(row)
    save(a.out / 'calibration.json', controls)
    assert r.returncode == 0 and observed == row['expected'], row
# Repeat explicit multithreaded coverage on the same counting client.
control_source = Path(__file__).resolve().parents[1] / 'flash-worker-study-20261126/worker_control.c'
control_binary = a.out / 'worker-control.bin'
subprocess.run(['gcc', '-O2', '-pthread', '-no-pie', str(control_source), '-o', str(control_binary)], check=True)
r = subprocess.run(base_command + [str(control_binary), '2', '20000000'], capture_output=True, timeout=120)
(a.out / 'worker-control.stdout').write_bytes(r.stdout)
(a.out / 'worker-control.stderr').write_bytes(r.stderr)
hits = re.findall(marker, r.stderr)
coverage = {'workers': 2, 'raw_exit': r.returncode, 'body_instructions': 120000000,
            'with_libraries': int(hits[-1]) if hits else None,
            'source_sha256': digest(control_source), 'binary_sha256': digest(control_binary)}
save(a.out / 'worker-coverage.json', coverage)
assert r.returncode == 0 and coverage['with_libraries'] is not None and 120000000 <= coverage['with_libraries'] <= 122400000
expected = (6326141213, 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec', 739167) if a.whole else (
    134232002, 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a', 25131)
assert (a.fixture.stat().st_size, digest(a.fixture)) == expected[:2]
binaries = {name: a.binaries / (name + '.bin') for name in ['baseline', 'strict']}
hashes = {name: digest(path) for name, path in binaries.items()}
assert len(set(hashes.values())) == 2, 'Identical executable comparisons are invalid'
config = a.out / 'baseline-config.json'
save(config, {'use_stdin': True, 'num_threads': 2, 'nat_extension': True,
    'string_extension': True, 'unsafe_permit_all_axioms': True,
    'unpermitted_axiom_hard_error': False, 'print_success_message': True})
identity = {'binary_sha256': hashes, 'input_sha256': expected[1], 'input_size': expected[0],
    'client_sha256': digest(a.client), 'threads': 2,
    'baseline_interface': 'flags' if a.baseline_cli else 'JSON configuration',
    'boundary': 'Dynamic basic-block application instruction estimate, including libraries. '
        'REP-string and asynchronous interruption accounting differs from other tools. '
        'Calibration covers straight-line loops, not all x86 or hardware semantics. '
        'This is not an official Arena instruction score.'}
save(a.out / 'identity.json', identity)
rows = []
for round_no in range(a.rounds):
    order = list(binaries) if round_no % 2 == 0 else list(reversed(binaries))
    for name in order:
        tag = f'{name}-{round_no}'
        command = base_command + [str(binaries[name])]
        command += [str(config)] if name == 'baseline' and not a.baseline_cli else [
            '--stdin', '--threads', '2', '--nat-extension', '--string-extension', '--axiom-allow-all']
        start = time.monotonic()
        with a.fixture.open('rb') as inp:
            process = subprocess.Popen(command, stdin=inp, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True)
            try:
                stdout, stderr = process.communicate(timeout=1800 if a.whole else 180)
                code = process.returncode
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                code = 'UNKNOWN_TIME_DIAGNOSTIC_BUDGET'
        (a.out / (tag + '.stdout')).write_bytes(stdout)
        (a.out / (tag + '.stderr')).write_bytes(stderr)
        hits = re.findall(marker, stderr)
        row = {'arm': name, 'round': round_no, 'raw_exit': code,
            'dynamic_instructions': int(hits[-1]) if hits else None,
            'elapsed_s': time.monotonic() - start,
            'complete_count': bool(re.search(rb'[Cc]hecked ' + str(expected[2]).encode() + rb' declarations', stdout))}
        rows.append(row)
        save(a.out / 'rows.json', rows)
        print(json.dumps(row), flush=True)
        assert code == 0 and row['dynamic_instructions'] is not None and row['complete_count'], row
        assert digest(a.client) == identity['client_sha256'], 'Counter changed during measurement'
        assert {n: digest(b) for n, b in binaries.items()} == hashes, 'Checker changed during measurement'
totals = {n: sum(r['dynamic_instructions'] for r in rows if r['arm'] == n) for n in binaries}
summary = {'observations': len(rows), 'strict_to_baseline_ratio': totals['strict'] / totals['baseline'],
    'boundary': identity['boundary']}
save(a.out / 'summary.json', summary)
print('SUMMARY', json.dumps(summary), flush=True)
