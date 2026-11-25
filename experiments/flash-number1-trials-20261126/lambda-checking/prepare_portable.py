"""Recover all portable input bytes; verify each against the current manifest."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import zipfile

out = Path(os.environ['RUNNER_TEMP']) / 'lambda-portable-inputs'
out.mkdir(parents=True, exist_ok=True)
manifest = json.loads(Path('experiments/flash-number1-trials-20261126/portable-manifest.json').read_text())
tests = {t['name']: t for t in manifest['tests']}
assert len(tests) == 230
archive = out / 'inputs.zip'
with archive.open('wb') as f:
    subprocess.run(['gh', 'api', 'repos/leanprover/lean-kernel-arena/actions/artifacts/14842971830/zip'], stdout=f, check=True)
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '4d33cfdd5754e9ebc06b546a3cc4ae41c8e3d0a1624b48ad4ba2ac6aeafb76ec'
tar = out / 'inputs.tar.gz'
with zipfile.ZipFile(archive) as z:
    names = [n for n in z.namelist() if n.endswith('/lean-arena-tests.tar.gz') or n == 'lean-arena-tests.tar.gz']
    assert len(names) == 1
    tar.write_bytes(z.read(names[0]))
seen = set()
with tarfile.open(tar) as t:
    for m in t:
        if not m.isfile():
            continue
        parts = Path(m.name).parts
        assert len(parts) >= 2 and parts[0] in ('good', 'bad') and m.name.endswith('.ndjson')
        assert all(p not in ('', '.', '..') for p in parts)
        name = '/'.join(parts[1:])[:-7]
        assert name in tests and name not in seen
        data = t.extractfile(m).read()
        meta = tests[name]
        assert len(data) == meta['size'] and hashlib.sha256(data).hexdigest() == meta['sha256'], name
        assert meta['outcome'] == ('accept' if parts[0] == 'good' else 'reject')
        path = out / 'fixtures' / (name + '.ndjson')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        seen.add(name)
assert seen == tests.keys()
print('Verified all', len(seen), 'portable inputs against official run 45581042122')
