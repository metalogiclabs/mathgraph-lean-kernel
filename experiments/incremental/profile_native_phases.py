#!/usr/bin/env python3
"""Separate memory diagnostic for the unchanged native identity adapter.

Linux only. Timings include sampling/instrumentation and are not economics
measurements. Keys live in an external temporary directory, never in --out.
"""
import argparse
from contextlib import contextmanager
import functools
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASES = {'unchanged': 'baseline', 'early': 'early-definition',
         'unrelated': 'unrelated-definition', 'leaf': 'theorem-leaf',
         'invalid': 'invalid-proof'}
EXPECTED_COUNTS = {'unchanged': (0, 3436), 'early': (413, 3023),
                   'unrelated': (1, 3435), 'leaf': (1, 3435), 'invalid': (None, 3435)}


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def usage():
    own, children = (resource.getrusage(kind) for kind in
                     (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN))
    return own.ru_utime + own.ru_stime, children.ru_utime + children.ru_stime, own.ru_maxrss


def proc_memory(pid):
    try:
        values = {}
        for line in Path('/proc', str(pid), 'status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:')):
                key, value, _ = line.split()
                values[key[:-1]] = int(value)
        return values if 'VmRSS' in values else None
    except (OSError, ValueError):
        return None


def descendants(pid):
    found, pending = set(), [pid]
    while pending:
        parent = pending.pop()
        try:
            children = Path('/proc', str(parent), 'task', str(parent), 'children').read_text().split()
        except OSError:
            continue
        for child in map(int, children):
            if child not in found:
                found.add(child)
                pending.append(child)
    return found


