"""Raw-verdict, exact-input qualification of the attributed upstream experiment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('mode', choices=['portable', 'prefix'])
p.add_argument('--binary', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--results', type=Path)
p.add_argument('--fixtures', type=Path)
p.add_argument('--prefix', type=Path)
p.add_argument('--flash', type=Path)
p.add_argument('--upstream', type=Path)
p.add_argument('--valgrind', default='valgrind')
p.add_argument('--rounds', type=int, default=2)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
a.out = a.out.resolve()
args = ['--stdin', '--threads', '2', '--nat-extension', '--string-extension', '--axiom-allow-all']
rows = []
if a.mode == 'portable':
    manifest = json.loads(a.results.read_text())
    tests = [t for t in manifest['tests'] if t['outcome'] in ['accept', 'reject'] and t['size'] <= 10 * 1024**2]
    assert len(tests) == 230
    save(a.out / 'identity.json', {'binary_sha256': digest(a.binary), 'arena': manifest['meta'],
        'threads': 2, 'boundary': 'All 230 exact portable prescribed inputs; ten large inputs are outside this run.'})
    for t in sorted(tests, key=lambda t: t['name']):
        fixture = a.fixtures / (t['name'] + '.ndjson')
        assert fixture.stat().st_size == t['size'] and digest(fixture) == t['sha256'], t['name']
        tag = t['name'].replace('/', '_')
        start = time.monotonic()
        with fixture.open('rb') as inp:
            try:
                r = subprocess.run([str(a.binary.resolve())] + args, stdin=inp,
                    capture_output=True, timeout=t.get('timeout', 180))
                code, stdout, stderr = r.returncode, r.stdout, r.stderr
            except subprocess.TimeoutExpired as e:
                code, stdout, stderr = 'TIMEOUT', e.stdout or b'', e.stderr or b''
        (a.out / (tag + '.stdout')).write_bytes(stdout)
        (a.out / (tag + '.stderr')).write_bytes(stderr)
        row = {'name': t['name'], 'expected': 0 if t['outcome'] == 'accept' else 1,
            'observed': code, 'sha256': t['sha256'], 'elapsed_s': time.monotonic() - start}
        rows.append(row)
        save(a.out / 'rows.json', rows)
        if code != row['expected']:
            print('UNRESOLVED', json.dumps(row), stderr.decode(errors='replace')[-400:], flush=True)
    summary = {'attempted': len(rows), 'correct': sum(r['expected'] == r['observed'] for r in rows),
        'wrong_or_unavailable': [r for r in rows if r['expected'] != r['observed']]}
else:
    assert a.prefix.stat().st_size == 134232002
    assert digest(a.prefix) == 'c3d1e08032bbfe2dbfc4c8a84fd711ba83296a47d7468d9ce15988efa4acfa3a'
    binaries = {'flash': a.flash.resolve(), 'upstream': a.upstream.resolve(), 'strict': a.binary.resolve()}
    hashes = {n: digest(b) for n, b in binaries.items()}
    assert len(set(hashes.values())) == len(hashes), 'Duplicate executables invalidate comparison'
    cfg = a.out / 'flash-config.json'
    save(cfg, {'use_stdin': True, 'num_threads': 2, 'nat_extension': True, 'string_extension': True,
        'unsafe_permit_all_axioms': True, 'unpermitted_axiom_hard_error': False, 'print_success_message': True})
    save(a.out / 'identity.json', {'binary_sha256': hashes, 'input_sha256': digest(a.prefix),
        'threads': 2, 'boundary': 'Fixed 25131-declaration prefix; software guest instructions, not full Mathlib or an Arena score.'})
    for round_no in range(a.rounds):
        names = list(binaries)
        for name in names if round_no % 2 == 0 else reversed(names):
            tag = f'{name}-{round_no}'
            profile = a.out / (tag + '.cachegrind')
            cmd = [a.valgrind, '--tool=cachegrind', '--cache-sim=no', '--branch-sim=no',
                '--cachegrind-out-file=' + str(profile), str(binaries[name])]
            cmd += [str(cfg)] if name == 'flash' else args
            start = time.monotonic()
            with a.prefix.open('rb') as inp:
                r = subprocess.run(cmd, stdin=inp, capture_output=True, timeout=180)
            (a.out / (tag + '.stdout')).write_bytes(r.stdout)
            (a.out / (tag + '.stderr')).write_bytes(r.stderr)
            hits = re.findall(r'^summary:\s*(\d+)', profile.read_text(), re.M) if profile.exists() else []
            row = {'arm': name, 'round': round_no, 'observed': r.returncode,
                'count_checked': bool(re.search(rb'[Cc]hecked 25131 declarations', r.stdout)),
                'guest_Ir': int(hits[-1]) if hits else None, 'elapsed_s': time.monotonic() - start}
            rows.append(row)
            save(a.out / 'rows.json', rows)
            print(json.dumps(row), flush=True)
    wrong = [r for r in rows if r['observed'] != 0 or not r['count_checked'] or r['guest_Ir'] is None]
    summary = {'observations': len(rows), 'wrong_or_unavailable': wrong,
        'boundary': 'Exact source-derived prefix only; no Arena performance claim.'}
    if not wrong:
        totals = {n: sum(r['guest_Ir'] for r in rows if r['arm'] == n) for n in binaries}
        summary['ratios_to_flash'] = {n: v / totals['flash'] for n, v in totals.items()}
save(a.out / 'summary.json', summary)
print('SUMMARY', json.dumps(summary), flush=True)
if summary['wrong_or_unavailable']:
    raise SystemExit(1)
