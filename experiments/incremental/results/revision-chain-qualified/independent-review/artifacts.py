"""Strict streaming artifact access. Standard library only; never extracts a ZIP."""
import contextlib
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

JSON_LOG_MAX_BYTES = 64 * 1024 * 1024
LIFECYCLE_SUMMARY_MAX_BYTES = 512 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def hexid(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def loads(raw):
    return json.loads(raw, object_pairs_hook=strict_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class Artifacts:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.zip = None
        self.opened_signatures = {}
        self.zip_signature = self.signature(self.path) if self.path.is_file() else None
        if self.path.is_file():
            self.zip = zipfile.ZipFile(self.path)
            self.members = {}
            for info in self.zip.infolist():
                name = self.safe(info.filename.rstrip('/'))
                if info.is_dir():
                    continue
                require(name not in self.members, 'duplicate ZIP member: ' + name)
                require(not stat.S_ISLNK(info.external_attr >> 16), 'ZIP symlink refused')
                self.members[name] = info
        else:
            require(self.path.is_dir(), 'artifact directory/ZIP is missing')
            self.members = {str(p.relative_to(self.path)): p for p in self.path.rglob('*') if p.is_file()}
        candidates = [name for name in self.members if name == 'summary.json' or name.endswith('/revision-chain/summary.json') or name == 'revision-chain/summary.json']
        candidates = [name for name in candidates if loads(self.read(name, LIFECYCLE_SUMMARY_MAX_BYTES)).get('schema') == 'mathgraph.authenticated-revision-chain-lifecycle.v1']
        require(len(candidates) == 1, 'exactly one lifecycle summary is required')
        self.summary_member = candidates[0]
        self.lifecycle = str(PurePosixPath(self.summary_member).parent)
        if self.lifecycle == '.':
            self.lifecycle = ''
        self.artifact = self.lifecycle[:-len('revision-chain')].rstrip('/') if self.lifecycle.endswith('revision-chain') else ''
        report = self.json(self.summary_member)
        blobs = [p['genesis']['baseline_witness'] for pr in report.get('profiles', {}).values() for p in pr.get('pairs', [])]
        require(blobs, 'summary has no actual input witness')
        first = blobs[0]
        rel = first['artifact_relative_path']
        require(first['path'].endswith(rel), 'original archive path does not end in artifact-relative path')
        self.original = first['path'][:-len(rel)].rstrip('/')
        self.descriptors = {}
        self.archive_checks = 0

    @staticmethod
    def signature(path):
        st = path.stat()
        return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns

    @staticmethod
    def safe(name):
        require(type(name) is str and '\\' not in name and name and not name.startswith('/'), 'unsafe artifact member')
        parts = PurePosixPath(name).parts
        require('..' not in parts and '.' not in parts, 'artifact traversal refused')
        return '/'.join(parts)

    def join(self, *parts):
        return self.safe('/'.join(str(p).strip('/') for p in parts if str(p).strip('/')))

    def map(self, recorded):
        require(type(recorded) is str, 'recorded path must be text')
        if recorded.startswith(self.original + '/'):
            return self.join(self.lifecycle, recorded[len(self.original) + 1:])
        if recorded.startswith('artifacts/'):
            return self.join(self.artifact, recorded[len('artifacts/'):])
        if '/artifacts/' in recorded:
            return self.join(self.artifact, recorded.split('/artifacts/', 1)[1])
        if not recorded.startswith('/'):
            direct = self.safe(recorded)
            if direct in self.members:
                return direct
        raise ValueError('recorded path is outside artifact: ' + recorded)

    @contextlib.contextmanager
    def open(self, name):
        name = self.safe(name)
        require(name in self.members, 'missing artifact object: ' + name)
        if self.zip:
            require(self.signature(self.path) == self.zip_signature, 'artifact ZIP changed during review')
            with self.zip.open(self.members[name]) as stream:
                yield stream
        else:
            path = self.members[name]
            require(path.resolve().is_relative_to(self.path), 'artifact symlink escapes root')
            signature = self.signature(path)
            if name in self.opened_signatures:
                require(self.opened_signatures[name] == signature, 'artifact file changed during review: ' + name)
            self.opened_signatures[name] = signature
            with path.open('rb') as stream:
                yield stream

    def read(self, name, limit=JSON_LOG_MAX_BYTES):
        with self.open(name) as stream:
            raw = stream.read(limit + 1)
        require(len(raw) <= limit, 'JSON/log artifact exceeds reader bound')
        return raw

    def json(self, name):
        limit = LIFECYCLE_SUMMARY_MAX_BYTES if name == getattr(self, 'summary_member', None) else JSON_LOG_MAX_BYTES
        return loads(self.read(name, limit))

    def stream_hash(self, name, gzip_encoded=False):
        h, length = hashlib.sha256(), 0
        with self.open(name) as raw:
            with (gzip.GzipFile(fileobj=raw) if gzip_encoded else contextlib.nullcontext(raw)) as stream:
                for chunk in iter(lambda: stream.read(1 << 20), b''):
                    h.update(chunk)
                    length += len(chunk)
                    require(length <= 1024 * 1024 * 1024, 'single artifact exceeds 1GiB review bound')
        return h.hexdigest(), length

    def archive(self, record):
        for key in ('sha256', 'uncompressed_sha256'):
            require(hexid(record.get(key)), 'invalid archive digest')
        for key in ('bytes', 'uncompressed_bytes'):
            require(type(record.get(key)) is int and record[key] >= 0, 'invalid archive byte count')
        require(record.get('encoding', 'gzip') == 'gzip', 'unsupported archive encoding')
        member = self.join(self.lifecycle, record['artifact_relative_path'])
        metadata = tuple(record[k] for k in ('sha256', 'bytes', 'uncompressed_sha256', 'uncompressed_bytes'))
        if member in self.descriptors:
            require(self.descriptors[member] == metadata, 'contradictory cached archive descriptor')
            # The directory development mode is mutable. Recheck its cached
            # file signature; ZIP mode is bound to the unchanged ZIP identity.
            with self.open(member):
                pass
        else:
            require(self.stream_hash(member) == metadata[:2], 'compressed archive SHA/size mismatch: ' + member)
            require(self.stream_hash(member, True) == metadata[2:], 'uncompressed archive SHA/size mismatch: ' + member)
            self.descriptors[member] = metadata
            self.archive_checks += 1
        return member

    def archive_json(self, record):
        member = self.archive(record)
        with self.open(member) as raw, gzip.GzipFile(fileobj=raw) as stream:
            value = stream.read(64 * 1024 * 1024 + 1)
        require(len(value) <= 64 * 1024 * 1024, 'compressed JSON exceeds reader bound')
        return loads(value)

    def saved(self, recorded):
        member = self.map(recorded)
        return self.saved_member(member)

    def saved_member(self, member):
        if member in self.members:
            return self.read(member)
        record = self.json(member + '.archive.json')
        archive = self.archive(record)
        with self.open(archive) as raw, gzip.GzipFile(fileobj=raw) as stream:
            value = stream.read(64 * 1024 * 1024 + 1)
        require(len(value) <= 64 * 1024 * 1024, 'saved JSON/log exceeds reader bound')
        return value

    def descriptors_in(self, value):
        if type(value) is dict:
            if {'artifact_relative_path', 'uncompressed_sha256', 'uncompressed_bytes', 'sha256', 'bytes'} <= set(value):
                self.archive(value)
            for child in value.values():
                self.descriptors_in(child)
        elif type(value) is list:
            for child in value:
                self.descriptors_in(child)

    def assert_stable(self):
        if self.zip:
            require(self.signature(self.path) == self.zip_signature, 'artifact ZIP changed during review')
        else:
            for name, signature in self.opened_signatures.items():
                require(name in self.members and self.signature(self.members[name]) == signature,
                        'artifact file changed during review: ' + name)
