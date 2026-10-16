#!/usr/bin/env python3
"""Independent producer-delta qualification and paired warm-session economics.

The timed update starts after separately measured baseline/session setup. Every
direct full-check comparator reads the very same live sealed composite snapshot.
Fresh full native/Python indexes and real Rust/C++/paranoid commands are oracles;
the mutable delta controller is never its own correctness oracle.
"""
import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import json
import math
import os
import platform
from pathlib import Path
import random
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

from build_workloads import EDITS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
QUALIFIED_SOURCE = 'c5ab12699338aa57b7e9d48b15d4a7409e453c7b'
VARIANTS = ('early-definition', 'unrelated-definition', 'theorem-leaf', 'baseline')
EXPECTED = {'baseline': (0, 3436), 'early-definition': (413, 3023),
            'unrelated-definition': (1, 3435), 'theorem-leaf': (1, 3435)}
NAMES = {'baseline': [], 'early-definition': ['IncrementalWorkload.early'],
         'unrelated-definition': ['IncrementalWorkload.unrelated'],
         'theorem-leaf': ['IncrementalWorkload.leaf']}
STANDARD_AXIOMS = ['propext', 'Classical.choice', 'Quot.sound']
SOURCE_PATHS = ('IncrementalWorkload/Base.lean',
                'IncrementalWorkload/Derived.lean',
                'IncrementalWorkload/Leaves.lean', 'Workload.lean',
                'lakefile.toml', 'lean-toolchain')


