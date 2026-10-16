#!/usr/bin/env python3
"""Bounded source-owned Lean transitions; acceptance remains the selected kernel's.

Warm transactions retain immutable Lean and typed-DAG state. Full declaration
SCC reclosure, authenticated baseline reads and full kernel parsing remain O(N).
Only changed export rows and the signed acceptance record are persisted anew.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time
import fcntl

import engine
from build_workloads import ROOTS

HERE = Path(__file__).resolve().parent
TRANSITION = 'mathgraph.lean-source-owned-transition.v1'
GENESIS = 'mathgraph.lean-source-owned-genesis.v1'
REPRESENTATION = 'mathgraph.lean-delta-representation.v1'
SOURCES = ('IncrementalWorkload/Base.lean', 'IncrementalWorkload/Derived.lean',
           'IncrementalWorkload/Leaves.lean', 'Workload.lean', 'lakefile.toml', 'lean-toolchain')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def seal(payload, key):
    """Same issuer and canonical HMAC as the original engine; separate domains."""
    return dict(payload=payload, hmac_sha256=hmac.new(key, engine.encoded(payload), hashlib.sha256).hexdigest())


def authenticate(signed, key, schema):
    if type(signed) is not dict or set(signed) != {'payload', 'hmac_sha256'}:
        raise ValueError('invalid issuer envelope')
    payload = signed['payload']
    if type(payload) is not dict or payload.get('schema') != schema:
        raise ValueError('wrong authority domain')
    expected = hmac.new(key, engine.encoded(payload), hashlib.sha256).hexdigest()
    if type(signed['hmac_sha256']) is not str or not hmac.compare_digest(expected, signed['hmac_sha256']):
        raise ValueError('issuer authentication failed')
    return payload


def sources_at(directory):
    directory = Path(directory)
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*.lean')
              if '.lake' not in p.relative_to(directory).parts}
    if actual != {p for p in SOURCES if p.endswith('.lean')}:
        raise ValueError('source universe changed')
    result = {}
    for name in SOURCES:
        path = directory / name
        if any(p.is_symlink() for p in [path, *path.parents] if p != directory.parent):
            raise ValueError('source symlink is not an owned input')
        raw = path.read_bytes()
        if len(raw) > 1_000_000:
            raise ValueError('source exceeds bounded producer policy')
        result[name] = raw.decode('utf-8')
    return result


def lean_sources(sources):
    return {name: text for name, text in sources.items() if name.endswith('.lean')}


class JsonProcess:
    def __init__(self, command, stderr, timeout=120, env=None):
        self.error = Path(stderr).open('wb')
        self.process = subprocess.Popen([str(x) for x in command], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.error, env=env)
        self.pending = bytearray()
        self.timeout = timeout

    def receive(self):
        deadline = time.monotonic() + self.timeout
        while b'\n' not in self.pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise ValueError('producer/index session timeout')
            data = os.read(self.process.stdout.fileno(), 65536)
            if not data:
                raise ValueError('producer/index session exited without a complete response')
            self.pending.extend(data)
            if len(self.pending) > 32_000_000:
                raise ValueError('producer/index response exceeds bound')
        line, _, rest = self.pending.partition(b'\n')
        self.pending = bytearray(rest)
        result = json.loads(line, object_pairs_hook=engine.strict_object)
        if type(result) is not dict or result.get('status') == 'error':
            raise ValueError('producer/index refused: ' + str(result))
        return result

    def request(self, request):
        self.process.stdin.write(engine.encoded(request) + b'\n')
        self.process.stdin.flush()
        return self.receive()

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.error.close()



def reconstruct_index_patch(baseline, patch):
    """Rebuild an untrusted transport witness against the HMAC-validated base.

    This does not establish acceptance. Full kernel checking and the independent
    fresh-composite typed-index oracle remain separately mandatory.
    """
    if type(baseline) is not dict or type(patch) is not dict:
        raise ValueError('index patch objects required')
    if set(patch) != {'schema', 'count', 'declarations', 'builtins'} or (
            patch['schema'] != 'mathgraph.export-identity-baseline-patch.v1'):
        raise ValueError('unsupported or ambiguous typed-index patch')
    original = baseline.get('declarations')
    if (type(original) is not list or type(baseline.get('count')) is not int or
            type(patch['count']) is not int or patch['count'] != baseline['count'] or
            len(original) != baseline['count']):
        raise ValueError('typed-index patch count mismatch')
    entries, builtin_changes = patch['declarations'], patch['builtins']
    if type(entries) is not list or type(builtin_changes) is not dict:
        raise ValueError('malformed typed-index patch payload')
    out = dict(baseline)
    declarations = list(original)
    previous = -1
    keys = set(original[0]) if original else set()
    for row in entries:
        if type(row) is not dict or set(row) != keys:
            raise ValueError('malformed changed declaration identity')
        pos = row.get('index')
        if type(pos) is not int or not previous < pos < len(declarations):
            raise ValueError('duplicate, out-of-order or invalid patch declaration')
        past = original[pos]
        for field in ('key', 'name', 'kind', 'deps', 'index'):
            if row.get(field) != past.get(field) or type(row.get(field)) is not type(past.get(field)):
                raise ValueError('identity patch silently changed dependency topology')
        for field in ('own', 'closure'):
            value = row.get(field)
            if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('invalid cryptographic identity witness')
        declarations[pos] = row
        previous = pos
    old_builtins = baseline.get('builtins')
    if type(old_builtins) is not dict:
        raise ValueError('missing baseline builtin policy')
    builtins = dict(old_builtins)
    for name, value in builtin_changes.items():
        if name not in old_builtins or type(value) is not list or len(value) != 2:
            raise ValueError('invalid changed builtin witness')
        for part in value:
            if part is not None and (type(part) is not str or len(part) != 64 or
                                      any(c not in '0123456789abcdef' for c in part)):
                raise ValueError('invalid builtin identity fingerprint')
        if value[0] != old_builtins[name][0]:
            raise ValueError('builtin key changed unexpectedly')
        builtins[name] = value
    out['declarations'] = declarations
    out['builtins'] = builtins
    return out

class DeltaSession:
    """One authenticated baseline-anchored transaction, then close or restart.

    The private producer process owns its imported Lean environment. Each input
    capture reads the complete six-file application source universe. Imported
    proof state stays immutable in that process; restart reconstructs it and
    requires the exact pinned baseline export and authenticated prior evidence.
    """
    def __init__(self, root, workloads, producer, checker, indexer, index_session,
                 authority_key, index_mode='retained', sparse_index_wire=False):
        # Mode is an explicit, authenticated A/B policy rather than an
        # unrecorded subprocess switch. Both paths must produce the same index.
        if index_mode not in ('retained', 'full'):
            raise ValueError('unsupported identity finish mode')
        self.index_mode = index_mode
        if type(sparse_index_wire) is not bool or (sparse_index_wire and index_mode != 'retained'):
            raise ValueError('sparse index wire requires retained identity mode')
        self.sparse_index_wire = sparse_index_wire
        self.root, self.workloads = Path(root).resolve(), Path(workloads).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.key_path = Path(authority_key).resolve()
        if self.root == self.key_path or self.root in self.key_path.parents:
            raise ValueError('issuer secret must be outside published artifacts')
        self.key = self.key_path.read_bytes()
        if len(self.key) != 32:
            raise ValueError('issuer key must have32bytes')
        self.manifest = json.loads((self.workloads / 'manifest.json').read_bytes())
        self.pins = json.loads((HERE / 'pins.json').read_bytes())
        self.profile = self.manifest.get('profile', 'original-v1')
        self.roots, self.export_pins = ROOTS, self.pins['export_sha256']
        self.profile_policy_sha256 = None
        if self.profile != 'original-v1':
            profile_policy = (HERE / 'delta-pins.json').read_bytes()
            self.profile_policy_sha256 = sha(profile_policy)
            expanded = json.loads(profile_policy)
            if self.profile != expanded['profile']:
                raise ValueError('unknown producer workload profile')
            root_bytes = (HERE / expanded['roots_file']).read_bytes()
            if sha(root_bytes) != expanded['roots_sha256']:
                raise ValueError('expanded source root-list pin changed')
            self.roots = json.loads(root_bytes)
            self.export_pins = expanded['export_sha256']
            if self.manifest.get('roots') != self.roots or len(self.roots) != expanded['root_count']:
                raise ValueError('manifest root universe differs from profile policy')
        for variant, info in self.manifest['variants'].items():
            if variant not in self.export_pins or info['sha256'] != self.export_pins[variant]:
                raise ValueError('manifest export differs from workload pin: ' + variant)
        lean_binary = Path(self.manifest['tools']['lean']['path'])
        if sha(lean_binary.read_bytes()) != self.pins['lean_release_binaries_sha256']['lean']:
            raise ValueError('producer Lean runtime differs from policy')
        self.producer_environment = dict(os.environ, LEAN_SYSROOT=str(lean_binary.parent.parent),
            LEAN_PATH='', PATH=str(lean_binary.parent)+os.pathsep+os.environ.get('PATH',''))
        self.private = tempfile.TemporaryDirectory(prefix='mathgraph-source-owner-')
        self.temp = Path(self.private.name)
        self.tools, self.tool_hashes = {}, {}
        for name, source in [('producer', producer), ('checker', checker), ('indexer', indexer),
                             ('index_session', index_session)]:
            destination = self.temp / name
            shutil.copyfile(source, destination)
            destination.chmod(0o500)
            self.tools[name] = destination
            self.tool_hashes[name] = sha(destination.read_bytes())
        self.producer = self.index = None
        self.fd = None
        self.used = False
        self.snapshot_path = None
        self.cache = self.root / 'cache'
        self.baseline_cache = self.root / 'baseline-cache'
        self.baseline_sources = sources_at(self.workloads / 'baseline' / 'source')
        for name, expected in self.pins['workload_sources_sha256'].items():
            if sha(self.baseline_sources[name].encode()) != expected:
                raise ValueError('pinned baseline source changed: ' + name)
        self.source_root = engine.digest(self.baseline_sources)
        self.delta_provenance = dict(schema='mathgraph.source-owned-producer-policy.v1',
            tools=self.tool_hashes, adapter_sha256=sha(Path(__file__).read_bytes()),
            engine_sha256=sha((HERE / 'engine.py').read_bytes()), pins_sha256=sha((HERE / 'pins.json').read_bytes()),
            profile=self.profile, profile_policy_sha256=self.profile_policy_sha256, roots=self.roots,
            source_policy='complete-six-file-capture;fixed-imports;one-simple-replacement-set',
            representation='baseline-DAG;append-only-delta-DAG;original-declaration-schedule',
            identity_finish_mode=self.index_mode)
        if self.sparse_index_wire:
            self.delta_provenance['identity_index_wire'] = 'baseline_patch_v1'

    def start(self):
        tick, cpu = time.perf_counter(), self.cpu_time()
        initial_export = self.temp / 'baseline.ndjson'
        init = self.temp / 'init.json'
        init.write_bytes(engine.encoded(dict(source_files=lean_sources(self.baseline_sources),
                                            profile=self.profile, roots=self.roots,
                                            baseline_export=str(initial_export))))
        self.producer = JsonProcess([self.tools['producer'], init], self.root / 'producer.stderr',
                                    env=self.producer_environment)
        ready = self.producer.receive()
        if (ready.get('status') != 'ready' or ready.get('profile') != self.profile or
                ready.get('roots') != self.roots):
            raise ValueError('producer did not establish a baseline')
        produced = initial_export.read_bytes()
        expected = self.export_pins['baseline']
        if sha(produced) != expected:
            raise ValueError('source-owned baseline differs from pinned genuine Lean export')
        state_path = self.root / 'session-state.json'
        if state_path.exists():
            state = json.loads(state_path.read_bytes(), object_pairs_hook=engine.strict_object)
            self.base_id = state['base_evidence_id']
            raw = (self.baseline_cache / 'records' / (self.base_id + '.json')).read_bytes()
            self.old = engine.authenticate_record(raw, self.base_id, self.key)
            signed = self._object('genesis', state['genesis_id'], '.json')
            genesis = authenticate(json.loads(signed, object_pairs_hook=engine.strict_object), self.key, GENESIS)
            if genesis != self._genesis(self.base_id):
                raise ValueError('source-owner genesis provenance mismatch')
            self.baseline_result = dict(status='VERIFIED', evidence_id=self.base_id,
                                        scope='authenticated_prior_baseline_not_a_new_full_check')
        else:
            self.baseline_result = engine.verify_incremental(None, initial_export,
                dict(cache=str(self.baseline_cache), authority_key=str(self.key_path),
                     checker=str(self.tools['checker']), indexer=str(self.tools['indexer']),
                     identity_backend='native'))
            if self.baseline_result['status'] != 'VERIFIED':
                raise ValueError('fresh baseline kernel check failed')
            self.base_id = self.baseline_result['evidence_id']
            self.old = engine.authenticate_record((self.baseline_cache / 'records' /
                (self.base_id + '.json')).read_bytes(), self.base_id, self.key)
            genesis = engine.encoded(seal(self._genesis(self.base_id), self.key))
            genesis_id = self._put('genesis', genesis, '.json')
            engine.immutable_write(state_path, engine.encoded(dict(base_evidence_id=self.base_id,
                                                                  genesis_id=genesis_id)))
        if self.old['export_sha256'] != expected:
            raise ValueError('authenticated baseline export mismatch')
        self._baseline_bytes()
        # Layout is reconstructed from authenticated bytes at every cold start;
        # ordinary untrusted storage never authenticates a cached offset table.
        self.layout = self._layout(produced)
        configuration = dict(self.old['provenance']['configuration'], export_file_path=str(initial_export))
        config = self.temp / 'index-config.json'
        config.write_bytes(engine.encoded(configuration))
        command = [self.tools['index_session'], config]
        if self.index_mode == 'full':
            command.append('--full-index')
        if self.sparse_index_wire:
            command.append('--sparse-response')
        self.index = JsonProcess(command, self.root / 'index.stderr')
        indexed = self.index.receive()
        if indexed.get('status') != 'ready' or engine.encoded(indexed.get('index')) != engine.encoded(self.old['index']):
            raise ValueError('retained typed index disagrees with authenticated baseline')
        self.start_report = dict(status='READY', base_evidence_id=self.base_id,
            source_root=self.source_root, producer=ready,
            wall_seconds=time.perf_counter()-tick, cpu_seconds=self.cpu_time()-cpu,
            delta_provenance=self.delta_provenance)
        return self.start_report

    def cpu_time(self):
        total = engine.cpu_time()
        # RUSAGE_CHILDREN omits still-running producer/index sessions. Their
        # procfs counters include completed grandchildren, in clock ticks.
        for daemon in [self.producer, self.index]:
            if daemon is None:
                continue
            try:
                fields = Path(f'/proc/{daemon.process.pid}/stat').read_text().rsplit(')', 1)[1].split()
                total += sum(int(x) for x in fields[11:15]) / os.sysconf('SC_CLK_TCK')
            except FileNotFoundError:
                pass
        return total

    def memory_observation(self):
        result = dict(scope='Post-phase procfs samples; VmHWM is cumulative since process startup; '
                            'not exact phase peaks or aggregate memory savings', processes={})
        for label, pid in [('adapter', os.getpid()),
            ('producer', self.producer.process.pid if self.producer else None),
            ('index', self.index.process.pid if self.index else None)]:
            if pid is None:
                continue
            try:
                rows = Path(f'/proc/{pid}/status').read_text().splitlines()
                result['processes'][label] = {line.split(':',1)[0]: int(line.split()[1])
                    for line in rows if line.split(':',1)[0] in ('VmRSS','VmHWM','RssAnon','RssFile')}
            except FileNotFoundError:
                result['processes'][label] = None
        return result

    def _genesis(self, evidence):
        return dict(schema=GENESIS, base_evidence_id=evidence, source_root=self.source_root,
                    export_sha256=self.export_pins['baseline'], provenance=self.delta_provenance)

    def _baseline_bytes(self):
        raw = (self.baseline_cache / 'records' / (self.base_id + '.json')).read_bytes()
        # The pinned content address and HMAC identify the exact same payload;
        # re-encoding the already loaded payload twice adds no validity premise.
        engine.authenticate_record(raw, self.base_id, self.key)
        data = (self.baseline_cache / 'exports' / (self.old['export_sha256'] + '.ndjson')).read_bytes()
        if sha(data) != self.old['export_sha256']:
            raise ValueError('baseline storage corruption')
        return data

    def _put(self, category, raw, suffix):
        ident = sha(raw)
        engine.immutable_write(self.cache / category / (ident + suffix), raw)
        return ident

    def _object(self, category, ident, suffix):
        if type(ident) is not str or len(ident) != 64 or any(c not in '0123456789abcdef' for c in ident):
            raise ValueError('invalid content address')
        raw = (self.cache / category / (ident + suffix)).read_bytes()
        if sha(raw) != ident:
            raise ValueError('delta storage corruption: ' + category)
        return raw

    @staticmethod
    def _layout(data):
        names = {0: ''}
        dags, declarations = [], []
        offset = 0
        for line in data.splitlines(keepends=True):
            row = json.loads(line, object_pairs_hook=engine.strict_object)
            if 'in' in row:
                part = row.get('str', row.get('num'))
                prefix = names[part['pre']]
                names[row['in']] = (prefix + '.' if prefix else '') + str(part.get('str', part.get('i')))
            tag = next((k for k in row if k in engine.SIMPLE | {'quot', 'inductive'}), None)
            if tag:
                value = row[tag]
                name = names[value['name']] if tag != 'inductive' else None
                declarations.append((name, tag, offset, len(line)))
            elif dags and sum(dags[-1]) == offset:
                start, length = dags[-1]
                dags[-1] = (start, length+len(line))
            else:
                dags.append((offset, len(line)))
            offset += len(line)
        return dict(names=names, dags=dags, declarations=declarations)

    def prepare(self, source_dir, patch, claimed_names):
        start, cpu = time.perf_counter(), self.cpu_time()
        sources = sources_at(source_dir)
        expected = dict(self.baseline_sources)
        if patch is not None:
            filename, before, after = patch
            if filename not in SOURCES[:3]:
                raise ValueError('configuration/import-root source changes are outside producer policy')
            if filename not in expected or expected[filename].count(before) != 1:
                raise ValueError('ambiguous or foreign source patch')
            expected[filename] = expected[filename].replace(before, after)
        if sources != expected:
            raise ValueError('source modifications outside the reported patch')
        delta_path = self.temp / 'producer-delta.ndjson'
        report = self.producer.request(dict(source_files=lean_sources(sources), delta_path=str(delta_path),
                                            expected_changed_names=list(claimed_names)))
        if report.get('status') != 'delta' or sorted(report.get('changed_names', [])) != sorted(claimed_names):
            raise ValueError('incomplete source-owned environment transition')
        delta = delta_path.read_bytes()
        payload = dict(schema=TRANSITION, base_evidence_id=self.base_id,
            base_export_sha256=self.old['export_sha256'], baseline_source_root=self.source_root,
            source_root=engine.digest(sources), delta_sha256=sha(delta),
            changed_names=sorted(claimed_names), provenance=self.delta_provenance,
            producer_report=report)
        return dict(attestation=seal(payload, self.key), delta_bytes=delta, producer_report=report,
                    prepare_wall_seconds=time.perf_counter()-start,
                    prepare_cpu_seconds=self.cpu_time()-cpu, memory_after_producer=self.memory_observation())

    def _materialize(self, baseline, delta, changed_names):
        names = dict(self.layout['names'])
        dags, replacements = [], {}
        for line in delta.splitlines(keepends=True):
            row = json.loads(line, object_pairs_hook=engine.strict_object)
            if 'meta' in row or 'inductive' in row or 'quot' in row:
                raise ValueError('unsupported global/schedule transition')
            if 'in' in row:
                part = row.get('str', row.get('num'))
                prefix = names[part['pre']]
                if row['in'] in names:
                    raise ValueError('attempted old name DAG mutation')
                names[row['in']] = (prefix + '.' if prefix else '') + str(part.get('str', part.get('i')))
            kinds = set(row) & engine.SIMPLE
            if kinds:
                if len(kinds) != 1 or len(row) != 1:
                    raise ValueError('ambiguous declaration delta')
                kind = next(iter(kinds))
                name = names[row[kind]['name']]
                if name in replacements:
                    raise ValueError('duplicate declaration replacement')
                replacements[name] = (kind, line)
            else:
                dags.append(line)
        if set(replacements) != set(changed_names):
            raise ValueError('declared changes differ from export mutations')
        if self.fd is not None:
            os.close(self.fd)
        self.fd = os.memfd_create('mathgraph-verified-delta', os.MFD_ALLOW_SEALING)
        digest = hashlib.sha256()
        count = 0
        def write(raw):
            nonlocal count
            digest.update(raw)
            count += len(raw)
            view = memoryview(raw)
            while view:
                n = os.write(self.fd, view)
                view = view[n:]
        view = memoryview(baseline)
        for start, length in self.layout['dags']:
            write(view[start:start+length])
        for raw in dags:
            write(raw)
        seen = set()
        for name, kind, start, length in self.layout['declarations']:
            if name in replacements:
                replacement_kind, raw = replacements[name]
                if replacement_kind != kind:
                    raise ValueError('declaration kind changed')
                write(raw)
                seen.add(name)
            else:
                write(view[start:start+length])
        if seen != set(replacements):
            raise ValueError('new declaration or schedule change')
        # Linux UAPI constants; some Python distributions omit their names.
        seals = 0x0001 | 0x0002 | 0x0004 | 0x0008
        fcntl.fcntl(self.fd, getattr(fcntl, 'F_ADD_SEALS', 1033), seals)
        if fcntl.fcntl(self.fd, getattr(fcntl, 'F_GET_SEALS', 1034)) & seals != seals:
            raise ValueError('composite input could not be sealed')
        self.snapshot_path = f'/proc/{os.getpid()}/fd/{self.fd}'
        return digest.hexdigest(), count

    def validate_apply(self, transaction):
        if self.used:
            raise ValueError('one baseline-anchored transaction per session')
        self.used = True
        start, cpu = time.perf_counter(), self.cpu_time()
        payload = authenticate(transaction['attestation'], self.key, TRANSITION)
        if (payload['base_evidence_id'] != self.base_id or
            payload['base_export_sha256'] != self.old['export_sha256'] or
            payload['baseline_source_root'] != self.source_root or
            payload['provenance'] != self.delta_provenance):
            raise ValueError('transition environment/version/base mismatch')
        delta = transaction['delta_bytes']
        if type(delta) is not bytes or sha(delta) != payload['delta_sha256']:
            raise ValueError('changed-byte integrity failed')
        phase_cpu, memory = {}, dict(producer=transaction.get('memory_after_producer'))
        tick, phase_start = time.perf_counter(), self.cpu_time()
        baseline = self._baseline_bytes()
        validation = time.perf_counter()-tick
        phase_cpu['baseline_validation_cpu_seconds'] = self.cpu_time()-phase_start
        memory['validation'] = self.memory_observation()
        path = self.temp / 'authenticated-delta.ndjson'
        path.write_bytes(delta)
        tick, phase_start = time.perf_counter(), self.cpu_time()
        update = self.index.request(dict(delta_path=str(path)))
        if update.get('status') != 'indexed' or sorted(update.get('replaced_names', [])) != payload['changed_names']:
            raise ValueError('typed index mutation witness disagrees')
        if self.sparse_index_wire and update.get('index_wire') == 'baseline_patch_v1':
            if 'index' in update:
                raise ValueError('ambiguous full and sparse index response')
            index = reconstruct_index_patch(self.old['index'], update['index_patch'])
        else:
            if self.sparse_index_wire and update.get('index_wire') != 'full_index_v1':
                raise ValueError('unrecognized sparse-index wire response')
            if 'index_patch' in update:
                raise ValueError('unexpected index patch on full transport')
            index = update['index']
        identity = time.perf_counter()-tick
        phase_cpu['identity_update_cpu_seconds'] = self.cpu_time()-phase_start
        memory['identity'] = self.memory_observation()
        tick, phase_start = time.perf_counter(), self.cpu_time()
        export_hash, export_bytes = self._materialize(baseline, delta, payload['changed_names'])
        materialization = time.perf_counter()-tick
        phase_cpu['materialization_and_hash_cpu_seconds'] = self.cpu_time()-phase_start
        memory['materialization'] = self.memory_observation()
        selected, decisions = engine.reuse_decisions(self.old, index, self.old['provenance'], self.base_id)
        config = self.temp / 'selected-config.json'
        config.write_bytes(engine.encoded(dict(self.old['provenance']['configuration'],
                                              export_file_path=self.snapshot_path)))
        indices = self.temp / 'indices.json'
        indices.write_bytes(engine.encoded(selected))
        tick, phase_start = time.perf_counter(), self.cpu_time()
        # Always parse changed representation bytes, including unused DAG rows.
        checked = subprocess.run([str(self.tools['checker']), str(config), str(indices)],
                                 capture_output=True, timeout=120)
        checking = time.perf_counter()-tick
        phase_cpu['checking_cpu_seconds'] = self.cpu_time()-phase_start
        memory['checking'] = self.memory_observation()
        status = 'VERIFIED' if checked.returncode == 0 else ('UNKNOWN' if checked.returncode in (2,124) else 'REJECTED')
        actual = None
        if checked.returncode == 0:
            proof = json.loads(checked.stdout, object_pairs_hook=engine.strict_object)
            if proof['checked'] != len(selected) or proof['total_declarations'] != index['count']:
                raise ValueError('actual kernel obligation count mismatch')
            actual = proof['checked']
        for decision in decisions:
            if decision['status'] == 'UNKNOWN' and status == 'VERIFIED':
                decision['status'] = 'VERIFIED_NEW'
        tick, phase_start = time.perf_counter(), self.cpu_time()
        receipt_id = None
        if status == 'VERIFIED':
            delta_id = self._put('deltas', delta, '.ndjson')
            attestation_id = self._put('transitions', engine.encoded(transaction['attestation']), '.json')
            representation = dict(schema=REPRESENTATION, base_evidence_id=self.base_id,
                delta_sha256=delta_id, transition_id=attestation_id, export_sha256=export_hash)
            representation_id = self._put('representations', engine.encoded(representation), '.json')
            accepted = dict(schema=engine.SCHEMA, status=status, export_sha256=export_hash,
                index=index, provenance=self.old['provenance'], previous_evidence=self.base_id,
                checked_indices=selected, reused_indices=[d['index'] for d in decisions if d['status']=='VERIFIED_REUSED'],
                producer_provenance=self.delta_provenance, delta_representation=representation_id)
            receipt_id = self._put('records', engine.encoded(seal(accepted, self.key)), '.json')
            for decision in decisions:
                if decision['status'] == 'VERIFIED_NEW':
                    decision['evidence_id'] = receipt_id
        persistence = time.perf_counter()-tick
        phase_cpu['persistence_cpu_seconds'] = self.cpu_time()-phase_start
        memory['persistence'] = self.memory_observation()
        result = dict(schema=engine.SCHEMA, status=status, evidence_id=receipt_id,
            export_sha256=export_hash, previous_evidence=self.base_id, decisions=decisions,
            counts=dict(total=index['count'], scheduled=len(selected), rechecked=actual,
                        reused=index['count']-len(selected), invalidated=len(selected)),
            checker_result=dict(code=checked.returncode, stdout=checked.stdout.decode(errors='replace'),
                                stderr=checked.stderr.decode(errors='replace')),
            provenance=self.old['provenance'], producer_provenance=self.delta_provenance,
            producer_report=transaction['producer_report'], typed_update={k:v for k,v in update.items() if k!='index'},
            representation=dict(delta_bytes=len(delta), export_bytes=export_bytes,
                                full_export_disk_bytes_written=0, immutable_memfd=True),
            timings=dict(producer_seconds=transaction.get('prepare_wall_seconds',0),
                baseline_validation_seconds=validation, identity_update_seconds=identity,
                materialization_and_hash_seconds=materialization, checking_seconds=checking,
                persistence_seconds=persistence, consumer_seconds=time.perf_counter()-start,
                consumer_cpu_seconds=self.cpu_time()-cpu, **phase_cpu), memory=memory,
            cpu_measurement='Adapter + completed children + live producer/index procfs ticks; '
                            'live counters have SC_CLK_TCK granularity', action_authorization='NONE')
        result['timings']['end_to_end_seconds'] = result['timings']['producer_seconds'] + result['timings']['consumer_seconds']
        result['timings']['end_to_end_cpu_seconds'] = transaction.get('prepare_cpu_seconds',0) + result['timings']['consumer_cpu_seconds']
        self.last_transaction, self.result = transaction, result
        return result

    def apply(self, source_dir, patch, claimed_names):
        start, cpu = time.perf_counter(), self.cpu_time()
        try:
            result = self.validate_apply(self.prepare(source_dir, patch, claimed_names))
        except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
            result = dict(status='UNKNOWN', evidence_id=None, reason=str(error),
                          counts=None, decisions=[], action_authorization='NONE')
        result.setdefault('timings', {})['end_to_end_seconds'] = time.perf_counter()-start
        result['timings']['end_to_end_cpu_seconds'] = self.cpu_time()-cpu
        return result

    def replay(self, receipt_id):
        raw = self._object('records', receipt_id, '.json')
        record = engine.authenticate_record(raw, receipt_id, self.key)
        if record.get('producer_provenance') != self.delta_provenance:
            raise ValueError('accepted delta toolchain/provenance mismatch')
        representation = json.loads(self._object('representations', record['delta_representation'], '.json'),
                                    object_pairs_hook=engine.strict_object)
        if representation.get('schema') != REPRESENTATION or representation['base_evidence_id'] != self.base_id:
            raise ValueError('representation base/schema mismatch')
        delta = self._object('deltas', representation['delta_sha256'], '.ndjson')
        attestation = json.loads(self._object('transitions', representation['transition_id'], '.json'),
                                 object_pairs_hook=engine.strict_object)
        payload = authenticate(attestation, self.key, TRANSITION)
        result = self.validate_apply(dict(attestation=attestation, delta_bytes=delta,
                                         producer_report=payload['producer_report']))
        if (result['status'] != 'VERIFIED' or result['export_sha256'] != record['export_sha256'] or
            result['export_sha256'] != representation['export_sha256'] or
            result['counts']['scheduled'] != len(record['checked_indices'])):
            raise ValueError('persisted delta replay mismatch')
        return result

    def close(self):
        for process in [self.producer, self.index]:
            if process is not None:
                process.close()
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.private.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
