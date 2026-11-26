"""Independently verify the retained PGO or native-worker execution archive.

Usage: python verify_diagnostic_archive.py {pgo,workers} artifact.zip
This verifies execution receipts, not a fresh checker run or global soundness.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('kind', choices=['pgo', 'workers'])
p.add_argument('archive', type=Path)
p.add_argument('--manifest', type=Path,
               default=Path(__file__).resolve().parents[1] / 'flash-upstream-repair-20261126/official-inputs.json')
a = p.parse_args()
expected = {
    'pgo': (15076991448, 'a58fc7871d0513b413643fff15fbb83fda1f84b056c133f31688f2f377cb2b56',
            'f24c67064ff93c8c62f94114068aa929d69d4b08'),
    'workers': (15077182392, 'dab288e7db2c89e92c19e10abf2e1dde5cd8638a52ea325eb67faf230439140e',
                'dc6eb9ebb1dad1a8c42979b822ea1130d7ca1a97'),
}[a.kind]
assert hashlib.sha256(a.archive.read_bytes()).hexdigest() == expected[1]
with zipfile.ZipFile(a.archive) as z:
    assert z.testzip() is None

    def text(name):
        return z.read(name).decode()

    def data(name):
        return json.loads(text(name))

    def sha(name):
        return hashlib.sha256(z.read(name)).hexdigest()

    assert text('harness-commit.txt').strip() == expected[2]
    assert text('source-tree.txt').strip() == '06c257f0f2ff1f64711cfa54620b650e6dd59b7e'
    identity = data('native/identity.json')
    assert identity['input'] == {
        'size': 6326141213,
        'sha256': 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec',
    }
    binaries = ({n: sha('builds/' + n + '.bin') for n in ['baseline', 'strict']}
                if a.kind == 'pgo' else {n: sha('checker.bin') for n in ['1', '2']})
    assert identity['binary_sha256'] == binaries
    assert len(set(binaries.values())) == (2 if a.kind == 'pgo' else 1)
    rows = data('native/rows.json')
    assert len(rows) == 4
    for row in rows:
        assert row['raw_exit'] == 0 and row['declarations'] == 739167
        tag = f"native/{row['arm']}-{row['round']}"
        assert re.search(r'checked 739167 declarations', text(tag + '.stdout'), re.I)
        timing = text(tag + '.time').splitlines()[-1].split('\t')
        assert abs(row['cpu_s'] - float(timing[1]) - float(timing[2])) < 1e-6
    medians = {n: statistics.median(r['cpu_s'] for r in rows if r['arm'] == n) for n in binaries}
    assert data('portable/summary.json') == {
        'attempted': 230, 'correct': 230, 'wrong_or_unavailable': [],
    }
    tests = {t['name']: t for t in json.loads(a.manifest.read_text())['tests']
             if t['size'] <= 10 * 1024**2}
    portable = data('portable/rows.json')
    assert len(portable) == len(tests) == 230 and {r['name'] for r in portable} == set(tests)
    for row in portable:
        spec = tests[row['name']]
        assert row['sha256'] == spec['sha256']
        assert row['expected'] == row['observed'] == (0 if spec['outcome'] == 'accept' else 1)
    assert data('source-controls/summary.json')['controls'] == 16
    assert not data('source-controls/summary.json')['wrong']
    for row in data('source-controls/rows.json'):
        assert row['observed'] == row['expected']
    assert 'test result: ok. 39 passed; 0 failed' in text('native-tests.log')
    calibration = data('instructions/calibration.json')
    assert len(calibration) == (3 if a.kind == 'pgo' else 6)
    for row in calibration:
        assert row['raw_exit'] == 0
        if row.get('kind') == 'thread_coverage':
            body = 3 * row['iterations'] * row['workers']
            assert row['loop_body_instructions'] == body
            assert body <= row['observed_with_libraries'] <= 1.02 * body
        else:
            assert row['expected'] == row['observed'] == 3 * row['iterations'] + 5
    counts = data('instructions/rows.json')
    if a.kind == 'pgo':
        assert len(counts) == 2
        for row in counts:
            assert row['raw_exit'] == 0 and row['complete_count']
            tag = f"instructions/{row['arm']}-{row['round']}"
            assert re.search(r'checked 739167 declarations', text(tag + '.stdout'), re.I)
            total = re.findall(r'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)', text(tag + '.stderr'))
            assert len(total) == 1 and int(total[0]) == row['dynamic_instructions']
        train = data('training/identity.json')
        assert train['generator_binary_sha256'] == sha('training.bin')
        assert train['gzip_sha256'] == sha('training/init.ndjson.gz')
        assert len(train['raw_profiles']) == 2
        for name, receipt in train['raw_profiles'].items():
            assert sha('raw/' + name) == receipt['sha256']
            assert len(z.read('raw/' + name)) == receipt['bytes']
        assert sha('training.profdata') == text('profdata.sha256').split()[0]
        result = {'cpu_medians': medians,
                  'software_ratio': counts[1]['dynamic_instructions'] / counts[0]['dynamic_instructions']}
    else:
        assert len(counts) == 1 and counts[0]['raw_exit'] == -4
        assert counts[0]['dynamic_instructions'] is None and not counts[0]['complete_count']
        result = {'cpu_medians': medians, 'instruction_state': 'UNKNOWN_INSTRUMENTED_SIGILL'}
    print(json.dumps({'archive': expected[0], 'sha256_crc_and_receipts': 'PASS',
                      'binary_sha256': binaries, **result}, indent=2))
