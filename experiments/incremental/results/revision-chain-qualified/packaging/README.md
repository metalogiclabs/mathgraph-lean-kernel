# Lossless evidence packaging

These files preserve the exact ZIP from qualified source
`d1b22447d23a928ae536cbe838a47fc9682a4b39`. This is storage and transport
packaging; compression time and compression ratio are not runtime speedup
evidence.

The original ZIP remains at its original local path. Its identity is:

- Bytes: `1250298163`
- SHA256: `878fbeeb4f6241084fd89ca20a2b9b8077c9071e2ada7e2e0b94d054e743d766`

`manifest.json` records provenance, the original ZIP identity, the standard
XZ wrapper identity, ordered part sizes and SHA256s, and verification results.
Each part is at most 48 MiB (`50331648` bytes). Commit the ordered
`archive.zip.xz.partNNN` files, manifest, this README, and
`reconstruct_archive.py`. The full `archive.zip.xz` and original ZIP need not be
committed. A copied manifest may be renamed: the helper resolves part names
against the directory containing the supplied manifest.

## Direct reconstruction with Python's standard library

Choose a fresh output path whose parent directory exists:

```sh
python3 /path/to/packaging/reconstruct_archive.py \
  --manifest /path/to/packaging/manifest.json \
  --output /path/to/fresh-output/qualified.zip
```

The helper verifies every part's size and SHA256, the concatenated XZ size and
SHA256, and the decompressed ZIP size and SHA256. It guards the original byte
limit while streaming, writes exclusively to a new output, rehashes the written
ZIP, then checks every ZIP member's CRC. It refuses an existing output. A failed verification exits
nonzero and can leave the newly created partial output for inspection.

Direct reconstruction needs `1250298163` bytes of output disk space beyond the
stored parts, plus filesystem overhead. Its decoder uses the 128 MiB XZ
dictionary with a 512 MiB decoder memory limit and 1 MiB output buffers.

## Python concatenation followed by standard xz

This alternative also creates a complete XZ wrapper on disk. Supply fresh
paths, with their parent directories already present:

```sh
python3 - /path/to/packaging/manifest.json /path/to/fresh-output/archive.zip.xz <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest = Path(sys.argv[1])
record = json.loads(manifest.read_text())
whole = hashlib.sha256()
total = 0
with Path(sys.argv[2]).open('xb') as output:
    for part in record['parts']:
        name = part['name']
        assert Path(name).name == name and name not in ('', '.', '..')
        digest = hashlib.sha256()
        size = 0
        with (manifest.parent / name).open('rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(block)
                whole.update(block)
                size += len(block)
                total += len(block)
                output.write(block)
        assert size == part['bytes'] and digest.hexdigest() == part['sha256']
assert total == record['wrapper']['bytes']
assert whole.hexdigest() == record['wrapper']['sha256']
PY
xz --decompress --keep /path/to/fresh-output/archive.zip.xz
```

`xz` creates `archive.zip` next to the wrapper and refuses an existing output.
Verify the decoded ZIP against the manifest and check all member CRCs:

```sh
python3 - /path/to/packaging/manifest.json /path/to/fresh-output/archive.zip <<'PY'
import hashlib, json, sys, zipfile
from pathlib import Path
record = json.loads(Path(sys.argv[1]).read_text())
digest = hashlib.sha256()
size = 0
with Path(sys.argv[2]).open('rb') as source:
    for block in iter(lambda: source.read(1024 * 1024), b''):
        digest.update(block)
        size += len(block)
assert size == record['original']['bytes']
assert digest.hexdigest() == record['original']['sha256']
with zipfile.ZipFile(sys.argv[2]) as archive:
    assert archive.testzip() is None
print('Exact original ZIP verified, including every member CRC.')
PY
```

The packager itself used `xz -3 --lzma2=dict=128MiB --threads=1 --stdout`,
verified the standalone wrapper by streaming decompression, and independently
verified the ordered parts by concatenation and streaming decompression. Its
source-byte hash and file metadata checks ensure the original local ZIP stayed
unchanged. The existing reconstruction proof records the original ZIP CRC
verification; a fresh reconstruction performs that CRC check again.
