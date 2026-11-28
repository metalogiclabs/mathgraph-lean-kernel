"""Compare native bc704eeb against its 512-declaration batch candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--binaries', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)


def save(name, value):
    (a.out / name).write_text(json.dumps(value, indent=2) + '\n')


identity = {'size': a.fixture.stat().st_size, 'sha256': digest(a.fixture)}
assert identity == {'size': 6326141213,
                    'sha256': 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'}
bins = {n: (a.binaries / (n + '.bin')).resolve() for n in ['baseline', 'strict']}
hashes = {n: digest(b) for n, b in bins.items()}
assert len(set(hashes.values())) == 2, 'duplicate executables invalidate the comparison'
save('identity.json', {'input': identity, 'binary_sha256': hashes, 'threads': 2,
                      'baseline': 'bc704eeb, 64-declaration batches, target-cpu=native',
                      'strict': '4816054e, 512-declaration batches, target-cpu=native',
                      'boundary': 'Matched complete-input native CPU/RSS diagnostic; no Arena rank.'})
rows = []
for round_no in range(2):
    for name in (['baseline', 'strict'] if round_no == 0 else ['strict', 'baseline']):
        tag = f'{name}-{round_no}'
        timing = a.out / (tag + '.time')
        command = ['/usr/bin/time', '-f', '%e\t%U\t%S\t%M', '-o', str(timing),
                   str(bins[name]), '--stdin', '--threads', '2', '--nat-extension',
                   '--string-extension', '--axiom-allow-all']
        with a.fixture.open('rb') as source, (a.out / (tag + '.stdout')).open('wb') as out, \
                (a.out / (tag + '.stderr')).open('wb') as err:
            result = subprocess.run(command, stdin=source, stdout=out, stderr=err, timeout=600)
        match = re.search(rb'[Cc]hecked (\d+) declarations', (a.out / (tag + '.stdout')).read_bytes())
        row = {'arm': name, 'round': round_no, 'raw_exit': result.returncode,
               'declarations': int(match.group(1)) if match else None}
        fields = timing.read_text().splitlines()[-1].split('\t')
        if len(fields) == 4:
            row.update(wall_s=float(fields[0]), cpu_s=float(fields[1]) + float(fields[2]),
                       max_rss_kib=int(fields[3]))
        rows.append(row)
        save('rows.json', rows)
        print(json.dumps(row), flush=True)
        assert row['raw_exit'] == 0 and row['declarations'] == 739167, row
        assert {n: digest(b) for n, b in bins.items()} == hashes, 'executable changed during measurement'
medians = {n: {metric: statistics.median(r[metric] for r in rows if r['arm'] == n)
               for metric in ['cpu_s', 'wall_s', 'max_rss_kib']} for n in bins}
save('summary.json', {'state': 'WARRANTED_BOUNDED_FULL_MATHLIB_ACCEPT', 'observations': 4,
                      'medians': medians,
                      'chunk512_to_baseline_cpu_ratio': medians['strict']['cpu_s'] / medians['baseline']['cpu_s'],
                      'boundary': 'Exact complete Mathlib, two alternating native pairs. This '
                                  'isolates scheduling batch size, not an Arena hardware score.'})
