"""Verify the complete comparison and join it to the verified 239-case capsule.

This checks original execution receipts and actual executable bytes. It does
not rerun the checker, prove universal soundness, or establish an Arena rank.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive', type=Path, required=True)
p.add_argument('--sha256', required=True)
p.add_argument('--qualification', type=Path, required=True)
p.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] /
               'flash-upstream-repair-20261126/official-inputs.json')
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
assert hashlib.sha256(a.archive.read_bytes()).hexdigest() == a.sha256
qualification = json.loads(a.qualification.read_text())
assert qualification['candidate_commit'] == '4816054e2331c3cd6b57cbcd51d3e265b48c68e7'
assert qualification['candidate_source_tree'] == 'fa9f0de20650f28f63f1d01d7dab50397e167bcf'
assert qualification['portable_correct'] == 230 and len(qualification['large_cases']) == 9
manifest = json.loads(a.manifest.read_text())
portable_expected = {r['name']: r for r in manifest['tests']
                     if r.get('outcome') in ['accept', 'reject'] and r['size'] <= 10 * 1024 * 1024}
assert len(portable_expected) == 230

with zipfile.ZipFile(a.archive) as z:
    assert z.testzip() is None
    names = z.namelist()
    assert all(not n.startswith('/') and '..' not in Path(n).parts for n in names)

    def text(name):
        return z.read(name).decode()

    def data(name):
        return json.loads(text(name))

    def sha(name):
        return hashlib.sha256(z.read(name)).hexdigest()

    g = 'chunk512/'
    n = 'chunk512-native/'
    generic_hashes = {arm: sha(g + 'builds/' + arm + '.bin') for arm in ['baseline', 'strict']}
    assert generic_hashes['baseline'] == '09fe7ecf7421be7ad7f7c57596c214bcd6e7c0d912d6d555cb5749b17202bd5b'
    assert generic_hashes['strict'] == qualification['frozen_generic_binary_sha256']
    assert len(set(generic_hashes.values())) == 2
    candidate_identity = data(g + 'identity.json')
    assert candidate_identity['candidate_commit'] == qualification['candidate_commit']
    assert candidate_identity['candidate_source_tree'] == qualification['candidate_source_tree']
    assert candidate_identity['candidate_binary_sha256'] == generic_hashes['strict']
    portable_identity = data(g + 'portable/identity.json')
    assert portable_identity['binary_sha256'] == generic_hashes['strict']
    assert portable_identity['threads'] == 2
    portable_rows = data(g + 'portable/rows.json')
    assert len(portable_rows) == len({r['name'] for r in portable_rows}) == 230
    assert {r['name'] for r in portable_rows} == set(portable_expected)
    for row in portable_rows:
        original = portable_expected[row['name']]
        assert row['sha256'] == original['sha256']
        assert row['observed'] == row['expected'] == (0 if original['outcome'] == 'accept' else 1)
        assert g + 'portable/' + row['name'].replace('/', '_') + '.stdout' in names
        assert g + 'portable/' + row['name'].replace('/', '_') + '.stderr' in names
    source_rows = data(g + 'source-controls/rows.json')
    assert len(source_rows) == len({r['name'] for r in source_rows}) == 16
    for row in source_rows:
        assert row['observed'] == row['expected']
        assert row['sha256'] == sha(g + 'source-controls/' + row['name'] + '.ndjson')
    ident = data(g + 'instructions/identity.json')
    assert ident['binary_sha256'] == generic_hashes and ident['threads'] == 2
    assert ident['input_size'] == 6326141213
    assert ident['input_sha256'] == 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'
    counter = data(g + 'counter-identity.json')
    assert counter['source_sha256'] == '6d00654e55d4b2049ff3f2031383106b9658a0ddaa3a3a05db53261fb35adb34'
    assert counter['archive_sha256'] == '3958421d74964ea2a30b43752560ae584d854ceb6209946dd2d9e173352d7a2c'
    assert counter['client_sha256'] == ident['client_sha256']
    counts = data(g + 'instructions/rows.json')
    assert len(counts) == 2 and {r['arm'] for r in counts} == {'baseline', 'strict'}
    for row in counts:
        assert row['raw_exit'] == 0 and row['complete_count']
        tag = g + f"instructions/{row['arm']}-{row['round']}"
        assert re.search(r'checked 739167 declarations', text(tag + '.stdout'), re.I)
        found = re.findall(r'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)', text(tag + '.stderr'))
        assert len(found) == 1 and int(found[0]) == row['dynamic_instructions']
    controls = data(g + 'instructions/calibration.json')
    assert len(controls) == 3
    for row in controls:
        assert row['raw_exit'] == 0 and row['observed'] == row['expected'] == 3 * row['iterations'] + 5
        assert row['binary_sha256'] == sha(g + f"instructions/loop-{row['iterations']}.bin")
        assert re.findall(r'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)',
                          text(g + f"instructions/loop-{row['iterations']}.stderr")) == [str(row['observed'])]
    coverage = data(g + 'instructions/worker-coverage.json')
    assert coverage['workers'] == 2 and coverage['raw_exit'] == 0
    assert coverage['body_instructions'] == 120000000
    assert 120000000 <= coverage['with_libraries'] <= 122400000
    assert coverage['binary_sha256'] == sha(g + 'instructions/worker-control.bin')
    control_source = Path(__file__).resolve().parents[1] / 'flash-worker-study-20261126/worker_control.c'
    assert coverage['source_sha256'] == hashlib.sha256(control_source.read_bytes()).hexdigest()
    assert re.findall(r'MATHGRAPH_DYNAMIC_INSTRUCTIONS (\d+)',
                      text(g + 'instructions/worker-control.stderr')) == [str(coverage['with_libraries'])]
    native_hashes = {arm: sha(n + 'builds/' + arm + '.bin') for arm in ['baseline', 'strict']}
    native_identity = data(n + 'measurements/identity.json')
    assert native_identity['binary_sha256'] == native_hashes
    assert native_identity['threads'] == 2
    assert native_identity['input'] == {'size': 6326141213, 'sha256': ident['input_sha256']}
    assert len(set(native_hashes.values())) == 2
    native = data(n + 'measurements/rows.json')
    assert len(native) == 4
    for row in native:
        assert row['raw_exit'] == 0 and row['declarations'] == 739167
        tag = n + f"measurements/{row['arm']}-{row['round']}"
        assert re.search(r'checked 739167 declarations', text(tag + '.stdout'), re.I)
        timing = text(tag + '.time').splitlines()[-1].split('\t')
        assert abs(row['cpu_s'] - float(timing[1]) - float(timing[2])) < 1e-6
        assert row['wall_s'] == float(timing[0]) and row['max_rss_kib'] == int(timing[3])
    medians = {arm: {metric: statistics.median(r[metric] for r in native if r['arm'] == arm)
                     for metric in ['cpu_s', 'wall_s', 'max_rss_kib']} for arm in native_hashes}
    values = {r['arm']: r['dynamic_instructions'] for r in counts}
    ratio = values['strict'] / values['baseline']
    report = {
        'state': 'WARRANTED_BOUNDED_240_PRESCRIBED_GENERIC',
        'candidate_commit': qualification['candidate_commit'],
        'candidate_source_tree': qualification['candidate_source_tree'],
        'archive_sha256': a.sha256, 'zip_crc_valid': True,
        'qualification_capsule_sha256': hashlib.sha256(a.qualification.read_bytes()).hexdigest(),
        'official_manifest_sha256': hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
        'counter_identity': counter,
        'generic_binary_sha256': generic_hashes, 'native_binary_sha256': native_hashes,
        'prescribed_correct': 240, 'additional_source_controls': 16,
        'generic_whole_accepts': 2, 'native_whole_accepts': 4,
        'declarations_per_whole_execution': 739167,
        'generic_software_instructions': values, 'generic_instruction_ratio': ratio,
        'generic_instruction_reduction_percent': 100 * (1 - ratio),
        'declared_instruction_priority_gate': 'at least 1% fewer complete-input software instructions',
        'instruction_priority_gate_passed': ratio <= 0.99,
        'native_medians': medians,
        'native_ratios': {metric: medians['strict'][metric] / medians['baseline'][metric]
                          for metric in medians['baseline']},
        'native_paired_cpu_ratios': [next(r['cpu_s'] for r in native if r['arm'] == 'strict' and r['round'] == i) /
                                     next(r['cpu_s'] for r in native if r['arm'] == 'baseline' and r['round'] == i)
                                     for i in [0, 1]],
        'boundary': 'Same frozen generic candidate joins all 230 portable, nine other large and '
                    'complete Mathlib prescribed outcomes. One software-counted complete execution '
                    'per generic arm with two workers, three exact loop controls and a separate '
                    'thread-coverage control. Native builds are separately matched on the measurement '
                    'host in two alternating pairs. Native nine-large compatibility, universal '
                    'soundness, official PMU scores and new Arena rank remain outside this warrant.',
    }
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'independent-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    entries = {}
    for name in names:
        if name.endswith('/'):
            continue
        blob = z.read(name)
        entries[name] = {'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)}
        if not name.endswith(('.bin', '.zip')):
            path = a.out / 'raw' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
    (a.out / 'archive-entries.json').write_text(json.dumps(entries, indent=2) + '\n')
    print(json.dumps(report, indent=2))
