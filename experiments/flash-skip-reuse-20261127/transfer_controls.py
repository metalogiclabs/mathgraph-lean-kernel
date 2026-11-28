"""Exact small-corpus transfer and valid-to-invalid warmed-context controls."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parent / 'transfer'
out.mkdir(exist_ok=True)
manifest = json.loads((root / 'experiments/flash-upstream-repair-20261126/official-inputs.json').read_text())
tests = [t for t in manifest['tests'] if t['outcome'] in ['accept', 'reject']
         and t['size'] <= 512 * 1024 and
         (t['name'].startswith(('bugs/', 'tutorial/')) or
          t['name'] in ['perf/let-fold', 'perf/let-ladder', 'perf/proj-app-lazy-delta',
                        'perf/proj-applied-struct', 'perf/proj-applied-struct-arg-bad',
                        'perf/proj-applied-struct-bad'])]
fixtures = Path('/tmp/flash-early-fixtures')
cases = []
for t in tests:
    p = fixtures / (t['name'] + '.ndjson')
    data = p.read_bytes()
    assert len(data) == t['size'] and hashlib.sha256(data).hexdigest() == t['sha256']
    cases.append((t['name'], data, 0 if t['outcome'] == 'accept' else 1))

meta = {'meta': {'exporter': {'name': 'lean4export', 'version': '3.1.0'},
        'format': {'version': '3.1.0'}, 'lean': {'githash': 'generated', 'version': '4.35.0'}}}
prefix = [meta] + [{'in': n, 'str': {'pre': 0, 'str': s}} for n, s in [(1, 'A'), (2, 'B'), (3, 'u')]]
prefix += [{'il': 1, 'param': 3}, {'ie': 0, 'sort': 1},
           {'ie': 1, 'forallE': {'binderInfo': 'default', 'body': 0, 'name': 0, 'type': 0}},
           {'ie': 2, 'bvar': 0}, {'ie': 3, 'lam': {'binderInfo': 'default', 'body': 2, 'name': 0, 'type': 0}}]
def declaration(name, params):
    return {'def': {'all': [name], 'hints': {'regular': 1}, 'levelParams': params,
                    'name': name, 'safety': 'safe', 'type': 1, 'value': 3}}
for name, declarations, expected in [
        ('scope-cold-invalid', [declaration(2, [])], 1),
        ('scope-warm-valid', [declaration(1, [3]), declaration(2, [3])], 0),
        ('scope-warm-invalid', [declaration(1, [3]), declaration(2, [])], 1)]:
    data = ('\n'.join(json.dumps(r, separators=(',', ':')) for r in prefix + declarations) + '\n').encode()
    (out / (name + '.ndjson')).write_bytes(data)
    cases.append((name, data, expected))
rows = []
for arm in ['baseline', 'skip', 'reuse', 'combined']:
    binary = Path('/tmp/flash-skip-reuse-binaries') / (arm + '.bin')
    binary_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    logs = out / arm; logs.mkdir(exist_ok=True)
    for name, data, expected in cases:
        r = subprocess.run([str(binary), '--stdin', '--threads', '1', '--nat-extension',
                            '--string-extension', '--axiom-allow-all'], input=data,
                           capture_output=True, timeout=30)
        tag = name.replace('/', '_')
        (logs / (tag + '.stdout')).write_bytes(r.stdout)
        (logs / (tag + '.stderr')).write_bytes(r.stderr)
        row = {'arm': arm, 'name': name, 'expected': expected, 'observed': r.returncode,
               'input_sha256': hashlib.sha256(data).hexdigest(), 'binary_sha256': binary_sha}
        rows.append(row)
        if r.returncode != expected:
            (out / 'rows.json').write_text(json.dumps(rows, indent=2) + '\n')
            print('UNRESOLVED', json.dumps(row), r.stderr[-500:].decode(errors='replace'), flush=True)
    print('TRANSFER_DONE', arm, len(cases), flush=True)
(out / 'rows.json').write_text(json.dumps(rows, indent=2) + '\n')
(out / 'summary.json').write_text(json.dumps({'cases_per_arm': len(cases), 'official_cases_per_arm': len(tests),
    'warm_context_cases_per_arm': 3, 'observations': len(rows),
    'wrong_or_unavailable': [r for r in rows if r['observed'] != r['expected']],
    'boundary': 'Prespecified exact original cases at most 512 KiB plus three generated warmed-universe controls. All raw statuses retained. Not the full 230 or 240 qualification.'}, indent=2) + '\n')
if any(r['observed'] != r['expected'] for r in rows):
    raise SystemExit(1)
