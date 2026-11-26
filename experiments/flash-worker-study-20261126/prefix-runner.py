"""Isolate worker count while intentionally keeping the executable identical.

This is a configuration comparison: each arm is uniquely identified by its
binary hash AND argv. It is not a comparison of supposedly different builds.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


p = argparse.ArgumentParser(description=__doc__)
for name in ['drrun', 'client', 'binary', 'fixture', 'out']:
    p.add_argument('--' + name, type=Path, required=True)
p.add_argument('--whole', action='store_true')
p.add_argument('--rounds', type=int, default=2)
a = p.parse_args()
for name in ['drrun', 'client', 'binary', 'fixture', 'out']:
    setattr(a, name, getattr(a, name).resolve())
a.out.mkdir(parents=True, exist_ok=True)


def save(name, value):
    (a.out / name).write_text(json.dumps(value, indent=2) + '\n')


expected = (6326141213, 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec', 739167) if a.whole else (
    134232002, 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a', 25131)
assert (a.fixture.stat().st_size, digest(a.fixture)) == expected[:2]
identity = {'binary_sha256': digest(a.binary), 'client_sha256': digest(a.client),
            'input_bytes': expected[0], 'input_sha256': expected[1], 'workers': [1, 2, 4],
            'boundary': 'Same binary and input, different declared worker counts. Dynamic '
                        'basic-block application instruction estimate including libraries. '
                        'Not hardware retired instructions, CPU time, whole-input transport '
                        'from a prefix, or an Arena score. Scheduling may change cache reuse.'}
save('identity.json', identity)
marker = rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)'
prefix = [str(a.drrun), '-c', str(a.client), '--']


def observe(tag, command, stdin=None, timeout=180):
    process = subprocess.Popen(prefix + command, stdin=stdin, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        code = process.returncode
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        code = 'UNKNOWN_TIME_DIAGNOSTIC_BUDGET'
    (a.out / (tag + '.stdout')).write_bytes(stdout)
    (a.out / (tag + '.stderr')).write_bytes(stderr)
    found = re.findall(marker, stderr)
    assert digest(a.client) == identity['client_sha256']
    assert digest(a.binary) == identity['binary_sha256']
    return code, int(found[-1]) if found else None, stdout


controls = []
for n in [1, 17, 1000000]:
    assembly = a.out / f'loop-{n}.S'
    binary = a.out / f'loop-{n}.bin'
    assembly.write_text('.global _start\n.text\n_start:\n'
                        f' movl ${n}, %ecx\n xorl %eax, %eax\n'
                        'again:\n addl $1, %eax\n decl %ecx\n jnz again\n'
                        ' movl $60, %eax\n xorl %edi, %edi\n syscall\n')
    subprocess.run(['gcc', '-nostdlib', '-no-pie', str(assembly), '-o', str(binary)], check=True)
    code, total, _ = observe(f'loop-{n}', [str(binary)])
    controls.append({'kind': 'exact_loop', 'iterations': n, 'raw_exit': code,
                     'expected': 3 * n + 5, 'observed': total})
    assert code == 0 and total == 3 * n + 5, controls[-1]
source = Path(__file__).with_name('worker_control.c')
binary = a.out / 'worker-control.bin'
subprocess.run(['gcc', '-O2', '-pthread', '-no-pie', str(source), '-o', str(binary)], check=True)
iterations = 20000000
for workers in [1, 2, 4]:
    code, total, _ = observe(f'worker-control-{workers}', [str(binary), str(workers), str(iterations)])
    exact_body = 3 * iterations * workers
    row = {'kind': 'thread_coverage', 'workers': workers, 'iterations': iterations,
           'loop_body_instructions': exact_body, 'observed_with_libraries': total,
           'raw_exit': code, 'source_sha256': digest(source), 'binary_sha256': digest(binary),
           'boundary': 'Total includes library and thread startup work. Every worker loop '
                       'must be counted; non-loop work must add less than 2%.'}
    controls.append(row)
    save('calibration.json', controls)
    assert code == 0 and total is not None and exact_body <= total <= exact_body * 1.02, row

rows = []
for round_no in range(a.rounds):
    for workers in ([1, 2, 4] if round_no % 2 == 0 else [4, 2, 1]):
        command = [str(a.binary), '--stdin', '--threads', str(workers), '--nat-extension',
                   '--string-extension', '--axiom-allow-all']
        with a.fixture.open('rb') as source:
            code, total, stdout = observe(f'workers-{workers}-{round_no}', command,
                                         stdin=source, timeout=1800 if a.whole else 180)
        row = {'workers': workers, 'round': round_no, 'raw_exit': code,
               'dynamic_instructions': total,
               'complete_count': bool(re.search(rb'[Cc]hecked ' + str(expected[2]).encode() + rb' declarations', stdout)),
               'argv': command}
        rows.append(row)
        save('rows.json', rows)
        print(json.dumps(row), flush=True)
        assert code == 0 and total and row['complete_count'], row
totals = {n: sum(r['dynamic_instructions'] for r in rows if r['workers'] == n) for n in [1, 2, 4]}
summary = {'observations': len(rows), 'ratios_to_two_workers': {n: t / totals[2] for n, t in totals.items()},
           'boundary': identity['boundary']}
save('summary.json', summary)
print(json.dumps(summary), flush=True)
