"""Build isolated factorial arms; never modify source during a build."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parent
bins = Path('/tmp/flash-skip-reuse-binaries')
bins.mkdir(exist_ok=True)
env = dict(os.environ, RUSTUP_HOME='/tmp/flash-rustup', CARGO_HOME='/tmp/flash-cargo',
           CARGO_TARGET_DIR='/dev/shm/flash-skip-reuse-target', CARGO_BUILD_JOBS='1',
           RUSTFLAGS='-C target-cpu=x86-64 -C target-feature=-avx,-avx2,-avx512f,-fma')
identity = json.loads((out / 'source-identity.json').read_text())
def check_source():
    for name, sha in identity['files'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == sha, name

def run(command, log):
    check_source()
    with (out / log).open('wb') as f:
        r = subprocess.run(command, cwd=root, env=env, stdout=f, stderr=subprocess.STDOUT)
    check_source()
    assert r.returncode == 0, (command, log)

cargo = ['/tmp/flash-cargo/bin/cargo']
common = ['--release', '--locked', '--offline', '--manifest-path', str(root / 'Cargo.toml')]
arms = {'combined': 'application-skip,application-reuse', 'skip': 'application-skip',
        'reuse': 'application-reuse', 'baseline': ''}
rows = []
for arm, features in arms.items():
    extra = ['--features', features] if features else []
    print('BUILD_ARM', arm, flush=True)
    if arm != 'combined':
        run(cargo + ['test'] + common + extra + ['--', '--nocapture'], arm + '-tests.log')
    log = (out / (arm + '-tests.log')).read_text()
    assert 'test result: ok. 44 passed; 0 failed' in log
    assert 'test retained_source_regressions ... ok' in log
    mechanisms = [json.loads(x) for x in re.findall(r'APPLICATION_MECHANISM (\{[^\n]+\})', log)]
    assert len(mechanisms) == 15, (arm, len(mechanisms))
    (out / (arm + '-mechanisms.json')).write_text(json.dumps(mechanisms, indent=2) + '\n')
    run(cargo + ['build'] + common + extra, arm + '-build.log')
    binary = bins / (arm + '.bin')
    shutil.copyfile(Path(env['CARGO_TARGET_DIR']) / 'release/sokonanoda', binary)
    binary.chmod(0o555)
    run(['python', 'experiments/flash-upstream-repair-20261126/metadata_controls.py',
         '--binary', str(binary), '--out', str(out / (arm + '-source-controls'))], arm + '-source-controls.log')
    rows.append({'arm': arm, 'features': features, 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                 'library_tests': 44, 'mechanism_rows': len(mechanisms), 'source_controls': 16})
    (out / 'builds.json').write_text(json.dumps(rows, indent=2) + '\n')
    print('FROZEN', json.dumps(rows[-1]), flush=True)
assert len({r['sha256'] for r in rows}) == 4
compiler = subprocess.check_output(['/tmp/flash-cargo/bin/rustc', '-Vv'], env=env, text=True)
(out / 'compiler.txt').write_text(compiler)
(out / 'build-flags.txt').write_text(env['RUSTFLAGS'] + '\n')
print('ALL_FOUR_ARMS_READY', flush=True)
