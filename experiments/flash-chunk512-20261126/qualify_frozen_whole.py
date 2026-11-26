"""Finish the frozen generic candidate's last prescribed correctness case.

This separates qualification from the slower software-counting instrument.
It establishes one exact-input verdict, not a cost improvement or rank.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive', type=Path, required=True)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
archive_hash = hashlib.sha256(a.archive.read_bytes()).hexdigest()
assert archive_hash == '636eb10905014d9062d4ab5eaf1569a14c76b6d60fb5e507bebe46de401fdb17'
with zipfile.ZipFile(a.archive) as z:
    assert z.testzip() is None
    identity = json.loads(z.read('identity.json'))
    binary_bytes = z.read('builds/strict.bin')
    assert identity['candidate_commit'] == '4816054e2331c3cd6b57cbcd51d3e265b48c68e7'
    assert identity['candidate_source_tree'] == 'fa9f0de20650f28f63f1d01d7dab50397e167bcf'
    assert hashlib.sha256(binary_bytes).hexdigest() == identity['candidate_binary_sha256'] == \
        '878d871f79bcf71ee1de3f131708ff31553fb130ea69b52f30be186fd414d553'
h = hashlib.sha256()
with a.fixture.open('rb') as source:
    for chunk in iter(lambda: source.read(1 << 20), b''):
        h.update(chunk)
assert a.fixture.stat().st_size == 6326141213
assert h.hexdigest() == 'f749dfd084fc0727d107c7aaded7d492cebfc0b517cfaa7337d8a7578a6c0dec'
binary = (a.out / 'checker.bin').resolve()
binary.write_bytes(binary_bytes)
binary.chmod(0o755)
identity.update(archive_sha256=archive_hash, input_sha256=h.hexdigest(),
                input_bytes=a.fixture.stat().st_size, threads=2,
                boundary='One direct frozen-generic Mathlib verdict; no instruction measurement or rank.')
(a.out / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
argv = [str(binary), '--stdin', '--threads', '2', '--nat-extension',
        '--string-extension', '--axiom-allow-all']
before = time.monotonic()
with a.fixture.open('rb') as source:
    r = subprocess.run(argv, stdin=source, capture_output=True, timeout=1200)
(a.out / 'stdout.txt').write_bytes(r.stdout)
(a.out / 'stderr.txt').write_bytes(r.stderr)
match = re.search(rb'[Cc]hecked (\d+) declarations', r.stdout)
result = {'state': 'OBSERVED', 'raw_exit': r.returncode,
          'checked_declarations': int(match[1]) if match else None,
          'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
          'threads': 2, 'elapsed_s': time.monotonic() - before,
          'input_sha256': h.hexdigest(), 'archive_sha256': archive_hash}
(a.out / 'verdict.json').write_text(json.dumps(result, indent=2) + '\n')
assert result['raw_exit'] == 0 and result['checked_declarations'] == 739167
assert result['binary_sha256'] == identity['candidate_binary_sha256']
print(json.dumps(result), flush=True)
