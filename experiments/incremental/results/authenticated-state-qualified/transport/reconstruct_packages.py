#!/usr/bin/env python3
"""Verify bounded provider envelopes and safely stream exact CI evidence.

This is an independent transport reader. It imports no MathGraph runtime code,
does not verify historical HMACs, and does not classify benchmark economics.
"""
import argparse
import hashlib
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import zipfile

BLOCK = 1 << 20
PIECE_LIMIT = 400 << 20
PROVIDER_LIMIT = 512 << 20


def require(value, message):
    if not value:
        raise ValueError(message)


def load(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(entry):
    require(type(entry['bytes']) is int and entry['bytes'] >= 0, 'invalid byte count')
    require(type(entry['sha256']) is str and re.fullmatch('[0-9a-f]{64}', entry['sha256']), 'invalid SHA256')


def safe_path(raw, prefix='artifacts'):
    require(type(raw) is str and '\\' not in raw, 'non-posix path')
    path = PurePosixPath(raw)
    require(not path.is_absolute() and path.as_posix() == raw, 'noncanonical relative path: ' + raw)
    require(path.parts and path.parts[0] == prefix and all(x not in ('', '.', '..') for x in path.parts),
            'unsafe path: ' + raw)
    return path


def provider_zip(path, metadata, source, run_id):
    path = Path(path)
    require(metadata['workflow_run']['head_sha'] == source and metadata['workflow_run']['id'] == run_id,
            'foreign provider artifact source/run')
    require(metadata['expired'] is False, 'provider artifact expired')
    require(0 < metadata['size_in_bytes'] <= PROVIDER_LIMIT, 'provider ZIP exceeds connector cap')
    require(path.stat().st_size == metadata['size_in_bytes'], 'provider ZIP size mismatch')
    digest = sha(path)
    require(metadata['digest'] == 'sha256:' + digest, 'provider ZIP SHA256 mismatch')
    return {'artifact_id': metadata['id'], 'artifact_name': metadata['name'],
            'provider_zip_bytes': path.stat().st_size, 'provider_zip_sha256': digest}


class ConcatenatedZipParts(io.RawIOBase):
    """Read the ordered inner part files without materializing a second archive."""
    def __init__(self, pieces):
        self.pieces = iter(pieces)
        self.archive = self.stream = None
    def readable(self):
        return True
    def readinto(self, buffer):
        while True:
            if self.stream is None:
                try:
                    path, member = next(self.pieces)
                except StopIteration:
                    return 0
                self.archive = zipfile.ZipFile(path)
                self.stream = self.archive.open(member)
            raw = self.stream.read(len(buffer))
            if raw:
                buffer[:len(raw)] = raw
                return len(raw)
            self.stream.close()
            self.archive.close()
            self.stream = self.archive = None
    def close(self):
        if self.stream is not None:
            self.stream.close()
        if self.archive is not None:
            self.archive.close()
        super().close()


def reconstruct(*, source, run_id, run, artifacts, index_zip, parts_dir, out, label='compact'):
    require(re.fullmatch('[0-9a-f]{40}', source), 'expected source must be exact Git SHA')
    require(run['id'] == run_id and run['head_sha'] == source, 'run source/id mismatch')
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'qualification run did not succeed')
    require(label in ('compact', 'full'), 'unknown package label')
    by_name = {}
    for artifact in artifacts['artifacts']:
        require(artifact['name'] not in by_name, 'duplicate provider artifact name')
        by_name[artifact['name']] = artifact
    index_name = 'authenticated-state-index-' + source
    require(index_name in by_name, 'missing index artifact')
    index_proof = provider_zip(index_zip, by_name[index_name], source, run_id)
    with zipfile.ZipFile(index_zip) as archive:
        names = archive.namelist()
        require(len(names) == 2 and set(names) == {'manifest.json', 'REPLAY.txt'}, 'unexpected package-index members')
        require(archive.getinfo('manifest.json').file_size <= 128 << 20, 'manifest too large')
        require(archive.getinfo('REPLAY.txt').file_size <= 1 << 20, 'replay text too large')
        manifest_raw = archive.read('manifest.json')
        replay_raw = archive.read('REPLAY.txt')
    manifest = load(manifest_raw)
    require(manifest['schema'] == 'mathgraph.authenticated-state-artifact-packages.v1', 'unknown package schema')
    require(manifest['source_sha'] == source and int(manifest['github_run_id']) == run_id, 'manifest source/run mismatch')
    require(int(manifest['github_run_attempt']) == run['run_attempt'], 'manifest run-attempt mismatch')
    require(set(manifest['archives']) == {'compact', 'full'}, 'incomplete package manifest')
    entries = {}
    for entry in manifest['all_files']:
        safe_path(entry['path'])
        identity(entry)
        require(entry['path'] not in entries, 'duplicate manifest file')
        entries[entry['path']] = entry
    package = manifest['archives'][label]
    identity(package)
    require(package['format'] == 'tar.xz', 'unknown archive format')
    expected = package['files']
    # The producer sorts pathlib.Path values component by component, not raw
    # strings ("authenticated-state/" precedes "authenticated-state-independent/").
    require(expected and expected == sorted(set(expected), key=PurePosixPath), 'noncanonical/duplicate package file list')
    expected_set=set(expected)
    require(expected_set <= set(entries), 'package file absent from all_files')
    if label == 'full':
        require(expected_set == set(entries), 'full package does not cover all_files')
    maximum = 4 if label == 'compact' else 16
    parts = package['ordered_parts']
    require(0 < len(parts) <= maximum, 'invalid package part count')
    pieces = []
    proofs = []
    whole = hashlib.sha256()
    total = 0
    for index, part in enumerate(parts):
        identity(part)
        member = label + '.tar.xz.part' + str(index).zfill(2)
        require(part['path'] == 'artifact-packages/' + member, 'part schedule/name mismatch')
        require(0 < part['bytes'] <= PIECE_LIMIT, 'part size outside producer bound')
        require(index == len(parts)-1 or part['bytes'] == PIECE_LIMIT, 'short intermediate part')
        name = 'authenticated-state-' + label + '-' + str(index).zfill(2) + '-' + source
        require(name in by_name, 'missing provider part: ' + name)
        path = Path(parts_dir) / (name + '.zip')
        proof = provider_zip(path, by_name[name], source, run_id)
        digest = hashlib.sha256()
        size = 0
        with zipfile.ZipFile(path) as archive:
            require(archive.namelist() == [member], 'unexpected provider part members')
            require(archive.getinfo(member).file_size == part['bytes'], 'inner part declared size mismatch')
            with archive.open(member) as stream:
                for raw in iter(lambda: stream.read(BLOCK), b''):
                    size += len(raw)
                    digest.update(raw)
                    whole.update(raw)
        require(size == part['bytes'] and digest.hexdigest() == part['sha256'], 'inner part identity mismatch')
        total += size
        proof['inner_part'] = part
        proofs.append(proof)
        pieces.append((path, member))
    require(total == package['bytes'] and whole.hexdigest() == package['sha256'], 'whole archive identity mismatch')
    out = Path(out)
    require(not out.exists(), 'output directory already exists')
    required = sum(entries[name]['bytes'] for name in expected)
    free = shutil.disk_usage(out.parent).free
    require(required < free - (64 << 20), 'insufficient extraction space: need ' + str(required) + ', free ' + str(free))
    out.mkdir(mode=0o700)
    seen = set()
    links = []
    padding = 0
    with ConcatenatedZipParts(pieces) as raw, io.BufferedReader(raw) as buffered, lzma.LZMAFile(buffered) as decoded:
        with tarfile.open(fileobj=decoded, mode='r|') as archive:
            for item in archive:
                path = safe_path(item.name)
                require(item.name in entries and item.name in expected_set, 'unexpected tar member: ' + item.name)
                require(item.name not in seen, 'duplicate tar member: ' + item.name)
                entry = entries[item.name]
                target = out.joinpath(*path.parts)
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                if item.isfile():
                    require(item.size == entry['bytes'], 'tar member size mismatch')
                    source_stream = archive.extractfile(item)
                elif item.islnk():
                    safe_path(item.linkname)
                    require(item.linkname in seen, 'hardlink does not target an earlier verified file')
                    prior = entries[item.linkname]
                    require((prior['sha256'], prior['bytes']) == (entry['sha256'], entry['bytes']), 'hardlink identity mismatch')
                    source_stream = out.joinpath(*PurePosixPath(item.linkname).parts).open('rb')
                    links.append({'path':item.name,'verified_target':item.linkname,'materialized_as_copy':True})
                else:
                    raise ValueError('symlink/special/directory tar member refused: ' + item.name)
                with source_stream, target.open('xb') as dest:
                    os.chmod(target, 0o600)
                    for chunk in iter(lambda: source_stream.read(BLOCK), b''):
                        size += len(chunk)
                        require(size <= entry['bytes'], 'tar member exceeds declared bytes')
                        digest.update(chunk)
                        dest.write(chunk)
                require(size == entry['bytes'] and digest.hexdigest() == entry['sha256'], 'tar member SHA256/size mismatch: ' + item.name)
                seen.add(item.name)
            # tarfile stops at the end marker; remaining decoded bytes may only
            # contain zero padding, never hidden members or another archive.
            for tail in iter(lambda: archive.fileobj.read(BLOCK), b''):
                require(not any(tail), 'nonzero bytes after tar end marker')
                padding += len(tail)
    require(seen == expected_set, 'tar members do not cover exact package file list')
    # Re-read persisted bytes independently of the streaming extraction hashes.
    for name in expected:
        path = out.joinpath(*PurePosixPath(name).parts)
        require(path.stat().st_size == entries[name]['bytes'] and sha(path) == entries[name]['sha256'], 'persisted evidence identity mismatch')
    # Detect mutation of a downloaded provider envelope during the two reads.
    require(provider_zip(index_zip, by_name[index_name], source, run_id) == index_proof,
            'provider index changed during reconstruction')
    for index, proof in enumerate(proofs):
        name=proof['artifact_name']
        current=provider_zip(Path(parts_dir)/(name+'.zip'), by_name[name], source, run_id)
        require(all(current[key] == proof[key] for key in current), 'provider part changed during reconstruction')
    proof = dict(schema='mathgraph.authenticated-state-transport-replay.v1', passed=True,
                 source_sha=source, github_run_id=run_id, package=label,
                 index_provider=index_proof, index_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
                 archive_bytes=total, archive_sha256=whole.hexdigest(), ordered_parts=proofs,
                 files_verified=len(seen), uncompressed_member_bytes=required,
                 hardlinks_materialized_as_copies=links, trailing_zero_padding_bytes=padding,
                 output=str(out), persisted_member_bytes_rechecked=True, persisted_provider_zip_bytes_rechecked=True,
                 scope='Transport integrity only; no historical HMAC reauthentication or kernel/economic verdict.')
    (out/'package-manifest.json').write_bytes(manifest_raw)
    (out/'PACKAGE-REPLAY.txt').write_bytes(replay_raw)
    (out/'transport-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    parser.add_argument('--run-id',required=True,type=int)
    parser.add_argument('--run-metadata',required=True,type=Path)
    parser.add_argument('--artifacts-metadata',required=True,type=Path)
    parser.add_argument('--index-zip',required=True,type=Path)
    parser.add_argument('--parts-dir',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--package',choices=['compact','full'],default='compact')
    args=parser.parse_args()
    proof=reconstruct(source=args.source,run_id=args.run_id,run=load(args.run_metadata.read_bytes()),
                      artifacts=load(args.artifacts_metadata.read_bytes()),index_zip=args.index_zip,
                      parts_dir=args.parts_dir,out=args.out,label=args.package)
    print(json.dumps(proof,indent=2))


if __name__=='__main__':
    main()
