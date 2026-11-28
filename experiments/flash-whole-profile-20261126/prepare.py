"""Build an exclusive-symbol counter for the frozen, already-qualified binary."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--sdk', type=Path, required=True)
p.add_argument('--binary', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.sdk = a.sdk.resolve()
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=True)
assert hashlib.sha256(a.binary.read_bytes()).hexdigest() == '09fe7ecf7421be7ad7f7c57596c214bcd6e7c0d912d6d555cb5749b17202bd5b'
raw = subprocess.check_output(['nm', '-S', '--demangle', '--numeric-sort', '--defined-only', str(a.binary)], text=True)
(a.out / 'symbols.nm').write_text(raw)
by_start = {}
for line in raw.splitlines():
    m = re.match(r'^([0-9a-f]+) ([0-9a-f]+) ([tTwW]) (.+)$', line)
    if not m:
        continue
    lo, size, _, name = m.groups()
    lo, size = int(lo, 16), int(size, 16)
    if size:
        row = {'lo': lo, 'hi': lo + size, 'name': name}
        if lo not in by_start or size > by_start[lo]['hi'] - lo:
            by_start[lo] = row
symbols = sorted(by_start.values(), key=lambda r: r['lo'])
assert symbols and all(x['hi'] <= y['lo'] for x, y in zip(symbols, symbols[1:])), 'Overlapping sized text symbols require explicit resolution'
loads = subprocess.check_output(['readelf', '-lW', str(a.binary)], text=True)
base = min(int(line.split()[2], 16) for line in loads.splitlines() if line.strip().startswith('LOAD '))
header = '#define IMAGE_BASE ' + str(base) + 'ULL\n#define SYMBOL_COUNT ' + str(len(symbols)) + '\n'
header += 'static const struct { uint64 lo, hi; } symbols[] = {\n'
header += ''.join('{' + str(r['lo']) + 'ULL,' + str(r['hi']) + 'ULL},\n' for r in symbols) + '};\n'
(a.out / 'symbol_map.h').write_text(header)
(a.out / 'symbol-map.json').write_text(json.dumps({'image_base': base, 'symbols': symbols}, indent=2) + '\n')
source = Path(__file__).with_name('profile_counter.c').resolve()
command = ['gcc', '-shared', '-fPIC', '-O3', '-fno-stack-protector', '-DX86_64', '-DLINUX',
    '-I' + str(a.sdk / 'include'), '-I' + str(a.sdk / 'ext/include'), '-I' + str(a.out), str(source)]
for path in [a.sdk / 'lib64/release', a.sdk / 'ext/lib64/release']:
    command += ['-L' + str(path), '-Wl,-rpath,' + str(path)]
command += ['-ldrx', '-ldrreg', '-ldrmgr', '-ldynamorio', '-o', str(a.out / 'profile-counter.so')]
subprocess.run(command, check=True)
identity = {'binary_sha256': hashlib.sha256(a.binary.read_bytes()).hexdigest(),
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'symbol_map_sha256': hashlib.sha256((a.out / 'symbol-map.json').read_bytes()).hexdigest(),
    'client_sha256': hashlib.sha256((a.out / 'profile-counter.so').read_bytes()).hexdigest(),
    'sized_text_symbols': len(symbols), 'image_base': base, 'compiler_command': command}
(a.out / 'build-identity.json').write_text(json.dumps(identity, indent=2) + '\n')
print(json.dumps({k: identity[k] for k in ['sized_text_symbols', 'image_base', 'client_sha256']}))
