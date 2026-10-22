#!/usr/bin/env python3
"""Losslessly wrap the frozen compact ZIP for evidence storage; no runtime benchmark."""
import hashlib
import json
import lzma
import os
from pathlib import Path
import stat
import subprocess
import time
from datetime import datetime, timezone
from reconstruct_archive import verify_parts

DIRECTORY = Path(__file__).resolve().parent
ORIGINAL = DIRECTORY.parent / 'ci-d1b2244/revision-chain-summaries-d1b2244.zip'
PROOF = ORIGINAL.parent / 'reconstruction-proof.json'
EXPECTED_BYTES = 1250298163
EXPECTED_SHA256 = '878fbeeb4f6241084fd89ca20a2b9b8077c9071e2ada7e2e0b94d054e743d766'
PART_BYTES = 48 * 1024 * 1024
BLOCK = 1024 * 1024


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest_stream(stream):
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(BLOCK), b''):
        digest.update(block)
        size += len(block)
    return dict(bytes=size, sha256=digest.hexdigest())


def identity(path):
    with path.open('rb') as stream:
        return digest_stream(stream)


def source_stat():
    value = ORIGINAL.lstat()
    require(stat.S_ISREG(value.st_mode), 'original is not a regular file')
    return {key: getattr(value, key) for key in ('st_dev', 'st_ino', 'st_nlink', 'st_size', 'st_mode', 'st_uid', 'st_gid', 'st_mtime_ns', 'st_ctime_ns')}


def write_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.rename(temporary, path)
    directory_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def event(stage, **fields):
    print(json.dumps(dict(stage=stage, utc=datetime.now(timezone.utc).isoformat(), **fields)), flush=True)


def main():
    started = time.perf_counter()
    before = source_stat()
    require(before['st_size'] == EXPECTED_BYTES, 'original ZIP size differs from frozen expected size')
    proof = json.loads(PROOF.read_text())
    require(proof['passed'] is True and proof['zip_crc_passed'] is True, 'source reconstruction proof failed')
    require(proof['original_bytes'] == EXPECTED_BYTES and proof['original_sha256'] == EXPECTED_SHA256, 'source proof identity mismatch')
    wrapper = DIRECTORY / 'archive.zip.xz'
    temporary = DIRECTORY / 'archive.zip.xz.tmp'
    manifest_path = DIRECTORY / 'part-manifest.json'
    require(not wrapper.exists() and not temporary.exists() and not manifest_path.exists(), 'packaging destination already exists')
    require(not list(DIRECTORY.glob('archive.zip.xz.part*')), 'parts already exist')
    command = ['xz', '-3', '--lzma2=dict=128MiB', '--threads=1', '--stdout']
    version = subprocess.run(['xz', '--version'], check=True, text=True, capture_output=True).stdout.splitlines()[0]
    event('compression_started', original_bytes=EXPECTED_BYTES, compression_command=command)
    compression_started = time.perf_counter()
    original_digest = hashlib.sha256()
    original_size = 0
    with temporary.open('xb') as output, (DIRECTORY / 'compression.stderr.log').open('x') as stderr:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=output, stderr=stderr)
        try:
            with ORIGINAL.open('rb') as source:
                for block in iter(lambda: source.read(BLOCK), b''):
                    original_digest.update(block)
                    original_size += len(block)
                    process.stdin.write(block)
            process.stdin.close()
            require(process.wait() == 0, 'xz compression failed; see compression.stderr.log')
        except BaseException:
            process.kill()
            process.wait()
            raise
        output.flush()
        os.fsync(output.fileno())
    compression_seconds = time.perf_counter() - compression_started
    require(original_size == EXPECTED_BYTES and original_digest.hexdigest() == EXPECTED_SHA256, 'source ZIP SHA256 differs from frozen identity')
    require(source_stat() == before, 'original ZIP changed during compression')
    compressed_identity = identity(temporary)
    with lzma.open(temporary, 'rb') as stream:
        decompressed_identity = digest_stream(stream)
    require(decompressed_identity == dict(bytes=EXPECTED_BYTES, sha256=EXPECTED_SHA256), 'XZ readback is not the exact original ZIP')
    os.rename(temporary, wrapper)
    event('wrapper_verified', wrapper_bytes=compressed_identity['bytes'], wrapper_sha256=compressed_identity['sha256'], compression_wall_seconds=compression_seconds)
    parts = []
    with wrapper.open('rb') as source:
        index = 0
        while True:
            data = source.read(PART_BYTES)
            if not data:
                break
            name = 'archive.zip.xz.part' + str(index).zfill(3)
            path = DIRECTORY / name
            with path.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            parts.append(dict(index=index, name=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            index += 1
    require(all(part['bytes'] <= PART_BYTES for part in parts), 'part exceeds cap')
    manifest = dict(schema='mathgraph.lossless-xz-evidence-parts.v1',
                    purpose='Lossless evidence packaging only; packaging timings are not runtime performance evidence.',
                    created_at_utc=datetime.now(timezone.utc).isoformat(),
                    qualified_source=proof['qualified_source'], qualification_run=proof['qualification_run'],
                    original_artifact_id=proof['original_artifact_id'],
                    reconstruction_proof=dict(path=str(PROOF), **identity(PROOF)),
                    original=dict(name=ORIGINAL.name, source_path=str(ORIGINAL), bytes=EXPECTED_BYTES, sha256=EXPECTED_SHA256),
                    original_stat_before=before,
                    wrapper=dict(name=wrapper.name, **compressed_identity, format='XZ', check='CRC64'),
                    compression=dict(command=command, xz_version=version, wall_seconds=compression_seconds),
                    part_bytes=PART_BYTES, part_count=len(parts), parts=parts,
                    standalone_wrapper_stream_decompression_verified=True)
    write_json(manifest_path, manifest)
    verification = verify_parts(manifest_path)
    require(verification['passed'] is True, 'part replay verification failed')
    require(source_stat() == before, 'original ZIP changed during packaging or verification')
    manifest['parts_concatenation_and_stream_decompression_verification'] = verification
    manifest['original_file_unchanged_after_all_verification'] = True
    manifest['total_packaging_and_verification_wall_seconds'] = time.perf_counter() - started
    manifest['transport_files_deleted'] = []
    fs = os.statvfs(DIRECTORY)
    manifest['free_bytes_at_completion'] = fs.f_bavail * fs.f_frsize
    write_json(manifest_path, manifest)
    require(json.loads(manifest_path.read_text()) == manifest, 'persisted manifest mismatch')
    event('parts_verified_and_manifest_persisted', manifest=str(manifest_path), manifest_sha256=identity(manifest_path)['sha256'], wrapper_bytes=compressed_identity['bytes'], wrapper_sha256=compressed_identity['sha256'], part_count=len(parts), part_bytes=PART_BYTES, original_bytes=EXPECTED_BYTES, original_sha256=EXPECTED_SHA256, free_bytes=manifest['free_bytes_at_completion'], total_wall_seconds=manifest['total_packaging_and_verification_wall_seconds'])


if __name__ == '__main__':
    main()
