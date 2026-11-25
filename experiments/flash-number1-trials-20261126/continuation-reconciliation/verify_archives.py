"""Independently verify retained Flash execution archives, without rerunning the kernel.

Usage: python verify_archives.py --native ZIP --census ZIP --large-root DIR
DIR contains <artifact-id>/artifact.zip. --manifest is the official-inputs.json
from bc704eebed4e009bc66af1a849f18315c11f1926. No benchmark is inferred from
green job status. Source-qualified large builds are not identical executables.
"""
import argparse
import hashlib
import json
import re
import statistics
import zipfile
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive(path, expected):
    assert digest(path.read_bytes()) == expected, path
    result = zipfile.ZipFile(path)
    assert result.testzip() is None, path
    return result


def data(z, name):
    return json.loads(z.read(name))


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--native', type=Path, required=True)
p.add_argument('--census', type=Path, required=True)
p.add_argument('--large-root', type=Path, required=True)
p.add_argument('--manifest', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
here = Path(__file__).resolve().parent
authorities = json.loads((here / 'archive-authorities.json').read_text())
manifest_bytes = a.manifest.read_bytes()
assert hashlib.sha1(b'blob ' + str(len(manifest_bytes)).encode() + b'\0' + manifest_bytes).hexdigest() == 'a17f96ff3f5c6cb3acabedd1b4ddf76aefc14424'
manifest = json.loads(manifest_bytes)
tests = {t['name']: t for t in manifest['tests'] if t['outcome'] in ('accept', 'reject')}
assert len(tests) == 240
accepted = set()
with archive(a.native, authorities['native']['sha256']) as z:
    assert z.read('commit.txt').decode().strip() == 'bc704eebed4e009bc66af1a849f18315c11f1926'
    ids = data(z, 'binary-identities.json')
    for name, expected in ids.items():
        assert digest(z.read(f'builds/{name}.bin')) == expected
    assert len(set(ids.values())) == 2
    inp = data(z, 'input.json')
    assert inp['sha256'] == tests['mathlib']['sha256'] and inp['size'] == tests['mathlib']['size']
    rows = data(z, 'mathlib/rows.json')
    assert {(r['arm'], r['round']) for r in rows} == {('baseline', 0), ('baseline', 1), ('strict', 0), ('strict', 1)}
    assert len(rows) == 4
    for r in rows:
        assert r['observed'] == 0 and r['declarations'] == 739167
        tag = f"mathlib/{r['arm']}-{r['round']}"
        assert b'739167 declarations' in z.read(tag + '.stdout')
        assert not z.read(tag + '.stderr').strip()
    medians = {n: statistics.median(r['cpu_s'] for r in rows if r['arm'] == n) for n in ids}
    cpu_ratio = medians['strict'] / medians['baseline']
    rss_ratio = max(r['max_rss_kb'] for r in rows if r['arm'] == 'strict') / max(r['max_rss_kb'] for r in rows if r['arm'] == 'baseline')
    portable = data(z, 'portable/rows.json')
    assert len(portable) == len({r['name'] for r in portable}) == 230
    for r in portable:
        t = tests[r['name']]
        assert r['sha256'] == t['sha256']
        assert r['expected'] == r['observed'] == (0 if t['outcome'] == 'accept' else 1)
        accepted.add(r['name'])
    controls = data(z, 'source-controls/rows.json')
    assert len(controls) == 16 and all(r['expected'] == r['observed'] for r in controls)
    accepted.add('mathlib')
large_rows = []
for auth in authorities['large']:
    with archive(a.large_root / str(auth['id']) / 'artifact.zip', auth['sha256']) as z:
        v = data(z, 'verdict.json')
        inp = data(z, 'input.json')
        t = tests[v['name']]
        assert t['outcome'] == 'accept' and v['raw_exit'] == 0
        assert t['sha256'] == inp['sha256'] == v['input_sha256']
        assert t['size'] == inp['size']
        assert z.read('source-tree.txt').decode().strip() == '06c257f0f2ff1f64711cfa54620b650e6dd59b7e'
        assert z.read('commit.txt').decode().strip() == auth['commit']
        assert z.read('binary.txt').decode().split()[0] == v['binary_sha256']
        assert z.read('compiler.txt').decode().startswith('rustc 1.99.1 ')
        assert z.read('build-flags.txt').decode().strip() == '-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma'
        assert re.search(rb'checked ' + str(v['checked_declarations']).encode() + rb' declarations', z.read('stdout.txt'))
        assert not z.read('stderr.txt').strip()
        assert v['name'] not in accepted
        accepted.add(v['name'])
        large_rows.append(v)
missing = sorted(set(tests) - accepted)
assert missing == ['navier-stokes-euler']
census_rounds = []
top_sets = []
with archive(a.census, authorities['census']['sha256']) as z:
    assert z.read('source-tree.txt').decode().strip() == 'deb3a3356a3b7ec6dd00c607dc56ecdc419ab4e1'
    for n in (0, 1):
        x = data(z, f'round-{n}-census.json')
        assert x['declarations'] == len(x['rows']) == 739167
        assert {r[0] for r in x['rows']} == set(range(739167))
        total = sum(r[1] for r in x['rows'])
        assert total == x['total_declaration_elapsed_ns']
        costs = sorted((r[1] for r in x['rows']), reverse=True)
        for c in x['cumulative']:
            assert sum(costs[:c['top_n']]) == c['elapsed_ns']
        result = data(z, f'round-{n}-result.json')
        assert result['raw_exit'] == 0 and result['diagnostic_stop'] is None
        top_sets.append({r[0] for r in x['rows'][:100]})
        census_rounds.append({'round': n, 'declarations': len(x['rows']), 'elapsed_s': result['elapsed_s'], 'top100_share': sum(costs[:100]) / total, 'top1000_share': sum(costs[:1000]) / total})
report = {
    'state': 'WARRANTED_BOUNDED_EXECUTION_EVIDENCE',
    'source_commit': 'bc704eebed4e009bc66af1a849f18315c11f1926',
    'source_tree': '06c257f0f2ff1f64711cfa54620b650e6dd59b7e',
    'qualified_prescribed_outcomes': len(accepted),
    'missing': missing,
    'source_integrity_controls': len(controls),
    'native': {'observations': 4, 'declarations_each': 739167, 'binary_sha256': ids, 'cpu_medians_s': medians, 'cpu_ratio': cpu_ratio, 'peak_rss_ratio': rss_ratio},
    'large_inputs': large_rows,
    'old_core_declaration_census': {'rounds': census_rounds, 'top100_overlap': len(top_sets[0] & top_sets[1])},
    'boundaries': [
        'CPU and peak RSS are two alternating native observations per arm, not an Arena instruction measurement or statistical generalization.',
        'Portable and native evidence uses the frozen strict binary. Large jobs rebuild identical source with generic flags; their executable hashes differ and are retained.',
        'Complete input hashes are execution-record attestations; archives do not include all giant input bytes.',
        'Declaration costs are instrumented elapsed time on the old core, excluding parsing and session maintenance. They are not the new core profile.',
        'Navier-Stokes/Euler and official rank improvement remain UNKNOWN.'
    ]
}
a.out.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'qualified': len(accepted), 'missing': missing, 'cpu_ratio': cpu_ratio, 'peak_rss_ratio': rss_ratio, 'census_rounds': census_rounds, 'top100_overlap': report['old_core_declaration_census']['top100_overlap']}, indent=2))
