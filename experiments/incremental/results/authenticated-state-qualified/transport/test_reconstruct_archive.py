import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import reconstruct_archive as reconstruct


def make_manifest(root, data):
    encoded = lzma.compress(data, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64)
    parts = []
    for index, start in enumerate(range(0, len(encoded), 65536)):
        block = encoded[start:start + 65536]
        name = 'part' + str(index)
        (root / name).write_bytes(block)
        parts.append(dict(index=index, name=name, bytes=len(block), sha256=hashlib.sha256(block).hexdigest()))
    manifest = dict(schema='mathgraph.lossless-xz-evidence-parts.v1',
                    original=dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest()),
                    wrapper=dict(bytes=len(encoded), sha256=hashlib.sha256(encoded).hexdigest()),
                    part_bytes=48 * 1024 * 1024, part_count=len(parts), parts=parts)
    path = root / 'manifest.json'
    path.write_text(json.dumps(manifest))
    return path, manifest


class ReplayTests(unittest.TestCase):
    def fixture(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('payload.bin', os.urandom(180000))
            archive.writestr('marker', b'known CRC payload')
        return buffer.getvalue()

    def test_cli_exact_bytes_written_sha_and_zip_crc(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self.fixture()
            manifest, _ = make_manifest(root, data)
            output = root / 'fresh.zip'
            run = subprocess.run([sys.executable, '-B', str(Path(reconstruct.__file__)),
                                  '--manifest', str(manifest), '--output', str(output)],
                                 check=True, text=True, capture_output=True)
            result = json.loads(run.stdout)
            self.assertTrue(result['zip_crc_checked'])
            self.assertTrue(result['written_output_sha256_verified'])
            self.assertEqual(result['zip_members'], 2)
            self.assertEqual(output.read_bytes(), data)

    def test_existing_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _ = make_manifest(root, self.fixture())
            output = root / 'existing.zip'
            output.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):
                reconstruct.verify_parts(manifest, output)
            self.assertEqual(output.read_bytes(), b'keep')

    def test_declared_size_caps_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self.fixture()
            manifest, record = make_manifest(root, data)
            record['original']['bytes'] = len(data) - 1
            manifest.write_text(json.dumps(record))
            output = root / 'capped.zip'
            with self.assertRaisesRegex(RuntimeError, 'exceeds declared original size'):
                reconstruct.verify_parts(manifest, output)
            self.assertLessEqual(output.stat().st_size, len(data) - 1)

    def test_crc_failure_rejected_even_with_matching_manifest_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self.fixture().replace(b'known CRC payload', b'brokenCRC payload', 1)
            manifest, _ = make_manifest(root, data)
            with self.assertRaisesRegex(RuntimeError, 'CRC check failed'):
                reconstruct.verify_parts(manifest, root / 'bad-crc.zip')


if __name__ == '__main__':
    unittest.main()
