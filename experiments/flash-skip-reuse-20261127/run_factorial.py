"""Calibrated four-arm screen with raw verdicts and matched-build resources."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

root = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parent / 'factorial'
out.mkdir(exist_ok=True)
bins = Path('/tmp/flash-skip-reuse-binaries')
fixture = Path('/tmp/flash-mathlib-prefix-128m/mathlib-prefix-128m.ndjson')
client = Path('/tmp/flash-eval-front-counter.so')
drrun = Path('/tmp/flash-dynamorio/DynamoRIO-Linux-11.92.20777/bin64/drrun')
arms = ['baseline', 'skip', 'reuse', 'combined']
args = ['--stdin', '--threads', '2', '--nat-extension', '--string-extension', '--axiom-allow-all']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, value): (out / name).write_text(json.dumps(value, indent=2) + '\n')
assert fixture.stat().st_size == 134232002
assert sha(fixture) == 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a'
assert sha(client) == '1b3c61f072436fd58606c84ff6198676cb194c47decc0a936cad1c74a35b26d9'
hashes = {arm: sha(bins / (arm + '.bin')) for arm in arms}
assert len(set(hashes.values())) == 4
save('identity.json', {'binary_sha256': hashes, 'input_sha256': sha(fixture),
     'client_sha256': sha(client), 'threads': 2,
     'build': 'same generic x86-64 executables for software counts and uninstrumented CPU/RSS'})
def check_hashes():
    assert {arm: sha(bins / (arm + '.bin')) for arm in arms} == hashes
    assert sha(client) == '1b3c61f072436fd58606c84ff6198676cb194c47decc0a936cad1c74a35b26d9'

calibration = []
for n in [1, 17, 1000000]:
    source = out / f'loop-{n}.S'; binary = out / f'loop-{n}.bin'
    source.write_text('.global _start\n.text\n_start:\n' + f' movl ${n}, %ecx\n xorl %eax, %eax\n'
        + 'again:\n addl $1, %eax\n decl %ecx\n jnz again\n movl $60, %eax\n xorl %edi, %edi\n syscall\n')
    subprocess.run(['gcc', '-nostdlib', '-no-pie', str(source), '-o', str(binary)], check=True)
    r = subprocess.run([str(drrun), '-c', str(client), '--', str(binary)], capture_output=True, timeout=30)
    (out / f'loop-{n}.stderr').write_bytes(r.stderr)
    hits = re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)', r.stderr)
    count = int(hits[0]) if len(hits) == 1 else None
    assert r.returncode == 0 and count == 3 * n + 5
    calibration.append({'iterations': n, 'expected': 3*n+5, 'observed': count,
                        'raw_exit': r.returncode, 'binary_sha256': sha(binary)})
save('calibration.json', calibration)

def execute(arm, tag, instrumented):
    check_hashes()
    command = ([str(drrun), '-c', str(client), '--'] if instrumented else [])
    command += [str(bins / (arm + '.bin'))] + args
    start = time.perf_counter()
    with fixture.open('rb') as inp, (out / (tag + '.stdout')).open('wb') as stdout, (out / (tag + '.stderr')).open('wb') as stderr:
        process = subprocess.Popen(command, stdin=inp, stdout=stdout, stderr=stderr)
        expired = []
        def stop():
            expired.append(True)
            process.kill()
        timer = threading.Timer(180, stop); timer.start()
        try:
            _, status, usage = os.wait4(process.pid, 0)
            process.returncode = os.waitstatus_to_exitcode(status)
        finally: timer.cancel()
    row = {'arm': arm, 'raw_exit': process.returncode, 'wall_s': time.perf_counter()-start,
           'complete_count': bool(re.search(rb'checked 25131 declarations', (out / (tag + '.stdout')).read_bytes())),
           'cpu_s': usage.ru_utime+usage.ru_stime, 'max_rss_kib': usage.ru_maxrss,
           'timed_out': bool(expired)}
    if instrumented:
        hits = re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)', (out / (tag + '.stderr')).read_bytes())
        row['instructions'] = int(hits[0]) if len(hits) == 1 else None
    check_hashes()
    assert row['raw_exit'] == 0 and row['complete_count'] and not expired, row
    if instrumented: assert row['instructions'] is not None
    print(tag, json.dumps(row), flush=True)
    return row

# Identical-executable A/A controls intentionally estimate scheduling variation.
# Their threshold is frozen before measuring any candidate arm.
controls = [execute('baseline', 'noise-' + str(i), True) for i in range(2)]
noise = abs(controls[0]['instructions'] - controls[1]['instructions']) / min(r['instructions'] for r in controls)
threshold = max(.01, 2 * noise)
save('prospective-noise-gate.json', {'controls': controls, 'observed_fractional_range': noise,
     'minimum_fractional_reduction': threshold, 'formula': 'max(1%, twice the two baseline controls fractional range)',
     'boundary': 'Conservative screening rule fixed before candidate observations; not a statistical confidence interval.'})
rows = []
for instrumented in [True, False]:
    kind = 'instructions' if instrumented else 'native'
    for round_no in range(2):
        for arm in arms if round_no == 0 else reversed(arms):
            row = execute(arm, kind + '-' + arm + '-' + str(round_no), instrumented)
            row.update(round=round_no, measurement=kind)
            rows.append(row); save('rows.json', rows)
results = {}
for arm in arms[1:]:
    counts = [r for r in rows if r['measurement'] == 'instructions']
    paired = [next(r['instructions'] for r in counts if r['arm'] == arm and r['round'] == i) /
              next(r['instructions'] for r in counts if r['arm'] == 'baseline' and r['round'] == i) for i in range(2)]
    ratio = sum(r['instructions'] for r in counts if r['arm'] == arm) / sum(r['instructions'] for r in counts if r['arm'] == 'baseline')
    native = [r for r in rows if r['measurement'] == 'native']
    cpu = sum(r['cpu_s'] for r in native if r['arm'] == arm) / sum(r['cpu_s'] for r in native if r['arm'] == 'baseline')
    rss = max(r['max_rss_kib'] for r in native if r['arm'] == arm) / max(r['max_rss_kib'] for r in native if r['arm'] == 'baseline')
    results[arm] = {'paired_instruction_ratios': paired, 'aggregate_instruction_ratio': ratio,
        'cpu_ratio_same_build': cpu, 'peak_rss_ratio_same_build': rss,
        'cost_gate_passed': all(r <= 1-threshold for r in paired) and ratio <= 1-threshold}
summary = {'state': 'BOUNDED_PREFIX_FACTORIAL', 'minimum_reduction': threshold, 'results': results,
           'boundary': 'Exact prefix only, two workers, generic build. Calibrated basic-block instruction estimate and matched-build CPU/RSS; not native-target hardware counts, full Mathlib or Arena scores.'}
save('summary.json', summary)
print('SUMMARY', json.dumps(summary), flush=True)
