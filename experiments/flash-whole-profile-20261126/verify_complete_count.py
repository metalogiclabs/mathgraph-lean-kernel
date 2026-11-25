"""Verify the completed, frozen-executable instruction diagnostic archive."""
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

p = Path(sys.argv[1])
assert hashlib.sha256(p.read_bytes()).hexdigest() == '1a24ca4c7161e0ad47e58bb0d4d3d11c3345c6d249cd6d42a9e7e3976d8ef9b5'
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    get = lambda n: json.loads(z.read(n))
    assert z.read('harness-commit.txt').decode().strip() == '2ba65451f90ce79b48a76cb5a33d0af3950e2fa1'
    assert z.read('source-tree.txt').decode().strip() == '06c257f0f2ff1f64711cfa54620b650e6dd59b7e'
    identity = get('counts/identity.json')
    assert identity['input_size'] == 6326141213
    assert identity['input_sha256'] == 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'
    assert identity['threads'] == 1
    assert len(set(identity['binary_sha256'].values())) == 2
    for arm, expected in identity['binary_sha256'].items():
        assert hashlib.sha256(z.read(f'builds/{arm}.bin')).hexdigest() == expected
    calibration = get('counts/calibration.json')
    assert {r['iterations'] for r in calibration} == {1, 17, 1000000} and len(calibration) == 3
    for r in calibration:
        assert r['raw_exit'] == 0 and r['observed'] == r['expected'] == 3*r['iterations'] + 5
        assert hashlib.sha256(z.read(f"counts/loop-{r['iterations']}.bin")).hexdigest() == r['binary_sha256']
    counter = get('counter-identity.json')
    assert counter['client_sha256'] == identity['client_sha256']
    assert hashlib.sha256(z.read('instruction_counter.c')).hexdigest() == counter['source_sha256']
    rows = get('counts/rows.json')
    assert len(rows) == 2 and {(r['arm'], r['round']) for r in rows} == {('baseline', 0), ('strict', 0)}
    for r in rows:
        assert r['raw_exit'] == 0 and r['complete_count'] is True
        tag = f"counts/{r['arm']}-{r['round']}"
        assert b'739167 declarations' in z.read(tag + '.stdout')
        hits = re.findall(rb'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)', z.read(tag + '.stderr'))
        assert len(hits) == 1 and int(hits[0]) == r['dynamic_instructions']
    values = {r['arm']: r['dynamic_instructions'] for r in rows}
    ratio = values['strict'] / values['baseline']
    assert ratio == get('counts/summary.json')['strict_to_baseline_ratio']
    print(json.dumps({'state': 'WARRANTED_BOUNDED_SOFTWARE_INSTRUCTION_DIAGNOSTIC',
        'run': 45712976230, 'artifact': 15069518161, 'archive_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
        'dynamic_instructions': values, 'candidate_to_baseline_ratio': ratio,
        'reduction_percent': 100*(1-ratio), 'observations': len(rows),
        'calibration_cases': len(calibration), 'boundary': identity['boundary'],
        'authority_boundary': 'Archive and execution records verified. The full multi-gigabyte input and compiled instrumentation client are not bundled in this archive. No official Arena instruction/rank claim.'}, indent=2))
