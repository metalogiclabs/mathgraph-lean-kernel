"""Mutate actual untrusted bytes, not already reconstructed declarations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
source = Path('src/checker/inductive/tests.rs').read_text()
raw = re.search(r'const NESTED_EXPORT: &str = r#"(.*?)"#;', source, re.S).group(1)
original = [json.loads(line) for line in raw.splitlines()]
variants = [('original', original, 0)]


def mutate(name, fn):
    rows = copy.deepcopy(original)
    block = next(r['inductive'] for r in rows if r.get('inductive', {}).get('types', [{}])[0].get('name') == 5)
    fn(rows, block)
    variants.append((name, rows, 1))


mutate('missing-field', lambda r,b: b['recs'][0]['rules'][1].update(nfields=0))
mutate('extra-field', lambda r,b: b['recs'][0]['rules'][1].update(nfields=2))
mutate('nullary-extra-field', lambda r,b: b['recs'][0]['rules'][0].update(nfields=1))
mutate('aux-missing-field', lambda r,b: b['recs'][1]['rules'][0].update(nfields=0))
mutate('aux-extra-field', lambda r,b: b['recs'][1]['rules'][0].update(nfields=2))
mutate('constructor-fields', lambda r,b: b['ctors'][1].update(numFields=0))
mutate('constructor-owner', lambda r,b: b['ctors'][1].update(induct=1))
mutate('recursor-params', lambda r,b: b['recs'][0].update(numParams=1))
mutate('recursor-universes', lambda r,b: b['recs'][0].update(levelParams=[]))
mutate('recursor-type', lambda r,b: b['recs'][0].update(type=0))
mutate('recursor-rule-type', lambda r,b: b['recs'][0]['rules'][1].update(rhs=0))
mutate('missing-recursor', lambda r,b: b['recs'].pop())
mutate('duplicate-recursor', lambda r,b: b['recs'].__setitem__(1, copy.deepcopy(b['recs'][0])))
mutate('foreign-recursor', lambda r,b: b['recs'][1].update(name=4))

renamed = copy.deepcopy(original)
for row in renamed:
    if 'str' in row and row['str']['pre'] == 0 and row['str']['str'] in ['C', 'T']:
        row['str']['str'] = 'renamed_' + row['str']['str']
variants.append(('renamed-original', renamed, 0))
results = []
for name, rows, expected in variants:
    data = ('\n'.join(json.dumps(r, separators=(',', ':')) for r in rows) + '\n').encode()
    (a.out / (name + '.ndjson')).write_bytes(data)
    p = subprocess.run([str(a.binary.resolve()), '--stdin', '--threads', '1'], input=data,
        capture_output=True, timeout=20)
    (a.out / (name + '.stdout')).write_bytes(p.stdout)
    (a.out / (name + '.stderr')).write_bytes(p.stderr)
    results.append({'name': name, 'expected': expected, 'observed': p.returncode,
        'sha256': hashlib.sha256(data).hexdigest()})
summary = {'controls': len(results), 'wrong': [r for r in results if r['observed'] != r['expected']],
    'boundary': 'Source correspondence controls; acceptance of altered metadata alone is not a proof of False.'}
(a.out / 'rows.json').write_text(json.dumps(results, indent=2) + '\n')
(a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
if summary['wrong']:
    raise SystemExit(1)
