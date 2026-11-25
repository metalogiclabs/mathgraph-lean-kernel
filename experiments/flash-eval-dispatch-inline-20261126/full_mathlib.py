"""Matched full-input native and software-count gates for the isolated compiler hint.

Executables are copied before any Cargo test build. Hardware Arena scoring and
the other nine large inputs remain separate obligations even if this gate passes.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import statistics
import subprocess

p = argparse.ArgumentParser(description=__doc__)
for name in ('baseline', 'candidate', 'fixture', 'drrun', 'client', 'out', 'candidate_source_tree'):
    p.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
a = p.parse_args()
for name in vars(a):
    setattr(a, name, getattr(a, name).resolve())
a.out.mkdir(parents=True, exist_ok=True)
helper = Path(__file__).resolve().parents[1] / 'flash-number1-trials-20261126/instruction-counter/profile.py'
spec = importlib.util.spec_from_file_location('frozen_counter_helpers', helper)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
expected_hash = 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'
assert a.fixture.stat().st_size == 6326141213 and m.digest(a.fixture) == expected_hash
binaries = {'baseline': a.baseline, 'candidate': a.candidate}
hashes = {name: m.digest(binary) for name, binary in binaries.items()}
assert hashes['baseline'] == '09fe7ecf7421be7ad7f7c57596c214bcd6e7c0d912d6d555cb5749b17202bd5b'
assert len(set(hashes.values())) == 2
source_tree = a.candidate_source_tree.read_text().strip()
assert source_tree == 'de6696fcecbe99e6fcab5bb68c5974e1e9a04e49'
m.save(a.out / 'identity.json', {'binary_sha256': hashes, 'input_sha256': expected_hash,
    'input_bytes': 6326141213, 'base_commit': 'bc704eebed4e009bc66af1a849f18315c11f1926',
    'baseline_source_tree': '06c257f0f2ff1f64711cfa54620b650e6dd59b7e',
    'candidate_source_tree': source_tree, 'client_sha256': m.digest(a.client),
    'helper_sha256': m.digest(helper), 'native_check_workers': 2, 'count_check_workers': 1,
    'boundary': 'Generic-build matched execution. Software basic-block counts are not the Arena hardware event; REP and asynchronous limits remain.'})
base = [str(a.drrun), '-thread_private', '-c', str(a.client)]
calibration = []
for n in (1, 17, 1000000):
    assembly, binary = a.out / f'loop-{n}.S', a.out / f'loop-{n}.bin'
    assembly.write_text('.global _start\n.text\n_start:\n' + f' movl ${n}, %ecx\n xorl %eax, %eax\n' +
        'again:\n addl $1, %eax\n decl %ecx\n jnz again\n movl $60, %eax\n xorl %edi, %edi\n syscall\n')
    subprocess.run(['cc', '-nostdlib', '-no-pie', str(assembly), '-o', str(binary)], check=True)
    table = a.out / f'calibration-{n}.tsv'
    row = m.run(base + [str(table), '--', str(binary)], f'calibration-{n}', a.out)
    row.update({'iterations': n, 'expected': 3*n+5, 'sum': sum(size*count for _, _, size, count in m.read_blocks(table))})
    calibration.append(row)
    m.save(a.out / 'calibration.json', calibration)
    assert row['raw_exit'] == 0 and row['instructions'] == row['sum'] == row['expected']
shared = m.run([str(a.drrun), '-c', str(a.client), str(a.out / 'invalid-shared.tsv'), '--', '/bin/true'], 'invalid-shared', a.out)
m.save(a.out / 'shared-cache-negative.json', shared)
assert shared['raw_exit'] != 0 and shared['instructions'] is None
rows = []
for round_no, order in enumerate([('baseline', 'candidate'), ('candidate', 'baseline')]):
    for arm in order:
        assert m.digest(binaries[arm]) == hashes[arm]
        tag = f'native-{arm}-{round_no}'
        resources = a.out / (tag + '.time')
        cmd = ['/usr/bin/time', '-f', '%U %S %M %e', '-o', str(resources), str(binaries[arm]),
            '--stdin', '--threads', '2', '--nat-extension', '--string-extension', '--axiom-allow-all']
        row = m.run(cmd, tag, a.out, a.fixture, seconds=600)
        complete = b'739167 declarations' in (a.out / (tag + '.stdout')).read_bytes()
        row.update({'mode': 'native', 'arm': arm, 'round': round_no, 'complete_count': complete})
        rows.append(row)
        m.save(a.out / 'rows.json', rows)
        assert row['raw_exit'] == 0 and complete, row
        user, system, rss, wall = resources.read_text().splitlines()[-1].split()
        row.update({'cpu_s': float(user)+float(system), 'max_rss_kb': int(rss), 'wall_s': float(wall)})
        m.save(a.out / 'rows.json', rows)
        print(json.dumps(row), flush=True)
for round_no, order in enumerate([('baseline', 'candidate'), ('candidate', 'baseline')]):
    for arm in order:
        assert m.digest(binaries[arm]) == hashes[arm]
        tag = f'count-{arm}-{round_no}'
        table = a.out / (tag + '.tsv')
        cmd = base + [str(table), '--', str(binaries[arm]), '--stdin', '--threads', '1',
            '--nat-extension', '--string-extension', '--axiom-allow-all']
        row = m.run(cmd, tag, a.out, a.fixture, seconds=900)
        complete = b'739167 declarations' in (a.out / (tag + '.stdout')).read_bytes()
        row.update({'mode': 'count', 'arm': arm, 'round': round_no, 'complete_count': complete})
        rows.append(row)
        m.save(a.out / 'rows.json', rows)
        assert row['raw_exit'] == 0 and complete and row['instructions'] is not None, row
        row['block_sum'] = sum(size*count for _, _, size, count in m.read_blocks(table))
        assert row['block_sum'] == row['instructions']
        m.save(a.out / 'rows.json', rows)
        print(json.dumps(row), flush=True)
counts = {(r['arm'],r['round']):r['instructions'] for r in rows if r['mode']=='count'}
ratios = [counts['candidate',n]/counts['baseline',n] for n in (0,1)]
cpu = {arm:statistics.median(r['cpu_s'] for r in rows if r['mode']=='native' and r['arm']==arm) for arm in binaries}
rss = {arm:max(r['max_rss_kb'] for r in rows if r['mode']=='native' and r['arm']==arm) for arm in binaries}
passed = all(r<=0.99 for r in ratios) and cpu['candidate']/cpu['baseline']<=1.05 and rss['candidate']/rss['baseline']<=1.10
summary = {'state':'CANDIDATE_FULL_MATHLIB_GATE_PASSED' if passed else 'REJECTED_FOR_PERFORMANCE_PROMOTION',
    'instruction_paired_ratios':ratios,'instruction_geometric_ratio':math.sqrt(math.prod(ratios)),
    'cpu_medians_s':cpu,'cpu_ratio':cpu['candidate']/cpu['baseline'],'peak_rss_kb':rss,
    'peak_rss_ratio':rss['candidate']/rss['baseline'],'observations':len(rows),'passed':passed,
    'gate':'Each complete instruction pair <=0.99, native median CPU ratio <=1.05, maximum observed RSS ratio <=1.10; every process accepts exactly 739167 declarations.',
    'boundary':'Full Mathlib only, generic builds. Other nine large candidate inputs, target-cpu=native Arena hardware scoring and release remain separate UNKNOWNs.'}
m.save(a.out / 'summary.json',summary)
print(json.dumps(summary,indent=2),flush=True)