class PhaseMemory:
    """Named adapter wrappers plus a Linux RSS sampler; no decision logic."""
    def __init__(self, interval):
        self.interval = interval
        self.origin = time.perf_counter()
        self.stack, self.spans, self.samples, self.child_usage = [], [], [], []
        self.roles, self.expected_executables = {}, {}
        self.lock, self.stop = threading.Lock(), threading.Event()

    @contextmanager
    def span(self, label):
        start, before = time.perf_counter(), usage()
        with self.lock:
            number = len(self.spans)
            record = dict(id=number, phase=label, start_seconds=start-self.origin,
                          self_highwater_before_kib=before[2])
            self.spans.append(record)
            self.stack.append(number)
        try:
            yield
        finally:
            end, after = time.perf_counter(), usage()
            with self.lock:
                self.stack.remove(number)
                record.update(end_seconds=end-self.origin, wall_seconds=end-start,
                              self_cpu_seconds=after[0]-before[0],
                              completed_children_cpu_seconds=after[1]-before[1],
                              self_highwater_after_kib=after[2])

    def wrap(self, function, label):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            name = label(*args, **kwargs) if callable(label) else label
            with self.span(name):
                return function(*args, **kwargs)
        return wrapped

    def sample(self):
        own = proc_memory(os.getpid())
        if own is None:
            return
        children = []
        # Explicit Popen PIDs cover children created by any Python thread;
        # /proc's task-specific children files alone can miss those children.
        for pid in descendants(os.getpid()) | set(self.roles):
            memory = proc_memory(pid)
            if memory is not None:
                try:
                    executable = os.readlink('/proc/' + str(pid) + '/exe')
                except OSError:
                    executable = None
                post_exec = executable is not None and executable == self.expected_executables.get(pid)
                children.append(dict(pid=pid, role=self.roles.get(pid, 'descendant'),
                                     rss_kib=memory['VmRSS'],
                                     executable=executable, confirmed_post_exec=post_exec,
                                     observed_process_highwater_kib=memory.get('VmHWM')))
        child_rss = sum(item['rss_kib'] for item in children)
        post_exec_rss = sum(item['rss_kib'] for item in children if item['confirmed_post_exec'])
        with self.lock:
            self.samples.append(dict(seconds=time.perf_counter()-self.origin,
                active_span_ids=list(self.stack), self_rss_kib=own['VmRSS'],
                self_observed_highwater_kib=own.get('VmHWM'),
                live_descendants_rss_sum_kib=child_rss,
                confirmed_post_exec_descendants_rss_sum_kib=post_exec_rss,
                self_plus_live_descendants_rss_sum_kib=own['VmRSS']+child_rss,
                children=children))

    def poll(self):
        while not self.stop.is_set():
            self.sample()
            self.stop.wait(self.interval)
        self.sample()

    def install(self, engine):
        self.original_waitpid = os.waitpid
        self.original_popen_init = subprocess.Popen.__init__
        recorder = self

        def popen_init(process, *args, **kwargs):
            recorder.original_popen_init(process, *args, **kwargs)
            command = args[0] if args else kwargs['args']
            recorder.roles[process.pid] = Path(command[0]).name
            recorder.expected_executables[process.pid] = str(Path(command[0]).resolve())

        def waitpid(pid, options):
            child, status, child_usage = os.wait4(pid, options)
            if child:
                recorder.child_usage.append(dict(pid=child,
                    role=recorder.roles.get(child, 'descendant'),
                    user_cpu_seconds=child_usage.ru_utime,
                    system_cpu_seconds=child_usage.ru_stime,
                    cpu_seconds=child_usage.ru_utime+child_usage.ru_stime,
                    wait4_max_rss_kib=child_usage.ru_maxrss,
                    exitcode=os.waitstatus_to_exitcode(status)))
            return child, status

        subprocess.Popen.__init__ = popen_init
        os.waitpid = waitpid
        for name in ('verify_incremental', 'load_evidence', 'indexed_export'):
            setattr(engine, name, self.wrap(getattr(engine, name), name))
        engine.immutable_write = self.wrap(engine.immutable_write,
            lambda path, *_args, **_kwargs: 'persist_receipt' if Path(path).suffix == '.json' else 'persist_export')

        def hash_label(path):
            name = Path(path).name
            if name == 'current.ndjson':
                return 'hash_current_export'
            return 'hash_prior_export' if name.endswith('.ndjson') else 'hash_' + name
        engine.file_hash = self.wrap(engine.file_hash, hash_label)
        engine.shutil.copyfile = self.wrap(engine.shutil.copyfile,
            lambda _source, destination, **_kwargs: 'copy_' + Path(destination).name)
        engine.subprocess.run = self.wrap(engine.subprocess.run,
            lambda command, *_args, **_kwargs: 'subprocess_' + Path(command[0]).name)
        original_encoded = engine.encoded

        def encoded(value):
            caller = inspect.currentframe().f_back.f_code.co_name
            if isinstance(value, dict) and 'decisions' in value:
                label = 'encode_final_result'
            elif isinstance(value, dict) and 'hmac_sha256' in value:
                label = 'encode_signed_receipt'
            elif isinstance(value, dict) and 'index' in value:
                label = 'encode_prior_hmac_payload' if caller == 'load_evidence' else 'encode_new_hmac_payload'
            else:
                label = 'encode_configuration_or_selection'
            with recorder.span(label):
                return original_encoded(value)
        engine.encoded = encoded
        original_loads = engine.json.loads

        def loads(value, *args, **kwargs):
            caller = inspect.currentframe().f_back.f_code.co_name
            label = {'load_evidence': 'decode_prior_receipt',
                     'indexed_export': 'decode_native_index',
                     '_verify_with_binary': 'decode_checker_report'}.get(caller, 'decode_other')
            with recorder.span(label):
                return original_loads(value, *args, **kwargs)
        engine.json.loads = loads
        self.thread = threading.Thread(target=self.poll, name='rss-sampler', daemon=True)
        self.thread.start()

    def finish(self):
        self.stop.set()
        self.thread.join()
        os.waitpid = self.original_waitpid
        subprocess.Popen.__init__ = self.original_popen_init
        phases = {}
        for span in self.spans:
            samples = [item for item in self.samples if span['id'] in item['active_span_ids']]
            peaks = {key: max((item[key] for item in samples), default=None) for key in
                     ('self_rss_kib', 'self_observed_highwater_kib', 'live_descendants_rss_sum_kib',
                      'confirmed_post_exec_descendants_rss_sum_kib',
                      'self_plus_live_descendants_rss_sum_kib')}
            span.update(sample_count=len(samples), sampled_peaks_kib=peaks)
            grouped = phases.setdefault(span['phase'], dict(calls=0, wall_seconds=0.,
                self_cpu_seconds=0., completed_children_cpu_seconds=0., sampled_peaks_kib={}))
            grouped['calls'] += 1
            for key in ('wall_seconds', 'self_cpu_seconds', 'completed_children_cpu_seconds'):
                grouped[key] += span[key]
            for key, value in peaks.items():
                prior = grouped['sampled_peaks_kib'].get(key)
                grouped['sampled_peaks_kib'][key] = max(prior or 0, value or 0) if value is not None or prior is not None else None
        for process in self.child_usage:
            observed = [child for sample in self.samples for child in sample['children']
                        if child['pid'] == process['pid'] and child['confirmed_post_exec']]
            process.update(confirmed_post_exec_sample_count=len(observed),
                sampled_post_exec_rss_peak_kib=max((child['rss_kib'] for child in observed), default=None),
                sampled_post_exec_hwm_peak_kib=max((child['observed_process_highwater_kib'] for child in observed if child['observed_process_highwater_kib'] is not None), default=None))
        return dict(phases=phases, spans=self.spans, samples=self.samples,
                    subprocess_wait4=self.child_usage, self_usage=dict(
                        cpu_seconds=usage()[0], highwater_kib=usage()[2]),
                    sample_interval_seconds=self.interval,
                    sampler_semantics='RSS values are periodic /proc samples, not exact phase peaks. Descendant sums count shared pages in each process. Highwaters are cumulative process observations; wait4 child maxima may include pre-exec fork memory. Nested phases overlap.')


