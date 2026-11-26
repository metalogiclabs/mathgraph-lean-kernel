"""Independently verify the exact hosted native-census archive."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('archive', type=Path)
a = p.parse_args()
raw = a.archive.read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'b15aa507b41f61c975c5fc720268f7c310854737b9790db137a140b4bd069cd1'
with zipfile.ZipFile(a.archive) as z:
    assert z.testzip() is None
    r = json.loads(z.read('whole/result.json'))
    assert (r['input_size'], r['input_sha256'], r['expected_declarations'], r['raw_exit'], r['threads']) == (
        6326141213, 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec', 739167, 0, 2)
    assert b'checked 739167 declarations' in z.read('whole/stdout')
    assert hashlib.sha256(z.read('census.bin')).hexdigest() == r['binary_sha256']
    assert z.read('observation-source-tree.txt').decode().strip() == 'c41624c373e12a46a86bcef4631a4bd20c99b1a5'
    patch = Path(__file__).with_name('census.patch').read_bytes()
    assert z.read('census.patch') == patch
    counts = [0] * 48
    records = 0
    for line in z.read('whole/stderr').decode().splitlines():
        if line.startswith('EVAL_COST_CENSUS '):
            row = json.loads(line.split(' ', 1)[1])['counts']
            assert len(row) == len(counts)
            counts = [x+y for x, y in zip(counts, row)]
            records += 1
    assert counts == r['counts'] and records == r['counter_records'] == 14418
    assert sum(counts[1:10]) == sum(counts[20:26])
    assert sum(counts[10:20]) == counts[21]+counts[23]+counts[25]
    assert counts[26] == sum(counts[27:31])
    assert counts[30] == counts[36]+counts[37]
    controls = json.loads(z.read('source-controls/rows.json'))
    assert len(controls) == 16 and all(x['observed'] == x['expected'] for x in controls)
    assert '39 passed; 0 failed' in z.read('tests.log').decode()
print(json.dumps({'verified': True, 'records': records, 'declarations': 739167,
    'boundary': 'Receipt and artifact verification; no second checker execution or native instruction score.'}))
