#!/usr/bin/env python3
"""Independently verify lossless reader-output storage; never remove source data."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile

BLOCK = 1024 * 1024
MAX_PART_BYTES = 48 * 1024 * 1024
SOURCE_SHA = 'cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5'
RUN_ID = 39709067518
METADATA_KEYS = ('mode', 'uid', 'gid', 'mtime_ns', 'ctime_ns', 'device', 'inode', 'nlink')


class VerificationError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def _metadata(value):
    return dict(mode=stat.S_IMODE(value.st_mode), uid=value.st_uid, gid=value.st_gid,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
                device=value.st_dev, inode=value.st_ino, nlink=value.st_nlink)


def _exact_ns(value):
    seconds, nanos = divmod(value, 1000000000)
    return str(seconds) + '.' + str(nanos).zfill(9)


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _canonical_inventory(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def _json_unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + str(key))
        result[key] = value
    return result


def _read_checked(path):
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), 'expected regular metadata file: ' + str(path))
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        require(_metadata(os.fstat(stream.fileno())) == _metadata(before),
                'metadata file replaced before read: ' + str(path))
        data = stream.read()
        require(_metadata(os.fstat(stream.fileno())) == _metadata(before)
                and os.fstat(stream.fileno()).st_size == before.st_size,
                'metadata file changed during read: ' + str(path))
    after = path.lstat()
    require(_metadata(after) == _metadata(before) and after.st_size == len(data) == before.st_size,
            'metadata file changed after read: ' + str(path))
    return data, dict(size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                      metadata=_metadata(before))


def _snapshot(source):
    """Hash every file path independently, then derive topology from actual inodes."""
    entries = {}
    inodes = defaultdict(list)

    def visit(path):
        before = path.lstat()
        key = '.' if path == source else path.relative_to(source).as_posix()
        record = _metadata(before)
        if stat.S_ISDIR(before.st_mode):
            entries[key] = dict(kind='directory', **record)
            for child in sorted(path.iterdir(), key=lambda value: value.name):
                visit(child)
            require(_metadata(path.lstat()) == record,
                    'source directory changed during snapshot: ' + key)
        elif stat.S_ISREG(before.st_mode):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            digest = hashlib.sha256()
            size = 0
            with os.fdopen(descriptor, 'rb') as stream:
                opened = os.fstat(stream.fileno())
                require(_metadata(opened) == record and opened.st_size == before.st_size,
                        'source replaced before hashing: ' + key)
                for block in iter(lambda: stream.read(BLOCK), b''):
                    digest.update(block)
                    size += len(block)
                closed = os.fstat(stream.fileno())
                require(_metadata(closed) == record and closed.st_size == before.st_size,
                        'source changed while hashing: ' + key)
            after = path.lstat()
            require(_metadata(after) == record and after.st_size == size == before.st_size,
                    'source changed after hashing: ' + key)
            entries[key] = dict(kind='file', **record, size=size, sha256=digest.hexdigest())
            inodes[(before.st_dev, before.st_ino)].append(key)
        else:
            raise VerificationError('source symlink/special object refused: ' + key)

    require(stat.S_ISDIR(source.lstat().st_mode), 'source root must be a real directory')
    visit(source)
    for names in inodes.values():
        names.sort()
        require(all(entries[name]['nlink'] == len(names) for name in names),
                'source inode has external hardlinks: ' + names[0])
        for name in names[1:]:
            entries[name]['hardlink_target'] = names[0]
    return entries


class _Parts:
    def __init__(self, directory, parts, expected):
        self.directory, self.parts, self.expected = directory, parts, expected
        self.digest = hashlib.sha256()
        self.size = 0
        self.identities = []
        self.complete = False

    def chunks(self):
        for part in self.parts:
            path = self.directory / part['name']
            before = path.lstat()
            require(stat.S_ISREG(before.st_mode), 'part is not a regular file: ' + part['name'])
            require(before.st_size == part['size'], 'part size differs before read: ' + part['name'])
            digest, size = hashlib.sha256(), 0
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, 'rb') as stream:
                require(_metadata(os.fstat(stream.fileno())) == _metadata(before),
                        'part replaced before read: ' + part['name'])
                for block in iter(lambda: stream.read(BLOCK), b''):
                    digest.update(block)
                    size += len(block)
                    self.digest.update(block)
                    self.size += len(block)
                    require(size <= part['size'] and self.size <= self.expected['size'],
                            'compressed input exceeds declared size')
                    yield block
                require(_metadata(os.fstat(stream.fileno())) == _metadata(before)
                        and os.fstat(stream.fileno()).st_size == before.st_size,
                        'part changed during read: ' + part['name'])
            after = path.lstat()
            require(_metadata(after) == _metadata(before) and after.st_size == before.st_size,
                    'part changed after read: ' + part['name'])
            require(size == part['size'] and digest.hexdigest() == part['sha256'],
                    'part SHA256/size mismatch: ' + part['name'])
            self.identities.append((path, _metadata(before), size))
        require(self.size == self.expected['size']
                and self.digest.hexdigest() == self.expected['sha256'],
                'whole concatenated XZ SHA256/size mismatch')
        self.complete = True

    def recheck(self):
        require(self.complete and len(self.identities) == len(self.parts), 'not all parts verified')
        for path, expected, size in self.identities:
            current = path.lstat()
            require(stat.S_ISREG(current.st_mode) and _metadata(current) == expected
                    and current.st_size == size, 'part changed after stream verification: ' + path.name)


class _XZReader:
    """One bounded-output XZ decoder over independently hashed compressed parts."""
    def __init__(self, parts):
        self.chunks = iter(parts.chunks())
        self.decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ,
                                           memlimit=1024 * 1024 * 1024)
        self.complete = False
        self.decoded_size = 0

    def _finish(self):
        require(not self.decoder.unused_data, 'trailing data or second XZ stream refused')
        require(self.decoder.check == lzma.CHECK_CRC64, 'XZ integrity check must be CRC64')
        try:
            next(self.chunks)
        except StopIteration:
            self.complete = True
        else:
            raise VerificationError('compressed bytes follow the single XZ stream')

    def read(self, size):
        require(type(size) is int and size >= 0, 'bounded stream read required')
        result = bytearray()
        while len(result) < size and not self.complete:
            if self.decoder.needs_input:
                try:
                    encoded = next(self.chunks)
                except StopIteration as error:
                    raise VerificationError('incomplete XZ stream or footer') from error
            else:
                encoded = b''
            decoded = self.decoder.decompress(encoded, max_length=min(BLOCK, size - len(result)))
            result.extend(decoded)
            self.decoded_size += len(decoded)
            require(decoded or self.decoder.needs_input or self.decoder.eof,
                    'XZ decoder made no progress')
            if self.decoder.eof:
                self._finish()
        return bytes(result)


def _validate_manifest(manifest, source):
    require(manifest.get('schema') == 'mathgraph.reader-output-preservation.v1', 'unexpected manifest schema')
    require(source.is_absolute() and manifest.get('source_root') == str(source), 'source scope mismatch')
    require(manifest.get('root_name') == source.name and source.name not in ('', '.', '..'), 'root name mismatch')
    require(manifest.get('expected_source_sha') == SOURCE_SHA
            and manifest.get('expected_run_id') == RUN_ID, 'qualified source/run mismatch')
    completion = manifest['completion']
    require(completion.get('completed') is True and completion.get('passed') is True
            and completion.get('source_sha') == SOURCE_SHA
            and completion.get('primary_transition_count') == 800
            and completion.get('fresh_kernel_processes') == 108
            and _sha(completion.get('summary_sha256')), 'reader completion requirements not met')
    execution = manifest['reader_execution']
    require(isinstance(execution.get('path'), str) and Path(execution['path']).is_absolute()
            and _sha(execution.get('sha256')), 'invalid reader execution reference')
    entries = manifest['entries']
    require(isinstance(entries, dict) and entries.get('.', {}).get('kind') == 'directory', 'missing root inventory')
    for key, entry in entries.items():
        require(isinstance(key, str), 'inventory key must be text')
        relative = PurePosixPath(key)
        require(key == '.' or (not relative.is_absolute() and '..' not in relative.parts
                              and relative.as_posix() == key and key != ''), 'unsafe relative inventory path')
        require(entry.get('kind') in ('file', 'directory'), 'unsupported inventory object kind')
        require(all(type(entry.get(field)) is int for field in METADATA_KEYS), 'invalid inventory metadata')
        if entry['kind'] == 'file':
            require(_integer(entry.get('size')) and _sha(entry.get('sha256')), 'invalid file identity')
            if 'hardlink_target' in entry:
                target = entry['hardlink_target']
                require(target in entries and entries[target].get('kind') == 'file' and target != key,
                        'invalid inventory hardlink target')
    require(_sha(manifest.get('inventory_sha256'))
            and _canonical_inventory(entries) == manifest['inventory_sha256'], 'inventory digest mismatch')
    part_bytes = manifest['part_bytes']
    require(_integer(part_bytes, 1) and part_bytes <= MAX_PART_BYTES, 'invalid part size limit')
    parts = manifest['parts']
    require(isinstance(parts, list) and parts, 'no compressed parts')
    for index, part in enumerate(parts):
        require(part.get('name') == 'reader-output.tar.xz.part' + str(index).zfill(3), 'unexpected part name/order')
        require(_integer(part.get('size'), 1) and part['size'] <= part_bytes
                and _sha(part.get('sha256')), 'invalid part identity')
        require(index == len(parts) - 1 or part['size'] == part_bytes, 'short non-final part')
    archive = manifest['archive']
    require(archive.get('format') == 'tar.xz' and archive.get('xz_check') == 'CRC64'
            and _integer(archive.get('size'), 1) and _sha(archive.get('sha256'))
            and archive['size'] == sum(part['size'] for part in parts), 'invalid whole archive identity')


def _verify_completion(manifest, source):
    summary_bytes, summary_identity = _read_checked(source / 'summary.json')
    require(summary_identity['sha256'] == manifest['completion']['summary_sha256']
            == manifest['entries'].get('summary.json', {}).get('sha256'), 'summary identity mismatch')
    summary = json.loads(summary_bytes, object_pairs_hook=_json_unique)
    require(summary.get('schema') == 'mathgraph.authenticated-state-independent-replay.v1'
            and summary.get('completed') is True
            and summary.get('passed') is True
            and summary.get('source_sha') == SOURCE_SHA
            and summary.get('primary_transition_count') == 800
            and summary.get('fresh_kernel_processes') == 108, 'summary is not a completed qualified pass')
    execution_path = Path(manifest['reader_execution']['path'])
    execution_bytes, identity = _read_checked(execution_path)
    require(identity['sha256'] == manifest['reader_execution']['sha256'], 'execution proof SHA256 mismatch')
    execution = json.loads(execution_bytes, object_pairs_hook=_json_unique)
    require(execution.get('completed') is True and type(execution.get('returncode')) is int
            and execution['returncode'] == 0 and execution.get('source_sha') == SOURCE_SHA
            and execution.get('head_after') == SOURCE_SHA and execution.get('run_id') == RUN_ID
            and execution.get('status_after') == '', 'execution proof is not a clean completed qualified run')
    command = execution.get('command')
    require(isinstance(command, list) and all(isinstance(value, str) for value in command), 'invalid execution command')
    positions = [index for index, value in enumerate(command) if value == '--out']
    require(len(positions) == 1 and positions[0] + 1 < len(command)
            and command[positions[0] + 1] == str(source), 'execution --out scope mismatch')
    return execution_path, execution_bytes, identity


def verify(manifest_path, source_path, proof_path):
    """Verify everything read-only; write a fresh proof only after full success."""
    manifest_path, source, proof_path = Path(manifest_path), Path(source_path), Path(proof_path)
    require(not proof_path.exists() and not proof_path.is_symlink(), 'proof already exists')
    require(proof_path.parent.is_dir(), 'proof parent must already exist')
    resolved_proof = proof_path.parent.resolve() / proof_path.name
    resolved_source = source.resolve()
    require(resolved_proof != resolved_source and resolved_source not in resolved_proof.parents,
            'proof must be outside the source tree')
    manifest_bytes, manifest_identity = _read_checked(manifest_path)
    manifest = json.loads(manifest_bytes, object_pairs_hook=_json_unique)
    _validate_manifest(manifest, source)
    execution_path, execution_bytes, execution_identity = _verify_completion(manifest, source)
    initial = _snapshot(source)
    require(initial == manifest['entries'], 'independent initial source inventory differs from manifest')
    require(_canonical_inventory(initial) == manifest['inventory_sha256'], 'initial inventory SHA256 mismatch')
    parts = _Parts(manifest_path.parent, manifest['parts'], manifest['archive'])
    decoded = _XZReader(parts)
    expected = {}
    for key, entry in initial.items():
        name = manifest['root_name'] if key == '.' else manifest['root_name'] + '/' + key
        expected[name] = entry
    seen, counts = {}, Counter()
    logical_bytes, unique_bytes = 0, 0
    with tarfile.open(fileobj=decoded, mode='r|', bufsize=512) as archive:
        for _ in range(len(expected)):
            member = archive.next()
            require(member is not None, 'TAR ended before complete coverage')
            name = member.name
            require(name in expected and name not in seen, 'unknown or duplicate TAR member: ' + name)
            entry = expected[name]
            require(member.mode == entry['mode'] and member.uid == entry['uid']
                    and member.gid == entry['gid'], 'TAR mode/ownership mismatch: ' + name)
            require(member.pax_headers.get('mtime') == _exact_ns(entry['mtime_ns'])
                    and member.pax_headers.get('ctime') == _exact_ns(entry['ctime_ns']),
                    'TAR exact timestamp mismatch: ' + name)
            require(set(member.pax_headers).issubset({'mtime', 'ctime', 'path', 'linkpath'}),
                    'unexpected PAX metadata: ' + name)
            counts['members'] += 1
            if entry['kind'] == 'directory':
                require(member.type == tarfile.DIRTYPE and member.size == 0, 'TAR directory type mismatch: ' + name)
                seen[name] = dict(kind='directory')
                counts['directories'] += 1
            else:
                if 'hardlink_target' not in entry:
                    require(member.type == tarfile.REGTYPE and member.size == entry['size'], 'TAR data type/size mismatch: ' + name)
                    stream = archive.extractfile(member)
                    require(stream is not None, 'missing TAR member data: ' + name)
                    digest, size = hashlib.sha256(), 0
                    with stream:
                        for block in iter(lambda: stream.read(BLOCK), b''):
                            digest.update(block)
                            size += len(block)
                    digest = digest.hexdigest()
                    origin = name
                    counts['regular_data_members'] += 1
                    unique_bytes += size
                else:
                    target = manifest['root_name'] + '/' + entry['hardlink_target']
                    require(member.type == tarfile.LNKTYPE and member.size == 0
                            and member.linkname == target and target in seen,
                            'TAR hardlink type/target mismatch: ' + name)
                    prior = seen[target]
                    require(prior['kind'] == 'file' and prior['origin'] == target,
                            'hardlink did not resolve to a prior byte-read member: ' + name)
                    digest, size, origin = prior['sha256'], prior['size'], target
                    counts['hardlink_members'] += 1
                require(size == entry['size'] and digest == entry['sha256'], 'TAR member SHA256/size mismatch: ' + name)
                seen[name] = dict(kind='file', sha256=digest, size=size, origin=origin)
                logical_bytes += size
        require(set(seen) == set(expected), 'TAR member coverage differs from inventory')
        tail_start = archive.fileobj.tell()
        tail_size = 0
        for block in iter(lambda: archive.fileobj.read(BLOCK), b''):
            require(block.count(b'\0') == len(block), 'nonzero TAR data after declared final member')
            tail_size += len(block)
        require(tail_size >= (-tail_start) % 512 + 1024
                and (tail_start + tail_size) % 512 == 0, 'missing or malformed TAR end blocks')
    require(decoded.complete and parts.complete, 'XZ stream/footer was not fully verified')
    parts.recheck()
    final = _snapshot(source)
    require(final == initial == manifest['entries'], 'source changed during independent verification')
    require(_canonical_inventory(final) == manifest['inventory_sha256'], 'final inventory SHA256 mismatch')
    final_manifest_bytes, final_manifest_identity = _read_checked(manifest_path)
    require(final_manifest_bytes == manifest_bytes and final_manifest_identity == manifest_identity,
            'manifest changed during verification')
    final_execution_bytes, final_execution_identity = _read_checked(execution_path)
    require(final_execution_bytes == execution_bytes and final_execution_identity == execution_identity,
            'external execution proof changed during verification')
    parts.recheck()
    proof = dict(schema='mathgraph.reader-output-independent-verification.v1', status='passed',
                 purpose='Lossless storage verification only; no runtime performance claim.',
                 created_at_utc=datetime.now(timezone.utc).isoformat(),
                 manifest_path=str(manifest_path), manifest_sha256=manifest_identity['sha256'],
                 manifest_size=manifest_identity['size'], archive_sha256=parts.digest.hexdigest(),
                 archive_size=parts.size, inventory_sha256=manifest['inventory_sha256'],
                 source_root=str(source), source_verified=True, source_untouched=True,
                 exact_member_coverage=True, all_member_bytes_verified=True,
                 initial_and_final_source_snapshots_match=True,
                 xz_single_stream_crc64_verified=True, xz_fully_drained=True,
                 tar_tail_zero_bytes=tail_size, tar_decoded_size=decoded.decoded_size,
                 part_count=len(manifest['parts']), part_bytes=manifest['part_bytes'],
                 counts=dict(counts), source_file_paths=sum(entry['kind'] == 'file' for entry in final.values()),
                 source_directories=sum(entry['kind'] == 'directory' for entry in final.values()),
                 logical_file_bytes=logical_bytes, unique_file_bytes=unique_bytes,
                 external_hardlinks=0, symlinks=0, special_objects=0,
                 completion=manifest['completion'], reader_execution=manifest['reader_execution'])
    with proof_path.open('x') as output:
        json.dump(proof, output, sort_keys=True, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    if hasattr(os, 'O_DIRECTORY'):
        directory_descriptor = os.open(proof_path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--proof', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest, args.source, args.proof), sort_keys=True))


if __name__ == '__main__':
    main()
