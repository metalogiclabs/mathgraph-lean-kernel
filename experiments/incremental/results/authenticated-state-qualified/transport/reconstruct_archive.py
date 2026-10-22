#!/usr/bin/env python3
"""Losslessly reconstruct evidence; packaging is not a runtime speedup claim."""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import zipfile

BLOCK = 1024 * 1024


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_parts(manifest_path, output=None):
    """Verify all parts and decoded bytes. An output also receives a ZIP CRC check."""
    manifest = json.loads(manifest_path.read_text())
    require(manifest['schema'] == 'mathgraph.lossless-xz-evidence-parts.v1', 'unknown schema')
    require(manifest['part_bytes'] == 48 * 1024 * 1024, 'unexpected part size')
    require(len(manifest['parts']) == manifest['part_count'] > 0, 'part count mismatch')
    original = manifest['original']
    wrapper = manifest['wrapper']
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=512 * 1024 * 1024)
    compressed_digest = hashlib.sha256()
    original_digest = hashlib.sha256()
    compressed_bytes = 0
    original_bytes = 0
    sink = output.open('xb') if output is not None else None
    try:
        for index, part in enumerate(manifest['parts']):
            name = part['name']
            require(Path(name).name == name and name not in ('', '.', '..'), 'unsafe part name')
            require(part['index'] == index and 0 < part['bytes'] <= manifest['part_bytes'], 'invalid part index or size')
            part_digest = hashlib.sha256()
            part_bytes = 0
            with (manifest_path.parent / name).open('rb') as stream:
                for block in iter(lambda: stream.read(BLOCK), b''):
                    require(not decoder.eof, 'data follows the end of the XZ stream')
                    part_digest.update(block)
                    part_bytes += len(block)
                    require(part_bytes <= part['bytes'], 'part exceeds declared size: ' + name)
                    compressed_digest.update(block)
                    compressed_bytes += len(block)
                    require(compressed_bytes <= wrapper['bytes'], 'XZ stream exceeds declared size')
                    encoded = block
                    while True:
                        decoded = decoder.decompress(encoded, max_length=BLOCK)
                        encoded = b''
                        original_bytes += len(decoded)
                        require(original_bytes <= original['bytes'], 'decoded ZIP exceeds declared original size')
                        original_digest.update(decoded)
                        if sink is not None:
                            sink.write(decoded)
                        if decoder.eof:
                            require(not decoder.unused_data, 'unexpected trailing XZ data')
                            break
                        if decoder.needs_input:
                            break
            require(part_bytes == part['bytes'], 'part size mismatch: ' + name)
            require(part_digest.hexdigest() == part['sha256'], 'part SHA256 mismatch: ' + name)
        require(decoder.eof, 'incomplete XZ stream')
        require(compressed_bytes == wrapper['bytes'], 'concatenated XZ size mismatch')
        require(compressed_digest.hexdigest() == wrapper['sha256'], 'concatenated XZ SHA256 mismatch')
        require(original_bytes == original['bytes'], 'reconstructed ZIP size mismatch')
        require(original_digest.hexdigest() == original['sha256'], 'reconstructed ZIP SHA256 mismatch')
        if sink is not None:
            sink.flush()
            os.fsync(sink.fileno())
    finally:
        if sink is not None:
            sink.close()
    zip_members = None
    if output is not None:
        written_digest = hashlib.sha256()
        written_bytes = 0
        with output.open('rb') as written:
            for block in iter(lambda: written.read(BLOCK), b''):
                written_digest.update(block)
                written_bytes += len(block)
        require(written_bytes == original['bytes'], 'written ZIP size mismatch')
        require(written_digest.hexdigest() == original['sha256'], 'written ZIP SHA256 mismatch')
        with zipfile.ZipFile(output) as archive:
            require(archive.testzip() is None, 'reconstructed ZIP member CRC check failed')
            zip_members = len(archive.infolist())
        if hasattr(os, 'O_DIRECTORY'):
            directory_fd = os.open(output.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    return dict(passed=True, parts_verified=len(manifest['parts']),
                concatenated_xz_bytes=compressed_bytes,
                concatenated_xz_sha256=compressed_digest.hexdigest(),
                original_bytes=original_bytes, original_sha256=original_digest.hexdigest(),
                output_path=str(output) if output is not None else None,
                written_output_sha256_verified=output is not None,
                zip_crc_checked=output is not None, zip_members=zip_members)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='exclusive fresh output path; an existing file is never overwritten')
    args = parser.parse_args()
    print(json.dumps(verify_parts(args.manifest, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