def worker(args):
    arguments = json.loads(args.worker_arguments)
    spec = importlib.util.spec_from_file_location('_captured_memory_engine', args.engine)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    memory = PhaseMemory(args.interval_ms/1000)
    memory.install(engine)
    with memory.span('complete_instrumented_cli'):
        if args.worker_parse:
            process = subprocess.run(arguments, capture_output=True, timeout=600)
            code = process.returncode
        else:
            sys.argv = [str(args.engine), *arguments]
            code = engine.main()
    detail = memory.finish()
    detail.update(returncode=code, measurement_use='MEMORY_DIAGNOSTIC_NOT_PERFORMANCE_ECONOMICS')
    write(args.worker_detail, detail)
    return code


def execute(command, directory, accepted=(0,)):
    directory.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    with (directory/'stdout').open('wb') as stdout, (directory/'stderr').open('wb') as stderr:
        process = subprocess.Popen([str(item) for item in command], stdout=stdout, stderr=stderr)
        _, status, resources = os.wait4(process.pid, 0)
    code = os.waitstatus_to_exitcode(status)
    result = dict(returncode=code, instrumented_wall_seconds=time.perf_counter()-start,
                  cpu_seconds=resources.ru_utime+resources.ru_stime,
                  wait4_max_rss_kib=resources.ru_maxrss, raw_directory=str(directory))
    if code not in accepted:
        raise RuntimeError('memory diagnostic failed; see ' + str(directory))
    return result


