#!/usr/bin/env python3
"""Losslessly preserve only the completed actual independent reader output.

Packaging resource use is not a runtime speedup or performance observation.
Archive creation never removes source data. Removal is a separate guarded action.
"""
import argparse
import hashlib
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import time

SOURCE = Path('/workspace/kernel-audit/authenticated-state/actual-independent-replay')
EXECUTION = SOURCE.parent / 'actual-independent-replay-execution.json'
SOURCE_SHA = 'cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5'
RUN_ID = 39709067518
PART_BYTES = 48 * 1024 * 1024
SCHEMA = 'mathgraph.reader-output-preservation.v1'
CHUNK = 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def file_identity(path):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f'Not a regular file: {path}')
    digest = hashlib.sha256()
    size = 0
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        while block := stream.read(CHUNK):
            digest.update(block)
            size += len(block)
    if metadata(before) != metadata(path.lstat()) or size != before.st_size:
        raise ValueError(f'File changed while hashing: {path}')
    return {'size': size, 'sha256': digest.hexdigest()}


def metadata(st):
    return dict(mode=stat.S_IMODE(st.st_mode), uid=st.st_uid, gid=st.st_gid,
                mtime_ns=st.st_mtime_ns, ctime_ns=st.st_ctime_ns,
                device=st.st_dev, inode=st.st_ino, nlink=st.st_nlink)


def snapshot(root):
    """Hash all paths; reject links outside the tree and unstable reads."""
    root = Path(root)
    entries = {}
    groups = {}

    def visit(path, relative):
        before = path.lstat()
        record = metadata(before)
        if stat.S_ISDIR(before.st_mode):
            record['kind'] = 'directory'
            entries[relative] = record
            with os.scandir(path) as children:
                names = sorted(child.name for child in children)
            for name in names:
                visit(path / name, name if relative == '.' else relative + '/' + name)
            if metadata(path.lstat()) != metadata(before):
                raise ValueError(f'Directory changed during inventory: {path}')
        elif stat.S_ISREG(before.st_mode):
            digest = hashlib.sha256()
            size = 0
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                if metadata(os.fstat(stream.fileno())) != metadata(before):
                    raise ValueError(f'File changed before read: {path}')
                while block := stream.read(CHUNK):
                    digest.update(block)
                    size += len(block)
                if metadata(os.fstat(stream.fileno())) != metadata(before):
                    raise ValueError(f'File changed during read: {path}')
            if metadata(path.lstat()) != metadata(before) or size != before.st_size:
                raise ValueError(f'File changed after read: {path}')
            record.update(kind='file', size=size, sha256=digest.hexdigest())
            entries[relative] = record
            groups.setdefault((before.st_dev, before.st_ino), []).append(relative)
        else:
            raise ValueError(f'Symlink or special file refused: {path}')

    visit(root, '.')
    for paths in groups.values():
        paths.sort()
        for relative in paths:
            if entries[relative]['nlink'] != len(paths):
                raise ValueError(f'External hardlink refused: {root / relative}')
        for relative in paths[1:]:
            entries[relative]['hardlink_target'] = paths[0]
    return dict(sorted(entries.items()))


def completion(root, execution_path):
    summary_path = root / 'summary.json'
    summary_identity = file_identity(summary_path)
    report = json.loads(summary_path.read_bytes())
    expected = dict(completed=True, passed=True, source_sha=SOURCE_SHA,
                    primary_transition_count=800, fresh_kernel_processes=108)
    if report.get('schema') != 'mathgraph.authenticated-state-independent-replay.v1':
        raise ValueError('Unexpected reader summary schema')
    for key, value in expected.items():
        if report.get(key) != value or (isinstance(value, bool) and report.get(key) is not value):
            raise ValueError(f'Reader completion gate failed: {key}')
    execution_identity = file_identity(execution_path)
    execution = json.loads(execution_path.read_bytes())
    for key, value in dict(completed=True, returncode=0, source_sha=SOURCE_SHA,
                           head_after=SOURCE_SHA, run_id=RUN_ID, status_after='').items():
        if execution.get(key) != value or (key == 'completed' and execution.get(key) is not True):
            raise ValueError(f'Execution completion gate failed: {key}')
    command = execution.get('command', [])
    if command.count('--out') != 1 or command[command.index('--out') + 1:] == []:
        raise ValueError('Execution proof has no unique output argument')
    if command[command.index('--out') + 1] != str(root):
        raise ValueError('Execution proof output path differs')
    if file_identity(summary_path) != summary_identity or file_identity(execution_path) != execution_identity:
        raise ValueError('Completion proof changed during read')
    return dict(summary_sha256=summary_identity['sha256'], **expected), dict(
        path=str(execution_path), sha256=execution_identity['sha256'])


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_fresh_json(path, value):
    with path.open('xb') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True).encode() + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    sync_dir(path.parent)


