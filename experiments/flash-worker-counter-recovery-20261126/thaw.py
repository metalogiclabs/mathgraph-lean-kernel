"""Restore the exact generic executable already verified on complete Mathlib."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
archive_sha = hashlib.sha256(a.archive.read_bytes()).hexdigest()
assert archive_sha == '1a24ca4c7161e0ad47e58bb0d4d3d11c3345c6d249cd6d42a9e7e3976d8ef9b5'
with zipfile.ZipFile(a.archive) as z:
    assert z.testzip() is None
    names = [n for n in z.namelist() if n == 'strict.bin' or n.endswith('/strict.bin')]
    assert len(names) == 1, names
    binary = z.read(names[0])
    binary_sha = hashlib.sha256(binary).hexdigest()
    assert binary_sha == '09fe7ecf7421be7ad7f7c57596c214bcd6e7c0d912d6d555cb5749b17202bd5b'
    for name in z.namelist():
        if name.endswith('.bin') or name.endswith('/'):
            continue
        path = Path(name)
        assert not path.is_absolute() and '..' not in path.parts
        target = a.out / 'original-evidence' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(name))
path = a.out / 'checker.bin'
path.write_bytes(binary)
path.chmod(0o755)
record = {
    'source_commit': 'bc704eebed4e009bc66af1a849f18315c11f1926',
    'source_tree': '06c257f0f2ff1f64711cfa54620b650e6dd59b7e',
    'original_run': 45712976230, 'original_artifact': 15069518161,
    'archive_sha256': archive_sha, 'zip_crc_valid': True,
    'binary_sha256': binary_sha,
    'build_boundary': 'Previously frozen generic x86-64 executable, not rebuilt or relabelled as native.',
    'recovery_reason': 'The separate native worker study accepted four complete exports, but '
                       'the first instrumented native execution exited with SIGILL (-4). '
                       'Its exact cause is unresolved. The known generic binary avoids '
                       'introducing native CPU specialization into this recovery experiment.',
}
(a.out / 'frozen-identity.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