def collect(args):
    out = args.out.resolve()
    if out.is_relative_to(REPO) or out.exists():
        raise ValueError('--out must be a new directory outside the repository')
    if args.repetitions < 1 or args.interval_ms < 0.5:
        raise ValueError('use positive repetitions and a sampling interval >= 0.5 ms')
    out.mkdir(parents=True)
    captured = out/'captured'
    captured.mkdir()
    sources = {'engine.py': args.engine, 'check-selected': args.checker, 'export-index': args.indexer}
    sources.update({'pins.json': args.pins, 'workload-manifest.json': args.workloads/'manifest.json'})
    if args.parser:
        sources['parse-only-checker'] = args.parser
    pins = {}
    for name, source in sources.items():
        raw = Path(source).read_bytes()
        (captured/name).write_bytes(raw)
        (captured/name).chmod(0o400 if name.endswith(('.py', '.json')) else 0o500)
        pins[name] = hashlib.sha256(raw).hexdigest()
    qualification = json.loads((captured/'pins.json').read_bytes())
    manifest = json.loads((captured/'workload-manifest.json').read_bytes())
    exports = {}
    for name, variant in CASES.items():
        export = (args.workloads/variant/'export.ndjson').resolve()
        actual = sha(export)
        info = manifest['variants'][variant]
        if (actual != qualification['export_sha256'][variant] or actual != info['sha256']
                or Path(info['path']).resolve() != export):
            raise ValueError('qualified export or manifest path differs: ' + name)
        exports[name] = dict(variant=variant, path=str(export), sha256=actual,
                             matches_qualification_pin=True, matches_manifest=True)
    tool = captured/'profile_native_phases.py'
    tool.write_bytes(Path(__file__).read_bytes())
    report = dict(schema='mathgraph.incremental-native-phase-memory.v1',
        measurement_use='MEMORY_DIAGNOSTIC_NOT_PERFORMANCE_ECONOMICS', captured_sha256=pins,
        profiling_tool_sha256=sha(tool), sampling_interval_ms=args.interval_ms,
        workloads=str(args.workloads.resolve()), repetitions=args.repetitions, cases={},
        validated_exports=exports, workload_manifest_sha256=pins['workload-manifest.json'],
        qualification_pins_sha256=pins['pins.json'],
        source_git_commit=subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
        authority_handling='Original engine initializes a temporary external issuer key; the key is not copied into output and is deleted after collection.',
        caveats=['Periodic /proc RSS samples are not exact phase peaks.',
                 'Parent RSS and live descendant RSS sums are separate; shared pages can be counted twice.',
                 'Highwaters are cumulative observations, not reset per phase.',
                 'Instrumented wall/CPU values are diagnostic and must not replace qualification timings.',
                 'Native indexing includes real parser and identity work; parse-only is a separate observation and is never subtracted as marginal work.'])
    with tempfile.TemporaryDirectory(prefix='native-phase-authority-') as authority:
        key = Path(authority)/'issuer.key'
        subprocess.run([sys.executable, str(captured/'engine.py'), '--init-key', str(key)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        common = ['--checker', str(captured/'check-selected'), '--indexer', str(captured/'export-index'),
                  '--identity-backend', 'native', '--authority-key', str(key)]
        baseline_dir, baseline_cache = out/'baseline', out/'baseline-cache'
        execute([sys.executable, captured/'engine.py', *common,
                 '--export', args.workloads/'baseline/export.ndjson', '--cache', baseline_cache,
                 '--disable-cache', '--output', baseline_dir/'result.json'], baseline_dir)
        baseline = json.loads((baseline_dir/'result.json').read_bytes())
        if baseline['status'] != 'VERIFIED':
            raise RuntimeError('fresh baseline did not verify')
        for field, filename in [('adapter_sha256', 'engine.py'), ('checker_sha256', 'check-selected'),
                                ('indexer_sha256', 'export-index')]:
            if baseline['provenance'][field] != pins[filename]:
                raise RuntimeError('baseline provenance differs from captured source or executable')
        if baseline['counts']['total'] != 3436 or baseline['counts']['rechecked'] != 3436:
            raise RuntimeError('this diagnostic requires the qualified 3436-declaration workload')
        report['baseline_evidence_id'] = baseline['evidence_id']
        report['baseline_counts'] = baseline['counts']
        for name, variant in CASES.items():
            runs = []
            for repetition in range(args.repetitions):
                directory, cache = out/name/str(repetition), out/'caches'/name/str(repetition)
                for folder, filename in [('records', baseline['evidence_id']+'.json'),
                                         ('exports', baseline['export_sha256']+'.ndjson')]:
                    (cache/folder).mkdir(parents=True)
                    shutil.copy2(baseline_cache/folder/filename, cache/folder/filename)
                arguments = [*common, '--export', str(args.workloads/variant/'export.ndjson'),
                             '--cache', str(cache), '--previous', baseline['evidence_id'],
                             '--output', str(directory/'result.json')]
                result = execute([sys.executable, tool, '--worker-arguments', json.dumps(arguments),
                    '--worker-detail', directory/'memory.json', '--engine', captured/'engine.py',
                    '--interval-ms', str(args.interval_ms)], directory, accepted=(1,) if name == 'invalid' else (0,))
                engine_result = json.loads((directory/'result.json').read_bytes())
                detail = json.loads((directory/'memory.json').read_bytes())
                expected_status = 'REJECTED' if name == 'invalid' else 'VERIFIED'
                actual_counts = engine_result['counts']
                if (engine_result['status'] != expected_status or engine_result.get('cache_error') is not None
                        or actual_counts['total'] != 3436
                        or (actual_counts['rechecked'], actual_counts['reused']) != EXPECTED_COUNTS[name]):
                    raise RuntimeError('classification or obligation counts changed: ' + name)
                result.update(status=engine_result['status'], counts=engine_result['counts'],
                              classification_and_counts_validated=True,
                              subprocess_sampling_complete=all(process['confirmed_post_exec_sample_count'] > 0
                                  for process in detail['subprocess_wait4']),
                              engine_timings=engine_result['timings'],
                              memory={key:value for key,value in detail.items() if key not in ('samples','spans')})
                runs.append(result)
            report['cases'][name] = runs
        if args.parser:
            config = out/'parse-only-config.json'
            write(config, dict(baseline['provenance']['configuration'], parse_only=True,
                               export_file_path=str(args.workloads/'baseline/export.ndjson')))
            directory = out/'parse-only'
            result = execute([sys.executable, tool, '--worker-arguments', json.dumps([str(captured/'parse-only-checker'),str(config)]),
                '--worker-parse', '--worker-detail', directory/'memory.json', '--engine', captured/'engine.py',
                '--interval-ms', str(args.interval_ms)], directory)
            detail = json.loads((directory/'memory.json').read_bytes())
            result['memory'] = {key:value for key,value in detail.items() if key not in ('samples','spans')}
            report['separate_parse_only_observation'] = result
    write(out/'summary.json', report)
    if args.summary:
        write(args.summary, report)
    print(json.dumps(dict(summary=str(args.summary or out/'summary.json'))))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workloads', type=Path, default=Path('/workspace/kernel-audit/workloads-final'))
    parser.add_argument('--checker', type=Path, default=REPO/'target/release/check-selected')
    parser.add_argument('--indexer', type=Path, default=REPO/'target/release/export-index')
    parser.add_argument('--engine', type=Path, default=HERE/'engine.py')
    parser.add_argument('--pins', type=Path, default=HERE/'pins.json')
    parser.add_argument('--parser', type=Path, help='Optional ordinary checker for a separate baseline parse_only observation')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--summary', type=Path, help='Compact report; raw samples and executable copies stay in --out')
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--interval-ms', type=float, default=2.)
    parser.add_argument('--worker-arguments', help=argparse.SUPPRESS)
    parser.add_argument('--worker-detail', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--worker-parse', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_arguments is not None:
        return worker(args)
    if args.out is None:
        parser.error('--out is required')
    return collect(args)


if __name__ == '__main__':
    raise SystemExit(main())
