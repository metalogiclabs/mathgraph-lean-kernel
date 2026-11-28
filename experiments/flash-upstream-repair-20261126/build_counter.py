"""Build the isolated diagnostic against a hash-pinned public DynamoRIO release."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request

root = Path(os.environ['RUNNER_TEMP']) / 'flash-dynamorio'
root.mkdir(exist_ok=True)
archive = root / 'release.tar.gz'
url = 'https://github.com/DynamoRIO/dynamorio/releases/download/cronbuild-11.92.20777/DynamoRIO-Linux-11.92.20777.tar.gz'
with urllib.request.urlopen(url) as response, archive.open('wb') as output:
    for b in iter(lambda: response.read(1024 * 1024), b''):
        output.write(b)
expected = '3958421d74964ea2a30b43752560ae584d854ceb6209946dd2d9e173352d7a2c'
h = hashlib.sha256()
with archive.open('rb') as f:
    for b in iter(lambda: f.read(1024 * 1024), b''):
        h.update(b)
assert h.hexdigest() == expected
name = 'DynamoRIO-Linux-11.92.20777'
parts = ('bin64/', 'lib64/', 'ext/lib64/release/', 'ext/include/', 'include/')
with tarfile.open(archive) as tar:
    members = [m for m in tar if any(m.name.startswith(name + '/' + p) for p in parts)]
    tar.extractall(root, members=members, filter='data')
package = root / name
source = Path('experiments/flash-upstream-repair-20261126/instruction_counter.c').resolve()
binary = root / 'instruction-counter.so'
libraries = [package / 'lib64/release', package / 'ext/lib64/release']
command = ['gcc', '-shared', '-fPIC', '-O3', '-fno-stack-protector', '-DX86_64', '-DLINUX',
    '-I' + str(package / 'include'), '-I' + str(package / 'ext/include'), str(source)]
for lib in libraries:
    command += ['-L' + str(lib), '-Wl,-rpath,' + str(lib)]
command += ['-ldrx', '-ldrreg', '-ldrmgr', '-ldynamorio', '-o', str(binary)]
subprocess.run(command, check=True)
(root / 'identity.json').write_text(json.dumps({'release_url': url, 'archive_sha256': expected,
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'client_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'compiler_command': command}, indent=2) + '\n')
