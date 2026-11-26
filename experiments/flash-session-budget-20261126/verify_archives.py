"""Independently verify retained archives and reconstruct the reported metrics."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--archives', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
expected = {
    'instructions': (15119595581, 1803047, '00a788179a00c60fe615d89f05d2bc151c442b1b99cbacc2af91638b0627d267'),
    'native': (15113847340, 1915134, 'ca51a7c941e7fc788795232c61b77bf6069e6c2f3c04e7a89170e3f1448c02ef'),
}
result = {'state': 'WARRANTED_BOUNDED_EXPERIMENT', 'run_id': 45811406828,
          'harness_commit': 'eef92be0975e106aa371d120a3d342af9f597070', 'archives': {}}
manifest = json.loads((Path(__file__).resolve().parents[1] /
    'flash-upstream-repair-20261126/official-inputs.json').read_text())
portable = {t['name']: t for t in manifest['tests']
            if t['outcome'] in ['accept', 'reject'] and t['size'] <= 10 * 1024**2}
assert len(portable) == 230
for mode, (artifact, size, digest) in expected.items():
    path = a.archives / ('flash-budget-verified-' + mode + '.zip')
    assert path.stat().st_size == size
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        read_json = lambda name: json.loads(z.read(name))
        assert z.read('harness-commit.txt').decode().strip() == result['harness_commit']
        assert z.read('baseline-source-tree.txt').decode().strip() == '06c257f0f2ff1f64711cfa54620b650e6dd59b7e'
        assert z.read('strict-source-tree.txt').decode().strip() == 'c5c0ec81bcba210382242ce5c4777b052f48780f'
        assert hashlib.sha256(z.read('prototype.patch')).digest() == hashlib.sha256(
            Path(__file__).with_name('prototype.patch').read_bytes()).digest()
        identity = read_json(mode + '/identity.json')
        for arm, sha in identity['binary_sha256'].items():
            assert hashlib.sha256(z.read('builds/' + arm + '.bin')).hexdigest() == sha
        checks = read_json('source-controls/summary.json')
        assert checks['controls'] == 16 and checks['wrong'] == []
        tests = z.read('tests.log').decode()
        assert 'test result: ok. 39 passed; 0 failed' in tests
        assert 'test retained_source_regressions ... ok' in tests
        gate = read_json('gate.json')
        assert gate['passed'] and all(gate['checks'].values())
        rows = read_json(mode + '/rows.json')
        assert len(rows) == 4
        for row in rows:
            tag = row['arm'] + '-' + str(row['round'])
            assert re.search(rb'[Cc]hecked 739167 declarations', z.read(mode + '/' + tag + '.stdout'))
            if mode == 'instructions':
                assert row['raw_exit'] == 0 and row['complete_count']
                raw = re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)',
                                 z.read(mode + '/' + tag + '.stderr'))
                assert len(raw) == 1 and int(raw[0]) == row['dynamic_instructions']
            else:
                assert row['observed'] == 0 and row['declarations'] == 739167
                wall, user, system, rss = z.read(mode + '/' + tag + '.time').decode().strip().split('\t')
                assert row['wall_s'] == float(wall)
                assert abs(row['cpu_s'] - float(user) - float(system)) < 1e-9
                assert row['max_rss_kb'] == int(rss)
        if mode == 'instructions':
            for control in read_json('instructions/calibration.json'):
                assert control['raw_exit'] == 0
                assert control['observed'] == control['expected'] == 3 * control['iterations'] + 5
                loop = z.read('instructions/loop-' + str(control['iterations']) + '.bin')
                assert hashlib.sha256(loop).hexdigest() == control['binary_sha256']
            assert identity['input_size'] == 6326141213
            assert identity['input_sha256'] == 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'
            counter = read_json('counter-identity.json')
            assert counter['client_sha256'] == identity['client_sha256']
            assert counter['source_sha256'] == hashlib.sha256(Path(__file__).with_name('instruction_counter.c').read_bytes()).hexdigest()
            totals = {arm: sum(r['dynamic_instructions'] for r in rows if r['arm'] == arm)
                      for arm in ['baseline', 'strict']}
            ratio = totals['strict'] / totals['baseline']
            assert ratio == read_json('instructions/summary.json')['strict_to_baseline_ratio']
            result['software_instruction_ratio'] = ratio
            result['software_instruction_reduction'] = 1 - ratio
            result['paired_instruction_ratios'] = [
                next(r['dynamic_instructions'] for r in rows if r['arm'] == 'strict' and r['round'] == i) /
                next(r['dynamic_instructions'] for r in rows if r['arm'] == 'baseline' and r['round'] == i)
                for i in range(2)]
        else:
            assert identity['input'] == {'size': 6326141213, 'sha256': 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'}
            entries = read_json('portable/rows.json')
            assert len(entries) == len({r['name'] for r in entries}) == 230
            for row in entries:
                meta = portable[row['name']]
                assert row['sha256'] == meta['sha256']
                assert row['observed'] == row['expected'] == (0 if meta['outcome'] == 'accept' else 1)
            result['hosted_portable_correct'] = len(entries)
            cpus = {arm: statistics.median(r['cpu_s'] for r in rows if r['arm'] == arm)
                    for arm in ['baseline', 'strict']}
            peaks = {arm: max(r['max_rss_kb'] for r in rows if r['arm'] == arm)
                     for arm in ['baseline', 'strict']}
            result['native_cpu_ratio'] = cpus['strict'] / cpus['baseline']
            result['native_peak_rss_kib'] = peaks
            result['native_peak_rss_ratio'] = peaks['strict'] / peaks['baseline']
        dest = a.out / mode
        for name in z.namelist():
            if name.endswith('.bin') or name.startswith('source-controls/'):
                continue
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
        result['archives'][mode] = {'artifact_id': artifact, 'size': size, 'sha256': digest,
                                  'crc_verified_entries': len(z.namelist())}
result['release_state'] = 'NOT_PROMOTED: native CPU regression; nine other large prescribed cases and an independent Arena result remain unqualified.'
result['remaining_large_cases'] = [t['name'] for t in manifest['tests']
    if t['outcome'] in ['accept', 'reject'] and t['size'] > 10 * 1024**2 and t['name'] != 'mathlib']
assert len(result['remaining_large_cases']) == 9
result['large_case_prose_correction'] = ('Earlier protocol prose said ten other large cases. '
    'The pinned 240-case manifest has ten large cases including Mathlib; nine remain.')
result['declared_gates'] = ('Both original declared gates PASSED. The native CPU regression is retained '
    'as an additional release concern; no prospective gate was retroactively changed.')
result['boundary'] = ('Archive, checker executable and loop executable hashes were independently rechecked. '
    'Metrics were reconstructed from archived raw records. Full-input hashes and compiled counter identity '
    'are runner evidence; the full 6.3 GB input and compiled counter were not separately downloaded. '
    'Software instruction counts are not official Arena hardware counts.')
(a.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
