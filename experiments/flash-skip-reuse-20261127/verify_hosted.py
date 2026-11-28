"""Rehash hosted archives and independently check exact source/corpus records."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--specs', type=Path, required=True)
p.add_argument('--archives', type=Path, default=Path('/tmp'))
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[2]
manifest = json.loads((root / 'experiments/flash-upstream-repair-20261126/official-inputs.json').read_text())
tests = {t['name']: t for t in manifest['tests'] if t['outcome'] in ['accept', 'reject'] and t['size'] <= 10*1024**2}
assert len(tests) == 230
features = {'baseline': '', 'skip': 'application-skip', 'reuse': 'application-reuse',
            'combined': 'application-skip,application-reuse'}
specs = json.loads(a.specs.read_text())
results = []
for s in specs:
    arm = s['arm']
    archive = a.archives / ('flash-sr-' + arm + '.zip')
    assert archive.stat().st_size == s['size']
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == s['sha256']
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert z.read('harness-commit.txt').decode().strip() == '35c6a8155c05ab0b0bbf81179eadf169818e556a'
        assert z.read('source-tree.txt').decode().strip() == '226b487d65fe0d19ad25f9d1aa721ab710f4458a'
        assert z.read('features.txt').decode().strip() == features[arm]
        assert z.read('prototype.patch') == Path(__file__).with_name('prototype.patch').read_bytes()
        binary_sha = hashlib.sha256(z.read('checker.bin')).hexdigest()
        assert z.read('executable.sha256').decode().split()[0] == binary_sha
        tests_log = z.read('tests.log').decode()
        assert 'test result: ok. 44 passed; 0 failed' in tests_log
        assert 'test retained_source_regressions ... ok' in tests_log
        rows = json.loads(z.read('portable/rows.json'))
        assert len(rows) == len({r['name'] for r in rows}) == 230
        assert {r['name'] for r in rows} == set(tests)
        for r in rows:
            t = tests[r['name']]
            assert r['sha256'] == t['sha256']
            assert r['expected'] == r['observed'] == (0 if t['outcome'] == 'accept' else 1)
        metadata = json.loads(z.read('source-controls/summary.json'))
        assert metadata['controls'] == 16 and not metadata['wrong']
        mechanisms = [json.loads(x) for x in re.findall(r'APPLICATION_MECHANISM (\{[^\n]+\})', tests_log)]
        assert len(mechanisms) == 15
        dest = a.out / arm
        keep = ['tests.log', 'build.log', 'compiler.txt', 'build-flags.txt', 'features.txt',
                'source-tree.txt', 'harness-commit.txt', 'executable.sha256',
                'portable/rows.json', 'portable/summary.json', 'portable/identity.json',
                'source-controls/rows.json', 'source-controls/summary.json']
        for name in keep:
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
        (dest / 'mechanisms.json').write_text(json.dumps(mechanisms, indent=2) + '\n')
        results.append({'arm': arm, 'artifact_id': s['id'], 'archive_sha256': s['sha256'],
                        'crc_entries': len(z.namelist()), 'binary_sha256': binary_sha,
                        'portable_correct': len(rows), 'library_tests': 44, 'source_controls': 16})
summary = {'run_id': 45881611501, 'verified_arms': results,
           'all_four_qualified': len(results) == 4,
           'boundary': 'Independent archive/executable hashes and exact corpus/source records. Portable qualification only, not full 240 or Arena performance.'}
(a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary), flush=True)