class PartsSink:
    def __init__(self, directory, limit):
        self.directory, self.limit = directory, limit
        self.parts, self.stream, self.current = [], None, None
        self.whole, self.total = hashlib.sha256(), 0

    def writable(self):
        return True

    def write(self, data):
        data = memoryview(data)
        original = len(data)
        self.whole.update(data)
        self.total += original
        while data:
            if self.stream is None:
                name = f'reader-output.tar.xz.part{len(self.parts):03d}'
                self.stream = (self.directory / name).open('xb')
                self.current = dict(name=name, size=0, digest=hashlib.sha256())
            amount = min(len(data), self.limit - self.current['size'])
            self.stream.write(data[:amount])
            self.current['digest'].update(data[:amount])
            self.current['size'] += amount
            data = data[amount:]
            if self.current['size'] == self.limit:
                self.finish_part()
        return original

    def flush(self):
        if self.stream is not None:
            self.stream.flush()

    def finish_part(self):
        if self.stream is None:
            return
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()
        self.parts.append(dict(name=self.current['name'], size=self.current['size'],
                               sha256=self.current['digest'].hexdigest()))
        self.stream, self.current = None, None

    def finish(self):
        self.finish_part()
        sync_dir(self.directory)
        return self.parts, dict(size=self.total, sha256=self.whole.hexdigest(),
                                format='tar.xz', xz_check='CRC64')


def decimal_ns(value):
    seconds, nanos = divmod(value, 10**9)
    return f'{seconds}.{nanos:09d}'


def tar_name(manifest, relative):
    return manifest['root_name'] if relative == '.' else manifest['root_name'] + '/' + relative


class PartsReader(io.RawIOBase):
    """Read exact manifest parts, checking each identity and the concatenation."""
    def __init__(self, directory, manifest):
        self.directory, self.manifest = directory, manifest
        self.index, self.stream, self.current = 0, None, None
        self.whole, self.total = hashlib.sha256(), 0
        self.done = False

    def readable(self):
        return True

    def readinto(self, buffer):
        if self.done:
            return 0
        if self.stream is None:
            if self.index == len(self.manifest['parts']):
                if self.total != self.manifest['archive']['size'] or self.whole.hexdigest() != self.manifest['archive']['sha256']:
                    raise ValueError('Concatenated archive identity mismatch')
                self.done = True
                return 0
            part = self.manifest['parts'][self.index]
            name = part['name']
            if PurePosixPath(name).name != name or name in ('.', '..'):
                raise ValueError('Unsafe part path')
            path = self.directory / name
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError('Part is not a regular file')
            self.stream = path.open('rb')
            self.current = dict(digest=hashlib.sha256(), size=0, before=path.lstat(), path=path)
        block = self.stream.read(len(buffer))
        if block:
            buffer[:len(block)] = block
            self.current['digest'].update(block)
            self.current['size'] += len(block)
            self.whole.update(block)
            self.total += len(block)
            return len(block)
        part = self.manifest['parts'][self.index]
        self.stream.close()
        if metadata(self.current['path'].lstat()) != metadata(self.current['before']):
            raise ValueError('Part changed during read')
        if (self.current['size'], self.current['digest'].hexdigest()) != (part['size'], part['sha256']):
            raise ValueError('Part identity mismatch')
        self.index += 1
        self.stream = None
        return self.readinto(buffer)


class XZReader(io.RawIOBase):
    def __init__(self, parts):
        self.parts, self.decoder = parts, lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
        self.done = False

    def readable(self):
        return True

    def readinto(self, buffer):
        if self.done:
            return 0
        while True:
            if self.decoder.eof:
                if self.decoder.check != lzma.CHECK_CRC64:
                    raise ValueError('Expected XZ CRC64 integrity check')
                if self.decoder.unused_data or self.parts.read(1):
                    raise ValueError('Unexpected data after single XZ stream')
                self.done = True
                return 0
            data = self.parts.read(65536) if self.decoder.needs_input else b''
            if not data and self.decoder.needs_input:
                raise ValueError('Truncated XZ stream')
            result = self.decoder.decompress(data, max_length=len(buffer))
            if result:
                buffer[:len(result)] = result
                return len(result)


