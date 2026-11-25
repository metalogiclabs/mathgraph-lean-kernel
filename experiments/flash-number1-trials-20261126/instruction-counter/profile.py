"""Profile the frozen checked executable; this never changes its verdict logic."""
import argparse
import bisect
import hashlib
import json
from pathlib import Path
import re
import resource
import signal
import os
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


def read_blocks(path):
    for line in path.read_text().splitlines():
        kind, pc, length, executions = line.split('\t')
        yield kind, int(pc, 16), int(length), int(executions)


def run(command, tag, out, fixture=None, seconds=30):
    start = time.monotonic()
    inp = fixture.open('rb') if fixture else subprocess.DEVNULL
    try:
        with (out / (tag + '.stdout')).open('wb') as stdout, (out / (tag + '.stderr')).open('wb') as stderr:
            p = subprocess.Popen(command, stdin=inp, stdout=stdout, stderr=stderr, start_new_session=True,
                preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
            try:
                code = p.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
                code = 'UNKNOWN_TIME_DIAGNOSTIC_BUDGET'
    finally:
        if fixture:
            inp.close()
    stderr = (out / (tag + '.stderr')).read_text(errors='replace')
    match = re.findall(r'FLASH_PROFILE instructions=(\d+) threads=(\d+)', stderr)
    return {'raw_exit': code, 'elapsed_s': time.monotonic() - start,
            'instructions': int(match[0][0]) if len(match) == 1 else None,
            'threads': int(match[0][1]) if len(match) == 1 else None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--drrun', required=True, type=Path)
    p.add_argument('--client', required=True, type=Path)
    p.add_argument('--binary', required=True, type=Path)
    p.add_argument('--binary-sha256', required=True)
    p.add_argument('--fixture', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--whole', action='store_true')
    p.add_argument('--seconds', type=int, default=1800)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for attr in ['drrun', 'client', 'binary', 'fixture', 'out']:
        setattr(a, attr, getattr(a, attr).resolve())
    expected = (6326141213, 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec', 739167) if a.whole else (
        134232002, 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a', 25131)
    identity = {'binary_sha256': digest(a.binary), 'client_sha256': digest(a.client),
        'input_sha256': digest(a.fixture), 'input_bytes': a.fixture.stat().st_size,
        'source_commit': 'bc704eebed4e009bc66af1a849f18315c11f1926',
        'source_tree': '06c257f0f2ff1f64711cfa54620b650e6dd59b7e',
        'boundary': 'Basic-block instruction frequencies, not hardware retirement. '
            'Compiled-function attribution includes inlined callees. REP and asynchronous-interruption limits apply.'}
    save(a.out / 'identity.json', identity)
    assert identity['binary_sha256'] == a.binary_sha256
    assert (identity['input_bytes'], identity['input_sha256']) == expected[:2]
    header = a.binary.read_bytes()[:20]
    assert header[:6] == b'\x7fELF\x02\x01' and int.from_bytes(header[16:18], 'little') == 3, 'Symbol attribution expects a 64-bit little-endian PIE'
    base = [str(a.drrun), '-thread_private', '-c', str(a.client)]
    controls = []
    for n in [1, 17, 1000000]:
        assembly, binary = a.out / f'loop-{n}.S', a.out / f'loop-{n}.bin'
        assembly.write_text('.global _start\n.text\n_start:\n'
            f' movl ${n}, %ecx\n xorl %eax, %eax\n'
            'again:\n addl $1, %eax\n decl %ecx\n jnz again\n'
            ' movl $60, %eax\n xorl %edi, %edi\n syscall\n')
        subprocess.run(['cc', '-nostdlib', '-no-pie', str(assembly), '-o', str(binary)], check=True)
        tag = f'calibration-{n}'
        blocks = a.out / (tag + '.tsv')
        row = run(base + [str(blocks), '--', str(binary)], tag, a.out)
        row.update({'iterations': n, 'expected': 3 * n + 5,
                    'block_sum': sum(length * count for _, _, length, count in read_blocks(blocks))})
        controls.append(row)
        save(a.out / 'calibration.json', controls)
        assert row['raw_exit'] == 0 and row['instructions'] == row['block_sum'] == row['expected']
    control = a.out / 'thread-control.bin'
    subprocess.run(['cc', '-O2', '-pthread', str(Path(__file__).with_name('control.c')), '-o', str(control)], check=True)
    thread_controls = []
    for round_no in range(3):
        pair = []
        for n in [1000000, 2000000]:
            tag = f'thread-control-{round_no}-{n}'
            table = a.out / (tag + '.tsv')
            row = run(base + [str(table), '--', str(control), str(n)], tag, a.out)
            row.update({'round': round_no, 'iterations': n,
                'block_sum': sum(length * count for _, _, length, count in read_blocks(table))})
            assert row['raw_exit'] == 0 and row['threads'] == 5 and row['instructions'] == row['block_sum']
            pair.append(row['instructions'])
            thread_controls.append(row)
        assert abs(pair[1] - pair[0] - 8000000) < 8000, pair
    save(a.out / 'thread-controls.json', thread_controls)
    shared = run([str(a.drrun), '-c', str(a.client), str(a.out / 'shared-cache-negative.tsv'),
                  '--', '/bin/true'], 'shared-cache-negative', a.out)
    assert shared['raw_exit'] != 0 and shared['instructions'] is None
    assert 'FLASH_PROFILE_INVALID' in (a.out / 'shared-cache-negative.stderr').read_text()
    save(a.out / 'shared-cache-negative.json', shared)
    blocks = a.out / 'checker-blocks.tsv'
    command = base + [str(blocks), '--', str(a.binary), '--stdin', '--threads', '1',
        '--nat-extension', '--string-extension', '--axiom-allow-all']
    row = run(command, 'checker', a.out, a.fixture, a.seconds)
    message = (a.out / 'checker.stdout').read_text(errors='replace')
    row['complete_accept'] = bool(re.search(r'[Cc]hecked ' + str(expected[2]) + r' declarations', message))
    save(a.out / 'result.json', row)
    assert row['raw_exit'] == 0 and row['complete_accept'] and row['instructions'] is not None, row
    symbols = subprocess.check_output(['nm', '-n', '-S', '--defined-only', '--demangle=rust', str(a.binary)], text=True)
    (a.out / 'symbols.txt').write_text(symbols)
    intervals = {}
    for line in symbols.splitlines():
        match = re.match(r'^([0-9a-f]+)\s+([0-9a-f]+)\s+[tTwW]\s+(.+)$', line)
        if match:
            start, size, name = int(match[1], 16), int(match[2], 16), match[3]
            if start not in intervals or size > intervals[start][0]:
                intervals[start] = (size, name)
    starts = sorted(intervals)
    counts, total, block_rows = {}, 0, 0
    for kind, pc, length, executions in read_blocks(blocks):
        cost = length * executions
        total += cost
        block_rows += 1
        name = 'shared libraries'
        if kind == 'M':
            index = bisect.bisect_right(starts, pc) - 1
            name = 'unresolved executable symbols'
            if index >= 0:
                size, candidate = intervals[starts[index]]
                if pc < starts[index] + size:
                    name = candidate
        counts[name] = counts.get(name, 0) + cost
    assert total == row['instructions'], (total, row)
    summary = {'state': 'WARRANTED_BOUNDED_COMPILED_FUNCTION_PROFILE', 'total': total,
        'blocks': block_rows, 'top': [{'function': name, 'instructions': cost, 'share': cost / total}
            for name, cost in sorted(counts.items(), key=lambda item: -item[1])],
        'boundary': identity['boundary']}
    save(a.out / 'profile.json', summary)
    print(json.dumps({'state': summary['state'], 'total': total, 'top': summary['top'][:20]}), flush=True)


if __name__ == '__main__':
    main()
