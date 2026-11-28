"""Train the compiler on the public, SHA-pinned Init export used by nano-lean.

No checker source is imported. The data source and conventional PGO build
approach are credited in README.md. Mathlib is not a training execution.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request

URL = 'https://github.com/sdiehl/nano-lean/releases/download/pgo-data-1/init.ndjson.gz'
GZIP_SHA256 = 'be43e8fc8fa3f9212f6bf005a924834af5cbfdb2ec6b7524fc85efbaf5c6a76e'
CLI = ['--stdin', '--nat-extension', '--string-extension', '--axiom-allow-all']


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--binary', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--raw', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
assert not list(a.raw.glob('*.profraw')), 'host build profiles must not enter checker training'
archive = a.out / 'init.ndjson.gz'
urllib.request.urlretrieve(URL, archive)
assert digest(archive) == GZIP_SHA256
fixture = a.out / 'init.ndjson'
with gzip.open(archive, 'rb') as source, fixture.open('wb') as target:
    for chunk in iter(lambda: source.read(1 << 20), b''):
        target.write(chunk)
        assert target.tell() < 2 * 1024**3, 'unexpected training input size'
rows = []
for threads in [1, 2]:
    with fixture.open('rb') as source:
        result = subprocess.run([str(a.binary.resolve()), *CLI, '--threads', str(threads)],
                                stdin=source, capture_output=True, timeout=240)
    (a.out / f'train-{threads}.stdout').write_bytes(result.stdout)
    (a.out / f'train-{threads}.stderr').write_bytes(result.stderr)
    match = re.search(rb'[Cc]hecked (\d+) declarations', result.stdout)
    row = {'threads': threads, 'raw_exit': result.returncode,
           'declarations': int(match.group(1)) if match else None}
    rows.append(row)
    assert result.returncode == 0 and row['declarations'] and row['declarations'] > 1000, row
assert rows[0]['declarations'] == rows[1]['declarations']
record = {
    'source': 'bc704eebed4e009bc66af1a849f18315c11f1926',
    'source_tree': '06c257f0f2ff1f64711cfa54620b650e6dd59b7e',
    'data_url': URL, 'gzip_sha256': GZIP_SHA256,
    'input_size': fixture.stat().st_size, 'input_sha256': digest(fixture),
    'generator_binary_sha256': digest(a.binary), 'executions': rows,
    'raw_profiles': {f.name: {'sha256': digest(f), 'bytes': f.stat().st_size}
                     for f in sorted(a.raw.glob('*.profraw'))},
    'boundary': 'Compiler training on a fixed Init export. Init overlaps the mathematical '
                'foundation of Mathlib. Mathlib itself is not run for training; this is '
                'not a claim of out-of-distribution generalization or an Arena score.',
}
assert record['raw_profiles'], 'training produced no profiles'
(a.out / 'identity.json').write_text(json.dumps(record, indent=2) + '\n')
fixture.unlink()
print(json.dumps(record), flush=True)