def canonical(value):
    """Typed JSON equality: Python bool/int equality must not conflate inputs."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            value.update(chunk)
    return value.hexdigest()


def safe(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return dict(bytes=len(value), sha256=hashlib.sha256(value).hexdigest())
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    return value


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe(value), indent=2, ensure_ascii=True,
                               allow_nan=False) + '\n')


def command_run(command, log, timeout=900, cwd=None):
    """Time command execution, then persist output outside the measured interval.

    Wall time includes fresh process creation and output capture. It excludes
    this harness's subsequent log persistence. No polling sleep is added.
    """
    command = [str(part) for part in command]
    child_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    try:
        run = subprocess.run(command, capture_output=True, timeout=timeout, cwd=cwd)
        stdout, stderr = run.stdout, run.stderr
        code, timed_out = run.returncode, False
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b'', error.stderr or b''
        code, timed_out = None, True
    elapsed = time.perf_counter() - start
    child_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    out, err = log.with_suffix('.stdout'), log.with_suffix('.stderr')
    out.write_bytes(stdout)
    err.write_bytes(stderr)
    record = dict(command=command, cwd=str(cwd) if cwd else None,
                  returncode=code, timed_out=timed_out, wall_seconds=elapsed,
                  completed_child_cpu_seconds=(child_after.ru_utime + child_after.ru_stime -
                                               child_before.ru_utime - child_before.ru_stime),
                  cpu_scope='completed child CPU delta; excludes live retained daemons',
                  stdout_path=str(out), stderr_path=str(err),
                  stdout_sha256=file_hash(out), stderr_sha256=file_hash(err))
    write(log.with_suffix('.json'), record)
    return record, stdout


def configuration(export):
    return dict(export_file_path=str(export), use_stdin=False,
                permitted_axioms=STANDARD_AXIOMS, unpermitted_axiom_hard_error=True,
                num_threads=1, nat_extension=True, string_extension=True,
                print_success_message=True)


def fresh_index(export, indexer, out, python=False):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if python:
        # The normal qualified index loader is the only engine import. No
        # mutable reuse/authentication/controller function certifies its result.
        script = ('import json,sys; from pathlib import Path; import engine; '
                  'print(json.dumps(engine.make_index(Path(sys.argv[1])), '
                  'sort_keys=True,separators=(",",":"),ensure_ascii=True))')
        command = [sys.executable, '-c', script, str(export)]
    else:
        config = out / 'config.json'
        write(config, configuration(export))
        command = [indexer, config]
    record, stdout = command_run(command, out / 'process', cwd=HERE)
    if record['timed_out'] or record['returncode'] != 0:
        raise ValueError('fresh full index failed: ' + str(record))
    value = json.loads(stdout)
    if not isinstance(value, dict) or set(value) != {
            'meta', 'declarations', 'count', 'builtins', 'complex', 'schedule'}:
        raise ValueError('fresh full index protocol is incomplete')
    write(out / 'index.json', value)
    return value, record


def selected_report(result):
    actual = result.get('checker_result', {})
    stdout = actual.get('stdout')
    if not isinstance(stdout, str):
        raise ValueError('missing actual selected-checker output')
    parsed = json.loads(stdout)
    if (not isinstance(parsed, dict) or type(parsed.get('checked')) is not int or
            type(parsed.get('total_declarations')) is not int or
            parsed.get('scope') != 'selected_obligations_under_caller_trusted_environment'):
        raise ValueError('invalid actual selected-checker output')
    return parsed


def independent_partition(old, current):
    """Finite replay of applicability from independently constructed full indexes.

    This audit never accepts a proof. It tests the qualified predicate's two
    authorized identity conditions, including complex-prefix/global boundaries.
    Kernel acceptance is established only by separately executed real checkers.
    """
    globals_same = (canonical(old['meta']) == canonical(current['meta']) and
                    canonical(old['builtins']) == canonical(current['builtins']) and
                    old['complex'] == current['complex'])
    schedule_same = globals_same and old['schedule'] == current['schedule']
    priors = {row['key']: row for row in old['declarations']}
    prefix = True
    reused, checked = [], []
    for row in current['declarations']:
        prior = priors.get(row['key'])
        prefix = bool(prefix and globals_same and prior is not None and
                      prior['index'] == row['index'] and prior['own'] == row['own'])
        local = bool(schedule_same and row['kind'] in ('axiom', 'def', 'thm', 'opaque')
                     and prior is not None and prior['own'] == row['own'] and
                     prior['closure'] == row['closure'])
        (reused if prefix or local else checked).append(row['index'])
    return checked, reused


def audit_partition(result, old, current):
    if result.get('status') != 'VERIFIED':
        raise ValueError('positive source update did not verify')
    expected_checked, expected_reused = independent_partition(old, current)
    decisions = result.get('decisions')
    if not isinstance(decisions, list) or len(decisions) != current['count']:
        raise ValueError('complete adapter partition missing')
    if len({row.get('index') for row in decisions}) != len(decisions):
        raise ValueError('duplicate decision index')
    checked = [row['index'] for row in decisions if row['status'] == 'VERIFIED_NEW']
    reused = [row['index'] for row in decisions if row['status'] == 'VERIFIED_REUSED']
    if checked != expected_checked or reused != expected_reused:
        raise ValueError('adapter partition differs from independent full-index replay')
    for decision, declaration in zip(decisions, current['declarations']):
        witness = dict(own=declaration['own'], closure=declaration['closure'],
                       direct=declaration['deps'])
        if (decision['name'] != declaration['name'] or
                decision['index'] != declaration['index'] or
                canonical(decision.get('dependency_witness')) != canonical(witness)):
            raise ValueError('adapter decision does not carry the actual full-index witness')
    counts = result.get('counts', {})
    if (counts.get('total') != current['count'] or
            counts.get('rechecked') != len(checked) or
            counts.get('reused') != len(reused) or
            counts.get('scheduled') != len(checked)):
        raise ValueError('adapter counts differ from actual partition')
    report = selected_report(result)
    if report['checked'] != len(checked) or report['total_declarations'] != current['count']:
        raise ValueError('actual kernel work does not match scheduled obligations')
    return dict(actual_kernel_checked=report['checked'],
                actual_kernel_total=report['total_declarations'],
                independently_replayed_reused=len(reused),
                checked_indices=checked, reused_indices=reused,
                identity_witnesses_checked=len(decisions))


def sealed_snapshot(path):
    path = Path(path)
    with path.open('rb') as stream:
        seals = fcntl.fcntl(stream.fileno(), getattr(fcntl, 'F_GET_SEALS', 1034))
    # Linux UAPI numbers also support distributions omitting Python's names.
    required = (getattr(fcntl, 'F_SEAL_WRITE', 8) | getattr(fcntl, 'F_SEAL_GROW', 4) |
                getattr(fcntl, 'F_SEAL_SHRINK', 2) | getattr(fcntl, 'F_SEAL_SEAL', 1))
    if seals & required != required:
        raise ValueError('composite snapshot is not completely sealed')
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=file_hash(path), seals=seals, required_seals=required)


def audit_receipt(root, result, current_index, key):
    """Independently read and authenticate actual persisted acceptance objects."""
    cache = Path(root) / 'cache'
    def read(category, identity, suffix):
        if (type(identity) is not str or len(identity) != 64 or
                any(c not in '0123456789abcdef' for c in identity)):
            raise ValueError('invalid independently audited content address')
        path = cache / category / (identity + suffix)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != identity:
            raise ValueError('persisted content address mismatch: ' + category)
        return raw
    def authenticated(raw, schema):
        value = json.loads(raw)
        if set(value) != {'payload', 'hmac_sha256'}:
            raise ValueError('persisted issuer envelope mismatch')
        payload = value['payload']
        expected = hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()
        if payload.get('schema') != schema or not hmac.compare_digest(
                value['hmac_sha256'], expected):
            raise ValueError('persisted issuer authentication mismatch')
        return payload
    raw_receipt = read('records', result['evidence_id'], '.json')
    envelope = json.loads(raw_receipt, object_pairs_hook=__import__('engine').strict_object)
    signed_schema = envelope.get('payload', {}).get('schema')
    if signed_schema == 'mathgraph.incremental-lean.sparse-accepted.v1':
        # The independently reconstructed full composite index is this
        # auditor's authority. The sparse receipt may not substitute an
        # unverified local patch for either actual checking or this oracle.
        from producer_delta import authenticate_sparse_acceptance
        prior_id = result['previous_evidence']
        prior = Path(root) / 'baseline-cache' / 'records' / (prior_id + '.json')
        raw_prior = prior.read_bytes()
        original = __import__('engine').authenticate_record(raw_prior, prior_id, key)
        accepted = authenticate_sparse_acceptance(raw_receipt, result['evidence_id'], key, original)
        contains_complete_index = False
    else:
        accepted = authenticated(raw_receipt, 'mathgraph.incremental-lean.v1')
        contains_complete_index = True
    if (accepted['status'] != 'VERIFIED' or
            accepted['export_sha256'] != result['export_sha256'] or
            canonical(accepted['index']) != canonical(current_index)):
        raise ValueError('persisted acceptance does not name actual full-index result')
    checked = [row['index'] for row in result['decisions'] if row['status'] == 'VERIFIED_NEW']
    reused = [row['index'] for row in result['decisions'] if row['status'] == 'VERIFIED_REUSED']
    if accepted['checked_indices'] != checked or accepted['reused_indices'] != reused:
        raise ValueError('persisted partition differs from actual kernel/identity partition')
    representation = json.loads(read('representations', accepted['delta_representation'], '.json'))
    if (representation['schema'] != 'mathgraph.lean-delta-representation.v1' or
            representation['export_sha256'] != result['export_sha256'] or
            representation['base_evidence_id'] != result['previous_evidence']):
        raise ValueError('persisted representation does not bind actual old/new inputs')
    transition = authenticated(read('transitions', representation['transition_id'], '.json'),
                               'mathgraph.lean-source-owned-transition.v1')
    delta = read('deltas', representation['delta_sha256'], '.ndjson')
    if (transition['delta_sha256'] != hashlib.sha256(delta).hexdigest() or
            transition['base_evidence_id'] != result['previous_evidence'] or
            canonical(transition['provenance']) != canonical(result['producer_provenance'])):
        raise ValueError('persisted source transition does not bind actual delta/provenance')
    return dict(issuer_hmac_valid=True, all_content_addresses_valid=True,
                receipt_bytes=len(raw_receipt), delta_bytes=len(delta),
                contains_complete_index=contains_complete_index,
                receipt_schema=signed_schema,
                scope='authenticates issued acceptance, not a proof of producer correctness')


def paired_economics(pairs, seed=20261016, bootstrap_repetitions=10000):
    if not pairs:
        return dict(passed=False, status='UNKNOWN_NO_COMPLETE_PAIRS')
    update = [pair['apply_wall_seconds'] for pair in pairs]
    direct = [pair['direct_wall_seconds'] for pair in pairs]
    if any(type(value) not in (float, int) or not math.isfinite(value) or value <= 0
           for value in update + direct):
        raise ValueError('economic measurements must be positive finite durations')
    ratio = statistics.median(update) / statistics.median(direct)
    rng = random.Random(seed)
    ratios = []
    for _ in range(bootstrap_repetitions):
        sample = [rng.randrange(len(pairs)) for _ in pairs]
        ratios.append(statistics.median(update[i] for i in sample) /
                      statistics.median(direct[i] for i in sample))
    ratios.sort()
    interval = [ratios[int(q * (len(ratios) - 1))] for q in (.025, .975)]
    wins = sum(left < right for left, right in zip(update, direct))
    passed = ratio < 1 and wins > len(pairs) / 2 and interval[1] < 1
    return dict(passed=passed, status='SPEEDUP' if passed else 'NO_SPEEDUP',
                apply_median_wall_seconds=statistics.median(update),
                direct_median_wall_seconds=statistics.median(direct),
                median_ratio=ratio, paired_wins=wins, paired_count=len(pairs),
                bootstrap_ratio_interval_95=interval,
                bootstrap_repetitions=bootstrap_repetitions, bootstrap_seed=seed,
                setup_in_timed_update=False,
                scope='warm authenticated session update versus fresh full Rust command')


class Qualification:
    def __init__(self, args):
        # Resolve CLI paths in the caller's directory before index subprocesses
        # switch cwd to HERE for the normal Python index loader.
        for name in ('producer', 'checker', 'indexer', 'index_session',
                     'full_checker', 'authority_key', 'workloads', 'out'):
            setattr(args, name, Path(getattr(args, name)).resolve())
        from producer_delta import DeltaSession
        self.session_type, self.args = DeltaSession, args
        self.out = args.out.resolve()
        self.workloads = args.workloads.resolve()
        self.manifest = json.loads((self.workloads / 'manifest.json').read_text())
        self.pins = json.loads((HERE / 'pins.json').read_text())
        self.profile_pins = None
        self.export_pins = self.pins['export_sha256']
        if self.manifest.get('profile') not in (None, 'original-v1'):
            self.profile_pins = json.loads((HERE / 'delta-pins.json').read_text())
            if (self.profile_pins.get('schema') != 'mathgraph.producer-delta-pins.v1' or
                    self.profile_pins['profile'] != 'std-hashmap-expanded-v1' or
                    self.manifest['profile'] != self.profile_pins['profile'] or
                    self.profile_pins['lean_toolchain'] != self.pins['lean_toolchain'] or
                    self.profile_pins['lean_githash'] != self.pins['lean_githash']):
                raise ValueError('expanded workload profile/version differs from exact pin')
            roots_path = HERE / self.profile_pins['roots_file']
            roots = json.loads(roots_path.read_text())
            if (file_hash(roots_path) != self.profile_pins['roots_sha256'] or
                    len(roots) != self.profile_pins['root_count'] or
                    canonical(self.manifest['roots']) != canonical(roots)):
                raise ValueError('expanded workload roots differ from exact policy')
            self.export_pins = self.profile_pins['export_sha256']
        self.report = dict(schema='mathgraph.authenticated-producer-delta-qualification.v1',
            continued_qualified_source=QUALIFIED_SOURCE,
            source_git_commit=subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
            source_git_status=subprocess.check_output(
                ['git', 'status', '--short'], cwd=REPO, text=True),
            harness_sha256=file_hash(__file__),
            run_completed=False, started_at_utc=datetime.now(timezone.utc).isoformat(),
            host=dict(hostname=platform.node(), system=platform.system(),
                      kernel=platform.release(), machine=platform.machine(),
                      cpu_model=next((line.split(':', 1)[1].strip() for line in
                          Path('/proc/cpuinfo').read_text().splitlines()
                          if line.startswith('model name')), 'UNKNOWN')),
            measurement_policy=dict(os_file_cache='warm',
                pair_order='apply_then_direct_on_same_live_sealed_snapshot',
                setup_in_timed_update=False, pool_hosts=False, pool_profiles=False),
            pins=self.pins, profile=self.manifest.get('profile', 'original-qualified-3436'),
            profile_pins=self.profile_pins, gates=[], samples=[], controls={}, references={},
            repetitions=args.repetitions,
            limits=['Producer supports exactly the pinned Std import and local source region.',
                    'Bootstrap measures finite host-repeat stability, not cross-host generalization.',
                    'Session seeding/startup is separately measured and excluded from warm apply.',
                    'No peak memory or change-proportional total lifetime claim is inferred.'])

    def gate(self, name, passed=None, *, detail=None, required=True):
        self.report['gates'].append(dict(name=name, passed=passed,
            status='UNKNOWN' if passed is None else 'PASS' if passed else 'FAIL',
            required=required, detail=safe(detail)))

    def flush(self):
        gates = self.report['gates']
        required = [gate for gate in gates if gate['required']]
        self.report['correctness_passed'] = self.report['run_completed'] and bool(required) and all(
            gate['passed'] is True for gate in required)
        observed = (
            'FAIL' if any(gate['passed'] is False for gate in required) else
            'INCOMPLETE' if any(gate['passed'] is None for gate in required) else
            'PASS')
        self.report['observed_gates_status'] = observed
        self.report['qualification_status'] = observed if self.report['run_completed'] else 'IN_PROGRESS'
        write(self.out / 'summary.json', self.report)

    def new_session(self, root, authority_key=None):
        return self.session_type(root=Path(root), workloads=self.workloads,
            producer=self.args.producer.resolve(), checker=self.args.checker.resolve(),
            indexer=self.args.indexer.resolve(), index_session=self.args.index_session.resolve(),
            authority_key=(authority_key or self.args.authority_key).resolve())

    def preflight(self):
        if self.out.exists() and any(self.out.iterdir()):
            raise ValueError('use a fresh output directory; prior evidence must remain intact')
        self.out.mkdir(parents=True, exist_ok=True)
        key = self.args.authority_key.resolve()
        if key == self.out or self.out in key.parents:
            raise ValueError('authority key must remain outside published evidence')
        if len(key.read_bytes()) != 32:
            raise ValueError('authority key must contain exactly 32 bytes')
        if set(self.manifest['variants']) != set(self.export_pins):
            raise ValueError('qualification requires the complete exact profile variant set')
        for variant, expected in self.export_pins.items():
            path = Path(self.manifest['variants'][variant]['path'])
            if file_hash(path) != expected:
                raise ValueError('pinned export mismatch: ' + variant)
        self.report['tools'] = {}
        for name in ('producer', 'checker', 'indexer', 'index_session', 'full_checker'):
            path = getattr(self.args, name).resolve()
            self.report['tools'][name] = dict(path=str(path), sha256=file_hash(path))
        for name in ('leanchecker', 'leanchecker-paranoid'):
            info = self.manifest['tools'][name]
            actual = file_hash(info['path'])
            if actual != self.pins['lean_release_binaries_sha256'][name]:
                raise ValueError('mandatory independent checker differs from pin: ' + name)
            self.report['tools'][name] = dict(path=info['path'], sha256=actual)
        self.gate('all_pinned_exports_and_independent_checkers_exact', True)
        sources = [HERE / name for name in ('engine.py', 'producer_delta.py', 'DeltaProducer.lean',
            'qualify_delta.py', 'build_workloads.py', 'build_delta_workloads.py',
            'pins.json', 'delta-pins.json', 'expanded-roots.json')]
        sources += [REPO / name for name in ('src/identity.rs', 'src/parser.rs',
                                           'src/bin/index_session.rs', 'src/bin/check_selected.rs')]
        self.report['measured_source_sha256'] = {str(path.relative_to(REPO)): file_hash(path)
                                                 for path in sources if path.is_file()}

    def reference(self, variant):
        export = self.manifest['variants'][variant]['path']
        native, resource = fresh_index(export, self.args.indexer,
                                      self.out / 'references' / variant / 'native')
        python, py_resource = fresh_index(export, self.args.indexer,
                                         self.out / 'references' / variant / 'python', python=True)
        self.gate('reference_python_native_exact:' + variant,
                  canonical(native) == canonical(python))
        if self.profile_pins:
            self.gate('reference_exact_profile_obligation_count:' + variant,
                      native['count'] == self.profile_pins['declaration_count'])
        self.report['references'][variant] = dict(export_path=export,
            export_sha256=file_hash(export), typed_index_sha256=digest(native),
            native=resource, python=py_resource)
        return native

    def full_oracle(self, snapshot, output, tool=None):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        config = output / 'config.json'
        write(config, configuration(snapshot))
        checker = tool or self.args.full_checker
        command = ([checker, '--from-export', snapshot]
                   if Path(checker).name in ('leanchecker', 'leanchecker-paranoid')
                   else [checker, config])
        record, _ = command_run(command, output / 'process')
        return record

    def sample(self, variant, repetition, references, *, cold_root=None, replay_id=None):
        name = f'{variant}-{repetition}'
        directory = self.out / 'samples' / name
        directory.mkdir(parents=True, exist_ok=True)
        setup_started = time.perf_counter()
        session = self.new_session(cold_root or directory / 'session')
        constructor_seconds = time.perf_counter() - setup_started
        sample = dict(variant=variant, repetition=repetition, cold_replay=cold_root is not None)
        self.report['samples'].append(sample)
        try:
            tick = time.perf_counter()
            setup = session.start()
            sample['start_wall_seconds'] = time.perf_counter() - tick
            sample['session_constructor_wall_seconds'] = constructor_seconds
            sample['setup_wall_seconds'] = time.perf_counter() - setup_started
            sample['setup_report'] = safe(setup)
            write(directory / 'baseline-result.json', session.baseline_result)
            sample['baseline_result_path'] = str(directory / 'baseline-result.json')
            sample['baseline_result_sha256'] = file_hash(directory / 'baseline-result.json')
            sample['baseline_result'] = {key: safe(session.baseline_result.get(key)) for key in
                                         ('status', 'evidence_id', 'scope', 'counts', 'checker_result')}
            self.gate('baseline_accepted:' + name,
                      session.baseline_result.get('status') == 'VERIFIED')
            tick = time.perf_counter()
            result = (session.replay(replay_id) if replay_id else
                      session.apply(source_dir=self.workloads / variant / 'source',
                                    patch=EDITS[variant], claimed_names=NAMES[variant]))
            sample['apply_wall_seconds'] = time.perf_counter() - tick
            write(directory / 'result.json', result)
            sample['result_path'] = str(directory / 'result.json')
            sample['evidence_id'] = result.get('evidence_id')
            snapshot = Path(session.snapshot_path)
            sample['snapshot'] = sealed_snapshot(snapshot)
            self.gate('snapshot_hash_matches_controller:' + name,
                      result.get('export_sha256') == sample['snapshot']['sha256'])
            # Comparator runs before any index oracle warms this composite anew.
            raw = self.full_oracle(snapshot, directory / 'direct-rust')
            sample['direct_rust'] = raw
            sample['direct_wall_seconds'] = raw['wall_seconds']
            self.gate('fresh_full_rust_accepts_exact_composite:' + name,
                      not raw['timed_out'] and raw['returncode'] == 0)
            native, process = fresh_index(snapshot, self.args.indexer,
                                          directory / 'composite-native-index')
            sample['full_index_oracle'] = process
            self.gate('composite_index_equals_independent_pinned_export:' + name,
                      canonical(native) == canonical(references[variant]))
            partition = audit_partition(result, references['baseline'], native)
            sample['partition_audit'] = partition
            self.gate('actual_kernel_counts_and_independent_reuse_partition:' + name, True)
            if not self.profile_pins:
                self.gate('preserved_original_qualified_counts:' + name,
                          (partition['actual_kernel_checked'],
                           partition['independently_replayed_reused']) == EXPECTED[variant])
            sample['persisted_acceptance_audit'] = audit_receipt(
                session.root, result, native, self.args.authority_key.read_bytes())
            self.gate('independently_authenticated_persisted_acceptance:' + name, True)
            if repetition == 0:
                python, process = fresh_index(snapshot, self.args.indexer,
                    directory / 'composite-python-index', python=True)
                sample['python_index_oracle'] = process
                self.gate('composite_python_native_exact:' + name,
                          canonical(python) == canonical(native))
                sample['independent_kernels'] = {}
                for tool in ('leanchecker', 'leanchecker-paranoid'):
                    record = self.full_oracle(snapshot, directory / tool,
                                             self.manifest['tools'][tool]['path'])
                    sample['independent_kernels'][tool] = record
                    self.gate('actual_full_' + tool + ':' + name,
                              not record['timed_out'] and record['returncode'] == 0)
            return sample
        except Exception as error:
            sample['error'] = repr(error)
            self.gate('sample_completed:' + name, False, detail=repr(error))
            return sample
        finally:
            session.close()
            self.flush()

    def negative(self, name, make_transaction=None, source_dir=None,
                 patch=None, claimed_names=None, *, variant='early-definition',
                 kernel_negative=False, zero_selection=False, expected_reason=None):
        directory = self.out / 'controls' / name
        session = self.new_session(directory / 'session')
        record = {}
        setup_complete = False
        stage = 'setup'
        before_records = None
        def accepted_records():
            return {str(path.relative_to(session.root)): file_hash(path)
                    for path in (session.root / 'cache' / 'records').glob('*.json')}
        self.report['controls'][name] = record
        try:
            record['setup'] = session.start()
            setup_complete = True
            before_records = accepted_records()
            if make_transaction is not None:
                stage = 'prepare'
                transaction = session.prepare(
                    source_dir=self.workloads / variant / 'source',
                    patch=EDITS[variant], claimed_names=NAMES[variant])
                stage = 'mutate-fixture'
                transaction = make_transaction(transaction)
                record['transaction'] = safe(transaction)
                fixture = directory / 'fixture-delta.ndjson'
                fixture.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_bytes(transaction['delta_bytes'])
                write(directory / 'fixture-attestation.json', transaction['attestation'])
                stage = 'validate'
                result = session.validate_apply(transaction)
            else:
                stage = 'validate'
                result = session.apply(source_dir=source_dir, patch=patch,
                                       claimed_names=claimed_names)
            write(directory / 'result.json', result)
            record['result_path'] = str(directory / 'result.json')
            record['result_sha256'] = file_hash(directory / 'result.json')
            record['result'] = {key: safe(result.get(key)) for key in
                               ('status', 'evidence_id', 'receipt_id', 'counts', 'checker_result', 'reason')}
            refused = result.get('status') in ('UNKNOWN', 'REJECTED')
            no_evidence = not result.get('evidence_id') and not result.get('receipt_id')
            expected_refusal = (kernel_negative or
                (result.get('status') == 'UNKNOWN' and expected_reason is not None and
                 expected_reason in str(result.get('reason', ''))))
            self.gate('control_refuses_and_issues_no_acceptance:' + name,
                      refused and no_evidence and expected_refusal,
                      detail=dict(expected_reason=expected_reason, actual_reason=result.get('reason')))
            if kernel_negative:
                checker = result.get('checker_result', {})
                self.gate('genuine_selected_parser_or_kernel_rejects:' + name,
                          result.get('status') == 'REJECTED' and checker.get('code') == 1)
                if zero_selection:
                    self.gate('genuine_parser_invoked_with_zero_selected:' + name,
                              result.get('counts', {}).get('scheduled') == 0 and
                              checker.get('code') == 1)
                snapshot = Path(session.snapshot_path)
                record['snapshot'] = sealed_snapshot(snapshot)
                record['independent_kernel_rejections'] = {}
                for tool, binary in [('rust', self.args.full_checker)] + [
                        (tool, self.manifest['tools'][tool]['path'])
                        for tool in ('leanchecker', 'leanchecker-paranoid')]:
                    oracle = self.full_oracle(snapshot, directory / tool, binary)
                    record['independent_kernel_rejections'][tool] = oracle
                    self.gate('fresh_full_' + tool + '_rejects:' + name,
                              not oracle['timed_out'] and oracle['returncode'] == 1)
                if zero_selection:
                    config, indices = directory / 'zero-config.json', directory / 'zero-indices.json'
                    write(config, configuration(snapshot))
                    write(indices, [])
                    actual, _ = command_run([self.args.checker, config, indices],
                                            directory / 'independent-zero-selected')
                    record['independent_zero_selected_parser'] = actual
                    self.gate('independent_zero_selected_parser_rejects:' + name,
                              not actual['timed_out'] and actual['returncode'] == 1)
        except ValueError as error:
            # A deliberate unsupported update can raise before returning a
            # result; this is an observed refusal, never a kernel REJECT claim.
            record['exception_refusal'] = repr(error)
            self.gate('control_refuses_before_acceptance:' + name,
                      setup_complete and stage == 'validate' and not kernel_negative and
                      expected_reason is not None and expected_reason in str(error),
                      detail=dict(expected_reason=expected_reason, actual_reason=str(error),
                                  scope='Exception refusal; no parser/kernel rejection inferred.'))
        except Exception as error:
            record['execution_error'] = repr(error)
            self.gate('control_execution_completed:' + name, False, detail=repr(error))
        finally:
            if before_records is not None:
                self.gate('no_new_persisted_acceptance:' + name,
                          before_records == accepted_records())
            session.close()
            self.flush()

    def controls(self):
        def signed_fixture(transaction, delta, names):
            value = copy.deepcopy(transaction)
            value['delta_bytes'] = delta
            payload = value['attestation']['payload']
            payload['delta_sha256'] = hashlib.sha256(delta).hexdigest()
            payload['changed_names'] = sorted(names)
            payload['producer_report']['changed_names'] = sorted(names)
            value['producer_report'] = copy.deepcopy(payload['producer_report'])
            value['attestation']['hmac_sha256'] = hmac.new(
                self.args.authority_key.read_bytes(), canonical(payload), hashlib.sha256).hexdigest()
            return value

        rows = [json.loads(line) for line in
                Path(self.manifest['variants']['baseline']['path']).open()]
        names = {0: ''}
        for row in rows:
            if 'in' in row:
                part = row.get('str', row.get('num'))
                names[row['in']] = (names[part['pre']] + '.' if names[part['pre']] else '') + str(
                    part.get('str', part.get('i')))
        original_leaf = next(row for row in rows if 'thm' in row and
                             names[row['thm']['name']] == 'IncrementalWorkload.leaf')
        leaf = copy.deepcopy(original_leaf)
        leaf['thm']['value'] = next(row['ie'] for row in rows if 'natVal' in row)
        bad_axiom = copy.deepcopy(next(row for row in rows if 'axiom' in row and
                                      names[row['axiom']['name']] == 'propext'))
        bad_axiom['axiom']['type'] = next(row['ie'] for row in rows if row.get('sort') == 0)
        unused = dict(ie=max(row['ie'] for row in rows if 'ie' in row) + 1,
                      bvar='not-an-integer')
        # The retained index policy permits replacement deltas, not DAG-only
        # updates. A bytewise no-op leaf replacement leaves every typed
        # obligation identical while the unused malformed row still must parse.
        for name, fixture_rows, changed, zero in [
                ('signed-invalid-proof', [leaf], ['IncrementalWorkload.leaf'], False),
                ('signed-invalid-axiom', [bad_axiom], ['propext'], False),
                ('unused-invalid-node-zero-selection-parser', [unused, original_leaf],
                 ['IncrementalWorkload.leaf'], True),
                ('unused-invalid-node-dag-only-zero-selection-parser', [unused], [], True)]:
            delta = b''.join(canonical(row) + b'\n' for row in fixture_rows)
            self.negative(name,
                lambda transaction, delta=delta, changed=changed:
                    signed_fixture(transaction, delta, changed),
                variant='baseline', kernel_negative=True, zero_selection=zero)
        def forged(transaction):
            value = copy.deepcopy(transaction)
            value['attestation']['hmac_sha256'] = '0' * 64
            return value
        self.negative('forged-attestation', forged, expected_reason='issuer authentication failed')
        def version_drift(transaction):
            value = copy.deepcopy(transaction)
            payload = value['attestation']['payload']
            if 'schema' not in payload:
                raise RuntimeError('attestation schema field is missing')
            payload['schema'] = str(payload['schema']) + '.foreign-version'
            value['attestation']['hmac_sha256'] = hmac.new(
                self.args.authority_key.read_bytes(), canonical(payload),
                hashlib.sha256).hexdigest()
            return value
        self.negative('authenticated-attestation-version-drift', version_drift,
                      expected_reason='wrong authority domain')
        for name, field, value in [
                ('authenticated-baseline-environment-drift', 'baseline_source_root', '0' * 64),
                ('authenticated-base-export-drift', 'base_export_sha256', '0' * 64),
                ('authenticated-producer-version-drift', 'provenance', {'schema': 'foreign'})]:
            def mutate(transaction, field=field, value=value):
                changed = copy.deepcopy(transaction)
                payload = changed['attestation']['payload']
                payload[field] = value
                changed['attestation']['hmac_sha256'] = hmac.new(
                    self.args.authority_key.read_bytes(), canonical(payload), hashlib.sha256).hexdigest()
                return changed
            self.negative(name, mutate, expected_reason='transition environment/version/base mismatch')
        self.negative('unannounced-source-change', source_dir=
                      self.workloads / 'early-definition' / 'source',
                      patch=None, claimed_names=NAMES['early-definition'],
                      expected_reason='source modifications outside the reported patch')
        self.negative('false-announced-name', source_dir=
                      self.workloads / 'early-definition' / 'source',
                      patch=EDITS['early-definition'], claimed_names=[],
                      expected_reason='expected_changed_names differs from complete local comparison')
        with tempfile.TemporaryDirectory(prefix='delta-outside-source-') as temp:
            source = Path(temp)
            for path in SOURCE_PATHS:
                target = source / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((self.workloads / 'early-definition' / 'source' / path).read_bytes())
            target = source / 'IncrementalWorkload/Leaves.lean'
            target.write_text(target.read_text().replace('n * n + 3', 'n * n + 4'))
            self.negative('outside-announced-region', source_dir=source,
                          patch=EDITS['early-definition'],
                          claimed_names=NAMES['early-definition'],
                          expected_reason='source modifications outside the reported patch')
            target = source / 'IncrementalWorkload/Base.lean'
            target.write_text(target.read_text().replace('Std.Data.HashMap', 'Std.Data.HashSet'))
            self.negative('import-environment-drift', source_dir=source,
                          patch=EDITS['early-definition'],
                          claimed_names=NAMES['early-definition'],
                          expected_reason='source modifications outside the reported patch')
        self.storage_controls()

    def storage_controls(self):
        sample = next((sample for sample in self.report['samples'] if
                       sample.get('variant') == 'early-definition' and
                       sample.get('evidence_id') and 'partition_audit' in sample), None)
        if not sample:
            self.gate('required_control:persisted-cache-corruption', None,
                      detail='No accepted delta is available for a real storage-corruption control.')
            return
        original = Path(sample['result_path']).parent / 'session'
        controls = [('baseline-receipt', 'baseline-cache/records/*.json', 'evidence content address mismatch'),
                    ('baseline-export', 'baseline-cache/exports/*.ndjson', 'baseline storage corruption'),
                    ('genesis', 'cache/genesis/*.json', 'delta storage corruption: genesis'),
                    ('accepted-delta-receipt', 'cache/records/*.json', 'delta storage corruption: records'),
                    ('persisted-delta-bytes', 'cache/deltas/*.ndjson', 'delta storage corruption: deltas'),
                    ('persisted-transition', 'cache/transitions/*.json', 'delta storage corruption: transitions'),
                    ('persisted-representation', 'cache/representations/*.json', 'delta storage corruption: representations')]
        for name, pattern, expected_reason in controls:
            directory = self.out / 'controls' / ('corrupt-' + name)
            root = directory / 'session'
            shutil.copytree(original, root)
            candidates = list(root.glob(pattern))
            record = dict(scope='disposable copy of actual accepted storage')
            self.report['controls']['corrupt-' + name] = record
            if len(candidates) != 1:
                self.gate('storage_corruption_fixture_present:' + name, False,
                          detail=[str(path) for path in candidates])
                continue
            target = candidates[0]
            before = target.read_bytes()
            target.chmod(0o600)
            target.write_bytes(before + b'\nCORRUPTED_BY_QUALIFICATION\n')
            record.update(path=str(target), original_sha256=hashlib.sha256(before).hexdigest(),
                          corrupt_sha256=file_hash(target))
            session = self.new_session(root)
            try:
                session.start()
                result = session.replay(sample['evidence_id'])
                record['result'] = safe(result)
                self.gate('cold_restart_corrupt_storage_refused:' + name,
                          result.get('status') in ('UNKNOWN', 'REJECTED') and
                          not result.get('evidence_id') and
                          expected_reason in str(result.get('reason', '')))
            except (ValueError, json.JSONDecodeError) as error:
                record['observed_refusal'] = repr(error)
                self.gate('cold_restart_corrupt_storage_refused:' + name,
                          expected_reason in str(error), detail=dict(
                              expected_reason=expected_reason, actual_reason=str(error)))
            except Exception as error:
                record['execution_error'] = repr(error)
                self.gate('cold_restart_corrupt_storage_refused:' + name, False,
                          detail=repr(error))
            finally:
                session.close()
                self.flush()
        directory = self.out / 'controls' / 'foreign-issuer-authority'
        root = directory / 'session'
        shutil.copytree(original, root)
        with tempfile.TemporaryDirectory(prefix='delta-foreign-issuer-') as private:
            key = Path(private) / 'issuer.key'
            key.write_bytes(os.urandom(32))
            key.chmod(0o600)
            session = self.new_session(root, authority_key=key)
            record = dict(scope='actual accepted baseline replay under a distinct issuer')
            self.report['controls']['foreign-issuer-authority'] = record
            try:
                session.start()
                result = session.replay(sample['evidence_id'])
                record['result'] = dict(status=result.get('status'), evidence_id=result.get('evidence_id'))
                self.gate('foreign_issuer_cannot_replay_acceptance', False)
            except ValueError as error:
                record['observed_refusal'] = repr(error)
                self.gate('foreign_issuer_cannot_replay_acceptance',
                          'evidence issuer authentication failed' in str(error), detail=str(error))
            finally:
                session.close()
                self.flush()

    def finish(self):
        economics = {}
        for variant in VARIANTS:
            samples = [sample for sample in self.report['samples'] if
                       sample['variant'] == variant and not sample['cold_replay']
                       and 'partition_audit' in sample]
            economics[variant] = paired_economics(samples)
            self.gate('complete_required_positive_pairs:' + variant,
                      len(samples) == self.args.repetitions and self.args.repetitions >= 5,
                      detail=dict(complete_pairs=len(samples), required_pairs=self.args.repetitions))
            if len(samples) != self.args.repetitions:
                economics[variant]['passed'] = False
                economics[variant]['status'] = 'UNKNOWN_INCOMPLETE_PAIRS'
        self.report['economics'] = economics
        self.report['primary_economic_gate'] = 'early-definition'
        self.report['economic_status'] = economics['early-definition']['status']
        self.report['setup_medians_wall_seconds'] = {
            variant: statistics.median([sample['setup_wall_seconds'] for sample in
                self.report['samples'] if sample['variant'] == variant and
                not sample['cold_replay'] and 'setup_wall_seconds' in sample])
            for variant in VARIANTS if any(sample['variant'] == variant and
                'setup_wall_seconds' in sample for sample in self.report['samples'])}
        for name, info in self.report['tools'].items():
            self.gate('tool_bytes_stable_through_qualification:' + name,
                      file_hash(info['path']) == info['sha256'])
        for name, expected in self.report['measured_source_sha256'].items():
            self.gate('source_bytes_stable_through_qualification:' + name,
                      file_hash(REPO / name) == expected)
        self.report['run_completed'] = True
        self.report['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        self.flush()
        lines = ['# Authenticated producer-delta qualification', '',
                 f"Correctness: {self.report['qualification_status']}. "
                 f"Primary changed-input economics: {self.report['economic_status']}.", '',
                 'Fresh full native/Python identity and real independent kernels check '
                 'the exact live sealed composite. Actual selected-kernel counts and '
                 'independent full-index replay establish the work partition.', '',
                 '| Source edit | Apply median (s) | Direct Rust median (s) | Ratio | Paired wins |',
                 '| --- | ---: | ---: | ---: | ---: |']
        for variant, value in economics.items():
            if 'median_ratio' in value:
                lines.append(f"| {variant} | {value['apply_median_wall_seconds']:.6f} | "
                    f"{value['direct_median_wall_seconds']:.6f} | {value['median_ratio']:.4f} | "
                    f"{value['paired_wins']}/{value['paired_count']} |")
        lines += ['', 'Apply timing includes the producer, authenticated delta identity, '
                  'actual selected checking and receipt persistence. Baseline seeding and '
                  'process setup are measured separately and excluded. Each pair uses a '
                  'new session; the raw full checker receives the same live sealed '
                  'composite before it is closed, in fixed apply-then-direct order. '
                  'OS file cache is warm; hosts and workload profiles are not pooled. This comparison '
                  'does not establish cold-command or total-lifetime superiority.', '',
                  'The primary gate requires lower median, strict paired majority and '
                  'paired-bootstrap 95% upper ratio below one on the early edit. '
                  'NO_SPEEDUP is retained as an economic negative and is separate from '
                  'correctness. Missing required controls are UNKNOWN and block a full '
                  'qualification claim.', '', 'Nonpassing required gates:']
        lines += ['- ' + gate['name'] + ': ' + gate['status'] for gate in self.report['gates']
                  if gate['required'] and gate['passed'] is not True]
        (self.out / 'summary.md').write_text('\n'.join(lines) + '\n')
        return self.report

    def run(self):
        self.preflight()
        references = {variant: self.reference(variant) for variant in VARIANTS}
        for repetition in range(self.args.repetitions):
            variants = list(VARIANTS)
            random.Random(20261016 + repetition).shuffle(variants)
            for variant in variants:
                self.sample(variant, repetition, references)
        original = next((sample for sample in self.report['samples'] if
                         sample['variant'] == 'early-definition' and
                         'partition_audit' in sample), None)
        if original:
            cold = self.sample('early-definition', 'cold-restart', references,
                               cold_root=Path(original['result_path']).parent / 'session',
                               replay_id=original['evidence_id'])
            self.gate('cold_restart_reauthenticates_and_repeats_partition',
                      canonical(cold.get('partition_audit')) ==
                      canonical(original['partition_audit']))
        else:
            self.gate('cold_restart_reauthenticates_and_repeats_partition', None)
        self.controls()
        return self.finish()


def self_test():
    assert canonical(True) != canonical(1)
    pairs = [dict(apply_wall_seconds=1 + i / 100,
                  direct_wall_seconds=2 + i / 100) for i in range(5)]
    assert paired_economics(pairs)['passed']
    assert not paired_economics([dict(apply_wall_seconds=2,
                                    direct_wall_seconds=1) for _ in range(5)])['passed']
    assert paired_economics([])['status'] == 'UNKNOWN_NO_COMPLETE_PAIRS'
    old = dict(meta={}, builtins={}, complex='same', schedule='same', count=2,
               declarations=[dict(key='a', own='old', closure='old', index=0, kind='def'),
                             dict(key='b', own='own', closure='dep', index=1, kind='thm')])
    assert independent_partition(old, old) == ([], [0, 1])
    changed = copy.deepcopy(old)
    changed['declarations'][0]['own'] = 'new'
    changed['declarations'][1]['closure'] = 'new-dependency'
    assert independent_partition(old, changed) == ([0, 1], [])
    with tempfile.TemporaryDirectory() as temp:
        record, output = command_run([sys.executable, '-c', 'print("oracle")'],
                                     Path(temp) / 'probe')
        assert record['returncode'] == 0 and output == b'oracle\n'
    return dict(status='PASS_HARNESS_SELF_TEST', scope='harness mechanics only')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    for flag in ('workloads', 'producer', 'checker', 'indexer', 'index-session',
                 'full-checker', 'authority-key', 'out'):
        parser.add_argument('--' + flag, type=Path)
    parser.add_argument('--repetitions', type=int, default=5)
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test()))
        return 0
    if args.repetitions < 5:
        parser.error('qualification economics requires at least five complete pairs per edit')
    for flag in ('workloads', 'producer', 'checker', 'indexer', 'index_session',
                 'full_checker', 'authority_key', 'out'):
        if getattr(args, flag) is None:
            parser.error('--' + flag.replace('_', '-') + ' is required')
    report = Qualification(args).run()
    print(json.dumps({key: report[key] for key in
        ('qualification_status', 'correctness_passed', 'economic_status')}))
    return 0 if report['correctness_passed'] else 1 if report['qualification_status'] == 'FAIL' else 2


if __name__ == '__main__':
    sys.exit(main())