def readback(manifest_path, source):
    manifest_identity = file_identity(manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    if manifest['schema'] != SCHEMA or str(source) != manifest['source_root']:
        raise ValueError('Manifest scope mismatch')
    if snapshot(source) != manifest['entries']:
        raise ValueError('Source differs before readback')
    stream = io.BufferedReader(XZReader(io.BufferedReader(PartsReader(manifest_path.parent, manifest))))
    expected = {tar_name(manifest, key): (key, record) for key, record in manifest['entries'].items()}
    seen, content = set(), {}
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for _ in range(len(expected)):
            member = archive.next()
            if member is None:
                raise ValueError('Tar ended before expected member count')
            if member.name not in expected or member.name in seen:
                raise ValueError(f'Unexpected or duplicate member: {member.name}')
            key, record = expected[member.name]
            if (member.mode, member.uid, member.gid) != (record['mode'], record['uid'], record['gid']):
                raise ValueError('Tar metadata mismatch')
            for field in ('mtime', 'ctime'):
                if member.pax_headers.get(field) != decimal_ns(record[field + '_ns']):
                    raise ValueError('Tar nanosecond timestamp mismatch')
            if record['kind'] == 'directory':
                if not member.isdir() or member.size:
                    raise ValueError('Directory type mismatch')
            elif 'hardlink_target' in record:
                target = tar_name(manifest, record['hardlink_target'])
                if not member.islnk() or member.linkname != target or member.size:
                    raise ValueError('Hardlink mismatch')
                if content.get(target) != (record['size'], record['sha256']):
                    raise ValueError('Hardlink payload mismatch')
                content[member.name] = content[target]
            else:
                if not member.isreg() or member.size != record['size']:
                    raise ValueError('Regular file type/length mismatch')
                digest, size = hashlib.sha256(), 0
                fileobj = archive.extractfile(member)
                while block := fileobj.read(CHUNK):
                    digest.update(block)
                    size += len(block)
                actual = (size, digest.hexdigest())
                if actual != (record['size'], record['sha256']):
                    raise ValueError('Regular file readback mismatch')
                content[member.name] = actual
            seen.add(member.name)
        tail_size = 0
        while block := archive.fileobj.read(CHUNK):
            tail_size += len(block)
            if any(block):
                raise ValueError('Nonzero data after final tar member')
        if tail_size < (-member.size) % 512 + 1024:
            raise ValueError('Missing tar end blocks')
    stream.close()
    if seen != set(expected):
        raise ValueError('Incomplete tar member coverage')
    if snapshot(source) != manifest['entries']:
        raise ValueError('Source differs after readback')
    for part in manifest['parts']:
        if file_identity(manifest_path.parent / part['name']) != {'size': part['size'], 'sha256': part['sha256']}:
            raise ValueError('Archive part differs after source recheck')
    if file_identity(manifest_path) != manifest_identity:
        raise ValueError('Manifest changed during verification')
    return dict(status='passed', manifest_sha256=file_identity(manifest_path)['sha256'],
                archive_sha256=manifest['archive']['sha256'], archive_size=manifest['archive']['size'],
                inventory_sha256=manifest['inventory_sha256'], source_root=str(source),
                source_verified=True, exact_member_coverage=True, all_member_bytes_verified=True,
                part_count=len(manifest['parts']), member_count=len(seen))


def archive_source(source, destination, execution_path, part_bytes=PART_BYTES):
    source, destination, execution_path = map(Path, (source, destination, execution_path))
    if source.resolve() != source or destination.resolve() != destination:
        raise ValueError('Absolute canonical paths required')
    if destination == source or source in destination.parents:
        raise ValueError('Archive destination must be outside the source tree')
    if not 1 <= part_bytes <= PART_BYTES:
        raise ValueError('Part limit exceeds 48 MiB')
    completed, execution = completion(source, execution_path)
    entries = snapshot(source)
    destination.mkdir(mode=0o755, parents=False, exist_ok=False)
    manifest = dict(schema=SCHEMA, source_root=str(source), root_name=source.name,
                    expected_source_sha=SOURCE_SHA, expected_run_id=RUN_ID,
                    completion=completed, reader_execution=execution, entries=entries,
                    inventory_sha256=hashlib.sha256(canonical(entries)).hexdigest(),
                    part_bytes=part_bytes,
                    packaging_claim='Lossless evidence storage only; no runtime speedup claim.')
    sink = PartsSink(destination, part_bytes)
    with lzma.LZMAFile(sink, 'wb', format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64,
                       filters=[dict(id=lzma.FILTER_LZMA2, preset=3, dict_size=32 * 1024 * 1024)]) as compressed:
        with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
            for relative, record in entries.items():
                member = tarfile.TarInfo(tar_name(manifest, relative))
                member.mode, member.uid, member.gid = record['mode'], record['uid'], record['gid']
                member.mtime = record['mtime_ns'] // 10**9
                member.pax_headers = dict(mtime=decimal_ns(record['mtime_ns']), ctime=decimal_ns(record['ctime_ns']))
                if record['kind'] == 'directory':
                    member.type = tarfile.DIRTYPE
                    archive.addfile(member)
                elif 'hardlink_target' in record:
                    member.type = tarfile.LNKTYPE
                    member.linkname = tar_name(manifest, record['hardlink_target'])
                    archive.addfile(member)
                else:
                    member.size = record['size']
                    with (source / relative).open('rb') as payload:
                        archive.addfile(member, payload)
    manifest['parts'], manifest['archive'] = sink.finish()
    if snapshot(source) != entries or completion(source, execution_path) != (completed, execution):
        raise ValueError('Source or completion proof changed while archiving')
    manifest_path = destination / 'manifest.json'
    write_fresh_json(manifest_path, manifest)
    proof = readback(manifest_path, source)
    proof.update(schema='mathgraph.reader-output-writer-verification.v1',
                 original_tree_removed=False, completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    write_fresh_json(destination / 'archive-proof.json', proof)
    return manifest_path


def remove_source(manifest_path, independent_proof_path, root_proof_path):
    """Production-only, explicit deletion with full revalidation and root proof."""
    manifest_path, independent_proof_path, root_proof_path = map(Path, (manifest_path, independent_proof_path, root_proof_path))
    manifest = json.loads(manifest_path.read_bytes())
    if manifest['source_root'] != str(SOURCE) or manifest['root_name'] != SOURCE.name:
        raise ValueError('Removal scope is restricted to the actual reader output')
    completed, execution = completion(SOURCE, EXECUTION)
    if completed != manifest['completion'] or execution != manifest['reader_execution']:
        raise ValueError('Completion identity differs from archived completion')
    manifest_sha = file_identity(manifest_path)['sha256']
    independent_identity = file_identity(independent_proof_path)
    independent = json.loads(independent_proof_path.read_bytes())
    for key, value in dict(schema='mathgraph.reader-output-independent-verification.v1', status='passed',
                           manifest_sha256=manifest_sha, source_root=str(SOURCE), source_verified=True,
                           exact_member_coverage=True, all_member_bytes_verified=True,
                           inventory_sha256=manifest['inventory_sha256'],
                           archive_sha256=manifest['archive']['sha256'], archive_size=manifest['archive']['size']).items():
        if independent.get(key) != value:
            raise ValueError(f'Independent proof gate failed: {key}')
    root_identity = file_identity(root_proof_path)
    root_proof = json.loads(root_proof_path.read_bytes())
    for key, value in dict(schema='mathgraph.reader-output-root-removal-authorization.v1', status='passed',
                           manifest_sha256=manifest_sha, source_root=str(SOURCE), source_sha=SOURCE_SHA,
                           reader_execution_sha256=execution['sha256'],
                           independent_proof_sha256=independent_identity['sha256']).items():
        if root_proof.get(key) != value:
            raise ValueError(f'Root removal proof gate failed: {key}')
    removal_proof_path = manifest_path.parent / 'removal-proof.json'
    if removal_proof_path.exists() or removal_proof_path.is_symlink():
        raise ValueError('Removal proof already exists')
    proof = readback(manifest_path, SOURCE)
    if (file_identity(manifest_path)['sha256'] != manifest_sha or
            file_identity(independent_proof_path) != independent_identity or
            file_identity(root_proof_path) != root_identity):
        raise ValueError('Proof changed during final verification')
    if completion(SOURCE, EXECUTION) != (completed, execution):
        raise ValueError('Reader completion proof changed during final verification')
    free_before = shutil.disk_usage(SOURCE.parent).free
    shutil.rmtree(SOURCE)
    sync_dir(SOURCE.parent)
    proof.update(schema='mathgraph.reader-output-removal.v1', original_tree_removed=True,
                 removed_only_root=str(SOURCE), free_before=free_before,
                 free_after=shutil.disk_usage(SOURCE.parent).free,
                 independent_proof_sha256=independent_identity['sha256'],
                 root_proof_sha256=root_identity['sha256'])
    write_fresh_json(removal_proof_path, proof)
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    create = commands.add_parser('archive', help='Preserve completed output; never removes source')
    create.add_argument('--destination', required=True, type=Path)
    remove = commands.add_parser('remove', help='Explicit guarded removal after independent/root proof')
    remove.add_argument('--manifest', required=True, type=Path)
    remove.add_argument('--independent-proof', required=True, type=Path)
    remove.add_argument('--root-proof', required=True, type=Path)
    args = parser.parse_args()
    if args.action == 'archive':
        if not args.destination.is_absolute() or args.destination.parent.resolve() != SOURCE.parent:
            parser.error('Destination must be a fresh absolute sibling of the fixed source root')
        print(archive_source(SOURCE, args.destination, EXECUTION))
    else:
        print(json.dumps(remove_source(args.manifest, args.independent_proof, args.root_proof), sort_keys=True))


if __name__ == '__main__':
    main()
