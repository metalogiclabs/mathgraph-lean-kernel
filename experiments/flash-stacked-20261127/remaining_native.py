"""Independent native repeat of the smaller-prune-cache locality hypothesis.

This follows an exploratory four-pair observation; the confirmation rule below
is fixed before collecting this new sample. It does not qualify full Mathlib.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import threading
import time

WORK = Path(os.environ.get('FLASH_STACK_WORK', '/tmp/flash-stack-work'))
OUT = WORK / 'evidence' / 'remaining-native'
OUT.mkdir(exist_ok=False)
BIN = WORK / 'evidence' / 'builds'
INPUT = Path('/tmp/flash-runtime/mathlib-prefix.ndjson')
ARMS = ['baseline-targeted', 'stack-control', 'stack-prune4']
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')
identity = json.loads((WORK / 'evidence/remaining-overhead/identity.json').read_text())
assert sha(INPUT) == identity['input_sha256']
assert {arm: sha(BIN / (arm + '.bin')) for arm in ARMS} == identity['executables']
save('protocol.json', {
    'state': 'PROSPECTIVE_NEW_SAMPLE_AFTER_EXPLORATORY_FOUR_PAIRS',
    'rounds': 12, 'checking_workers': 2, 'identity': identity,
    'order': 'Rotate first arm each round; reverse each second round.',
    'wall_locality_confirmation': 'vs stack-control: median paired ratio <= 0.99, at least 10/12 paired ratios < 1, median paired CPU <= 1.01 and peak RSS <= 1.05.',
    'boundary': 'Only this exact 25,131-declaration prefix, hardware and generic executable; no full-Mathlib, rank, or general wall-speed claim.'})
rows = []
for round_id in range(12):
    order = ARMS[round_id % 3:] + ARMS[:round_id % 3]
    if round_id % 2:
        order = list(reversed(order))
    for arm in order:
        assert sha(BIN / (arm + '.bin')) == identity['executables'][arm]
        tag = f'{round_id:02d}-{arm}'
        command = [str(BIN / (arm + '.bin')), '--stdin', '--threads', '2',
                   '--nat-extension', '--string-extension', '--axiom-allow-all']
        with INPUT.open('rb') as inp, (OUT / (tag + '.stdout')).open('wb') as out, (OUT / (tag + '.stderr')).open('wb') as err:
            start = time.monotonic()
            process = subprocess.Popen(command, stdin=inp, stdout=out, stderr=err, start_new_session=True)
            expired = []
            def stop():
                expired.append(True)
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            timer = threading.Timer(60, stop)
            timer.start()
            try:
                _, status, usage = os.wait4(process.pid, 0)
                process.returncode = os.waitstatus_to_exitcode(status)
                wall = time.monotonic() - start
            finally:
                timer.cancel()
        row = {'round': round_id, 'arm': arm, 'raw_exit': process.returncode,
               'wall_s': wall, 'cpu_s': usage.ru_utime + usage.ru_stime,
               'peak_rss_kib': usage.ru_maxrss, 'timeout': bool(expired),
               'complete': bool(re.search(rb'checked 25131 declarations', (OUT / (tag + '.stdout')).read_bytes()))}
        rows.append(row)
        save('rows.json', rows)
        assert row['raw_exit'] == 0 and row['complete'] and not row['timeout'], row
        print(json.dumps(row), flush=True)
results = {}
for arm in ['stack-control', 'stack-prune4']:
    results[arm] = {}
    for parent in ['baseline-targeted', 'stack-control']:
        child = [r for r in rows if r['arm'] == arm]
        base = [r for r in rows if r['arm'] == parent]
        ratios = [c['wall_s'] / b['wall_s'] for c, b in zip(child, base)]
        cpu = statistics.median(c['cpu_s'] / b['cpu_s'] for c, b in zip(child, base))
        rss = max(c['peak_rss_kib'] for c in child) / max(b['peak_rss_kib'] for b in base)
        results[arm][parent] = {'paired_wall_ratios': ratios, 'median_wall_ratio': statistics.median(ratios),
            'wall_improved_pairs': sum(v < 1 for v in ratios), 'median_cpu_ratio': cpu, 'peak_rss_ratio': rss,
            'locality_rule_passed': statistics.median(ratios) <= .99 and sum(v < 1 for v in ratios) >= 10 and cpu <= 1.01 and rss <= 1.05}
save('summary.json', {'results': results, 'boundary': 'New-sample native prefix confirmation; full input and broad correctness remain UNKNOWN.'})
print('SUMMARY', json.dumps(results), flush=True)
