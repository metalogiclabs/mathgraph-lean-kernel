"""Rejoin downloaded official PR receipts to their own input-stat manifest.

Run from this directory after extracting artifacts 15072279691 and 15073935467.
This verifies retained execution receipts; it does not rerun the checker.
"""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
ARCHIVES = {
    'results-mathgraph.zip': '11004c4cfc01d1739abda85a00a151feb0207db828aa9573bea8f6fbc34fa841',
    'test-stats.zip': 'e74c50f10e93ed831b7919a20c3d5f40bf52fcac9e11c646c14784f534d702b8',
}

for name, expected in ARCHIVES.items():
    archive = ROOT / name
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected, name
    with zipfile.ZipFile(archive) as contents:
        assert contents.testzip() is None, name

files = sorted((ROOT / 'raw/_results').glob('*.json'))
stats_files = sorted((ROOT / 'test-stats').rglob('*.stats.json'))
rows = [json.loads(f.read_text()) for f in files]
stats = {r['name']: r for f in stats_files if (r := json.loads(f.read_text()))}
assert len(rows) == len({r['test'] for r in rows}) == len(stats) == 261
assert set(stats) == {r['test'] for r in rows}
assert {r['github_run_id'] for r in rows} == {'45722992953'}
assert {r['checker_hash'] for r in rows} == {'0f962fa70d5f55ad'}
prescribed, policy = [], []
compact = []
for row in rows:
    stat = stats[row['test']]
    outcome = stat['outcome']
    assert len(stat['sha256']) == 64 and stat['size'] > 0
    if outcome in ('accept', 'reject'):
        expected_code = 0 if outcome == 'accept' else 1
        assert row['exit_code'] == expected_code, row['test']
        assert row['status'] == ('accepted' if outcome == 'accept' else 'rejected')
        assert row['correctness'] == 'correct'
        prescribed.append(row)
    else:
        assert outcome == 'either', (row['test'], outcome)
        assert row['correctness'] in ('either', 'error')
        if row['status'] == 'timeout':
            assert row['exit_code'] == -9 and row['correctness'] == 'error'
        else:
            assert (row['status'], row['exit_code']) in [('accepted', 0), ('rejected', 1)]
            assert row['correctness'] == 'either'
        policy.append(row)
    compact.append({
        **{k: row[k] for k in ('test', 'status', 'correctness', 'exit_code',
                             'test_hash', 'checker_hash', 'instructions',
                             'wall_time', 'cpu_time', 'max_rss', 'github_run_id')},
        'expected': outcome, 'input_sha256': stat['sha256'], 'input_size': stat['size'],
    })

assert len(prescribed) == 231 and len(policy) == 30
assert sum(r['exit_code'] == 0 for r in prescribed) == 139
assert sum(r['exit_code'] == 1 for r in prescribed) == 92
timeouts = [r for r in policy if r['status'] == 'timeout']
assert len(timeouts) == 2
assert 'mathlib' not in stats
record = {
    'status': 'WARRANTED_BOUNDED',
    'repository': 'leanprover/lean-kernel-arena', 'pull_request': 398,
    'pull_request_head': '23003362b3c48487f03afa72e4390a05c3ca8ead',
    'run_id': 45722992953, 'job_id': 139586219550,
    'artifacts': {'results': 15072279691, 'test_stats': 15073935467},
    'archive_sha256': ARCHIVES, 'archive_crc_valid': True,
    'raw_result_entries': len(rows), 'input_stat_entries': len(stats),
    'prescribed': {'correct': 231, 'accept': 139, 'reject': 92},
    'policy': {'total': 30, 'decisions': 28,
               'timeouts': [{k: r[k] for k in ('test', 'status', 'correctness', 'exit_code')}
                            for r in timeouts]},
    'checker_hash': '0f962fa70d5f55ad',
    'boundary': 'Independent verification of archive identities, CRC, retained receipt digests '
                'and the join of raw outcomes to their own input-stat manifest. This is not '
                'a checker rerun. Official PR CI omits Mathlib and other large exports. The '
                'overlapping 231 current PR outcomes and previous 230 portable/240 exact '
                'cases must not be added. No new rank or full-input hardware score.',
}
(ROOT / 'independent-verification.json').write_text(json.dumps(record, indent=2) + '\n')
(ROOT / 'verdicts.json').write_text(json.dumps(compact, indent=2) + '\n')
(ROOT / 'raw-entry-sha256.json').write_text(json.dumps({
    str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
    for f in files + stats_files
}, indent=2) + '\n')
print(json.dumps(record, indent=2))
