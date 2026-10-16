#!/usr/bin/env python3
"""Profile the pinned Python identity path without changing its source/provenance.

This is a workload-specific research tool, not a replacement engine. Unprofiled,
cProfile, and operation-instrumented runs use separate caches. Raw outputs and
.prof files belong outside git; only the compact report is intended for git.
"""
import argparse
import ast
from collections import defaultdict
from contextlib import contextmanager
import cProfile
import functools
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pstats
import resource
import shutil
import subprocess
import sys
import time


SOURCE = '9ac0403'
FILES = ('engine.py', 'mathgraph_integration.py', 'pins.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def rss_kib():
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith('VmRSS:'):
            return int(line.split()[1])
    return None


class Operations:
    """Only named engine operations; inclusive and exclusive costs are separate."""
    def __init__(self):
        self.rows = defaultdict(lambda: dict(calls=0, wall_seconds=0., cpu_seconds=0.,
            self_wall_seconds=0., self_cpu_seconds=0.))
        self.stack = []
        self.phase_name = None
        self.phase_start = None
        self.phases = []
        self.counts = defaultdict(int)

    @contextmanager
    def span(self, name):
        label = (self.phase_name + '/' if self.phase_name else '') + name
        frame = [time.perf_counter(), time.process_time(), 0., 0.]
        self.stack.append(frame)
        try:
            yield
        finally:
            wall, cpu = time.perf_counter()-frame[0], time.process_time()-frame[1]
            self.stack.pop()
            row = self.rows[label]
            row['calls'] += 1
            row['wall_seconds'] += wall
            row['cpu_seconds'] += cpu
            row['self_wall_seconds'] += wall-frame[2]
            row['self_cpu_seconds'] += cpu-frame[3]
            if self.stack:
                self.stack[-1][2] += wall
                self.stack[-1][3] += cpu

    def call(self, name, function, *args, **kwargs):
        if name == 'json_parse' and args:
            label = (self.phase_name + '/' if self.phase_name else '') + name
            self.counts[label + '_input_bytes'] += len(args[0])
        if name.startswith('dependency_'):
            if name == 'dependency_update' and args:
                self.counts['dependency_update_input_members'] += len(args[0])
            elif name == 'dependency_materialize' and args:
                self.counts['dependency_materialized_members'] += len(args[0])
        with self.span(name):
            return function(*args, **kwargs)

    def phase(self, name):
        now = (time.perf_counter(), time.process_time(), rss_kib())
        if self.phase_name:
            self.phases.append(dict(name=self.phase_name,
                wall_seconds=now[0]-self.phase_start[0],
                cpu_seconds=now[1]-self.phase_start[1],
                rss_start_kib=self.phase_start[2], rss_end_kib=now[2]))
        self.phase_name, self.phase_start = name, now if name else None

    def wrap(self, name, function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            if name == 'file_copy':
                self.counts['copied_bytes'] += Path(args[0]).stat().st_size
            if name == 'file_hash':
                self.counts['file_hash_input_bytes'] += Path(args[0]).stat().st_size
            if name == 'canonical_json':
                with self.span(name):
                    result = function(*args, **kwargs)
                self.counts['canonical_json_output_bytes'] += len(result)
                label = (self.phase_name or 'outside_index') + '/' + name
                self.counts[label + '_output_bytes'] += len(result)
                return result
            return self.call(name, function, *args, **kwargs)
        return wrapped

    def index_counts(self, names, levels, exprs, decls, blocks):
        with self.span('index_statistics'):
            self.counts.update(name_nodes=len(names), level_nodes=len(levels),
                expression_nodes=len(exprs), declarations=len(decls), inductive_blocks=len(blocks),
                expression_dependency_members=sum(len(value[1]) for value in exprs.values()),
                max_expression_dependencies=max(len(value[1]) for value in exprs.values()),
                declaration_dependency_members=sum(len(value['deps']) for value in decls),
                max_declaration_dependencies=max(len(value['deps']) for value in decls))

    def graph_counts(self, adjacency, components):
        with self.span('index_statistics'):
            self.counts.update(declaration_graph_edges=sum(map(len,adjacency.values())),
                scc_components=len(components), max_scc_members=max(map(len,components)))


class Instrument(ast.NodeTransformer):
    """Count the original dependency set calls, and split rows from SCC closure."""
    def visit_Call(self, node):
        self.generic_visit(node)
        name = None
        if isinstance(node.func, ast.Attribute):
            base, attr = node.func.value, node.func.attr
            if isinstance(base, ast.Name) and base.id == 'json' and attr == 'loads':
                name = 'json_parse'
            elif isinstance(base, ast.Name) and base.id == 'deps' and attr in ('add','update','discard'):
                name = 'dependency_' + attr
        elif isinstance(node.func, ast.Name) and node.func.id in ('frozenset','sorted'):
            if node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == 'deps':
                name = 'dependency_materialize'
        if name:
            return ast.copy_location(ast.Call(func=ast.Name(id='_op_call', ctx=ast.Load()),
                args=[ast.Constant(name), node.func, *node.args], keywords=node.keywords), node)
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        if node.name == 'make_index':
            body = [ast.parse("_op_phase('index_rows')").body[0]]
            for statement in node.body:
                if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'by_key' for t in statement.targets):
                    body += ast.parse('_op_index_counts(names, levels, exprs, decls, blocks)').body
                    body += ast.parse("_op_phase('index_scc')").body
                if isinstance(statement, ast.Return):
                    # Return expressions still belong to SCC/summary computation.
                    body += ast.parse('_op_graph_counts(adjacency, components)').body
                    statement = ast.Assign(targets=[ast.Name(id='_op_index_result',ctx=ast.Store())],value=statement.value)
                    body += [statement, *ast.parse("_op_phase(None)\nreturn _op_index_result").body]
                else:
                    body.append(statement)
            node.body = body
        return node


def load_module(path, instrument=False, operations=None):
    # __file__ remains the exact git-show copy. Runtime instrumentation does not
    # alter the adapter hash authenticated by the existing qualified evidence.
    name = '_pinned_' + Path(path).stem
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    raw = Path(path).read_bytes()
    if instrument:
        tree = Instrument().visit(ast.parse(raw, filename=str(path)))
        ast.fix_missing_locations(tree)
        module.__dict__.update(_op_call=operations.call, _op_phase=operations.phase,
            _op_index_counts=operations.index_counts, _op_graph_counts=operations.graph_counts)
        exec(compile(tree, str(path), 'exec'), module.__dict__)
        for function, label in [('encoded','canonical_json'), ('canonical','canonical_json'),
                ('digest','merkle_digest'), ('file_hash','file_hash'),
                ('make_index','make_index'), ('load_evidence','cache_authentication'),
                ('immutable_write','receipt_or_export_persistence'),
                ('pinned_resolver','pinned_resolver'), ('consume_qualified_result','adapter_consume')]:
            if hasattr(module, function):
                setattr(module, function, operations.wrap(label, getattr(module,function)))
        if hasattr(module, 'shutil'):
            module.shutil.copyfile = operations.wrap('file_copy', module.shutil.copyfile)
        if hasattr(module, 'subprocess'):
            module.subprocess.run = operations.wrap('external_subprocess', module.subprocess.run)
    else:
        exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def profile_top(path):
    stats = pstats.Stats(str(path))
    return [dict(file=key[0], line=key[1], function=key[2], primitive_calls=value[0],
        calls=value[1], self_seconds=value[2], cumulative_seconds=value[3])
        for key,value in sorted(stats.stats.items(), key=lambda item:item[1][2], reverse=True)[:35]]


def child(args):
    operations = Operations()
    module_name = 'engine.py' if args.kind == 'engine' else 'mathgraph_integration.py'
    module = load_module(args.base / module_name, args.mode == 'operations', operations)
    # Invoke the unchanged CLI main, retaining its output write and stdout work.
    sys.argv = [str(args.base / module_name), *json.loads(args.arguments)]
    profiler = cProfile.Profile() if args.mode == 'cprofile' else None
    start = time.perf_counter(), time.process_time()
    if profiler:
        profiler.enable()
    code = module.main()
    if profiler:
        profiler.disable()
        profiler.dump_stats(str(args.raw / 'profile.prof'))
    wall, cpu = time.perf_counter()-start[0], time.process_time()-start[1]
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    metrics = dict(mode=args.mode, kind=args.kind, returncode=code,
        in_process_wall_seconds=wall, in_process_cpu_seconds=cpu,
        children_cpu_seconds=children.ru_utime+children.ru_stime,
        process_max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        children_max_rss_kib=children.ru_maxrss)
    if args.mode == 'operations':
        metrics.update(operations=dict(operations.rows), counts=dict(operations.counts),
            phases=operations.phases,
            caveat='Operation timers perturb runtime. Exclusive costs exclude nested timers, not instrumentation overhead. RSS phase values are boundary samples; process maxima are measured separately.')
    if profiler:
        metrics['profile_top_self'] = profile_top(args.raw/'profile.prof')
    write(args.raw/'metrics.json', metrics)
    return code


def run_child(script, base, raw, kind, mode, arguments):
    raw.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, str(script), '--child', '--base', str(base),
        '--raw', str(raw), '--kind', kind, '--mode', mode,
        '--arguments', json.dumps(arguments)]
    start = time.perf_counter()
    with (raw/'stdout').open('wb') as stdout, (raw/'stderr').open('wb') as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        _, status, usage = os.wait4(process.pid, 0)
    code = os.waitstatus_to_exitcode(status)
    record = dict(command=command, returncode=code,
        wall_seconds=time.perf_counter()-start,
        cpu_seconds=usage.ru_utime+usage.ru_stime, max_rss_kib=usage.ru_maxrss,
        raw_directory=str(raw))
    if code:
        raise RuntimeError('profile child failed: ' + str(raw))
    record['detail'] = json.loads((raw/'metrics.json').read_bytes())
    write(raw/'process.json', record)
    return record


def orchestrate(args):
    repo = args.repo.resolve()
    if args.raw.resolve().is_relative_to(repo) or args.repetitions < 1:
        raise ValueError('use an external raw directory and at least one unprofiled repetition')
    source = subprocess.check_output(['git','rev-parse',args.source+'^{commit}'],cwd=repo,text=True).strip()
    args.base.mkdir(parents=True, exist_ok=True)
    args.raw.mkdir(parents=True, exist_ok=True)
    if (args.raw/'summary.json').exists():
        raise ValueError('choose a new raw directory; evidence is never overwritten')
    captured_tool = args.raw/'profile_identity.py'
    if captured_tool.exists():
        raise ValueError('choose a new raw directory; captured tool already exists')
    captured_tool.write_bytes(Path(__file__).read_bytes())
    hashes = {}
    for name in FILES:
        data = subprocess.check_output(['git','show',source+':experiments/incremental/'+name],cwd=repo)
        destination = args.base/name
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError('pinned private-copy source differs: '+str(destination))
        destination.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    baseline = json.loads(args.baseline_result.read_bytes())
    if baseline['provenance']['adapter_sha256'] != hashes['engine.py']:
        raise ValueError('baseline evidence adapter differs from pinned source')
    if baseline['provenance']['checker_sha256'] != sha(args.checker):
        raise ValueError('baseline evidence checker differs from selected binary')
    pins = json.loads((args.base/'pins.json').read_bytes())
    report = dict(schema='mathgraph.incremental-native-profile.v1', source_commit=source,
        profiling_tool_sha256=sha(__file__),
        source_sha256=hashes, baseline_evidence_id=baseline['evidence_id'],
        baseline_result_sha256=sha(args.baseline_result), checker_sha256=sha(args.checker),
        workload_manifest_sha256=sha(args.workloads/'manifest.json'),
        python=sys.version, timing_definition='Fresh child process including common profiling-harness startup; caches cloned outside timing. Unprofiled runs are performance evidence; instrumented runs provide attribution only.',
        cache_state='Each run receives only the baseline evidence record and baseline export; the changed export and receipt are newly persisted.',
        rss_definition='wait4 ru_maxrss in KiB; process tree maximum, not sum of simultaneous resident memory.',
        cases={}, adapter={})
    for variant in ('early-definition','unrelated-definition'):
        export = args.workloads/variant/'export.ndjson'
        if sha(export) != pins['export_sha256'][variant]:
            raise ValueError('workload differs from qualified pin: '+variant)
        case = dict(export_sha256=sha(export), bytes=export.stat().st_size, runs=[])
        for mode in ['unprofiled']*args.repetitions + ['cprofile','operations']:
            number = len(case['runs'])
            raw = args.raw/variant/(str(number)+'-'+mode)
            cache = args.raw/'caches'/variant/(str(number)+'-'+mode)
            for directory, filename in [('records',baseline['evidence_id']+'.json'),
                    ('exports',baseline['export_sha256']+'.ndjson')]:
                (cache/directory).mkdir(parents=True, exist_ok=False)
                shutil.copy2(args.cache/directory/filename, cache/directory/filename)
            arguments = ['--export',str(export),'--checker',str(args.checker),'--cache',str(cache),
                '--authority-key',str(args.authority_key),'--previous',baseline['evidence_id'],
                '--output',str(raw/'result.json')]
            record = run_child(captured_tool, args.base, raw, 'engine', mode, arguments)
            result = json.loads((raw/'result.json').read_bytes())
            record.update(status=result['status'], counts=result['counts'], engine_timings=result['timings'],
                result_sha256=sha(raw/'result.json'), result_path=str(raw/'result.json'))
            record['evidence_id'] = result['evidence_id']
            if result['status'] != 'VERIFIED':
                raise ValueError('profiled export did not verify')
            case['runs'].append(record)
        case['all_modes_same_evidence'] = len({r['evidence_id'] for r in case['runs']}) == 1
        if not case['all_modes_same_evidence']:
            raise ValueError('runtime instrumentation changed authenticated evidence')
        report['cases'][variant] = case
    # Import one actual unrelated-edit result, with an externally supplied exact
    # result pin and identity pins, through the unchanged bounded adapter CLI.
    result_path = Path(report['cases']['unrelated-definition']['runs'][0]['result_path'])
    result = json.loads(result_path.read_bytes())
    for mode in ('unprofiled','cprofile','operations'):
        raw = args.raw/'adapter'/mode
        arguments = ['--mathgraph',str(args.mathgraph),'--result',str(result_path),
            '--expected-evidence-id',result['evidence_id'],
            '--expected-export-sha256',result['export_sha256'],
            '--expected-result-sha256',sha(result_path),'--output',str(raw/'result.json')]
        record = run_child(captured_tool, args.base, raw, 'adapter', mode, arguments)
        adapter_result = json.loads((raw/'result.json').read_bytes())
        record.update(status=adapter_result['status'], obligations=len(adapter_result['obligations']))
        report['adapter'][mode] = record
    write(args.raw/'summary.json', report)
    if args.summary:
        write(args.summary, report)
    print(json.dumps(dict(summary=str(args.summary or args.raw/'summary.json'),source=source)))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--kind',choices=('engine','adapter'),help=argparse.SUPPRESS)
    p.add_argument('--mode',choices=('unprofiled','cprofile','operations'),help=argparse.SUPPRESS)
    p.add_argument('--arguments',help=argparse.SUPPRESS)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--source',default=SOURCE)
    p.add_argument('--base',type=Path,default=Path('/workspace/native-profile-base'))
    p.add_argument('--raw',type=Path,required=True)
    p.add_argument('--summary',type=Path)
    p.add_argument('--repetitions',type=int,default=3)
    p.add_argument('--baseline-result',type=Path,default=Path('/workspace/kernel-audit/qualification-final-v2/baseline-full.json'))
    p.add_argument('--cache',type=Path,default=Path('/workspace/kernel-audit/qualification-final-v2/cache'))
    p.add_argument('--authority-key',type=Path,default=Path('/workspace/kernel-audit/.qualification-final-v2-authority/issuer.key'))
    p.add_argument('--checker',type=Path,default=Path('/workspace/mathgraph-lean-kernel/target/release/check-selected'))
    p.add_argument('--workloads',type=Path,default=Path('/workspace/kernel-audit/workloads-final'))
    p.add_argument('--mathgraph',type=Path,default=Path('/workspace/mathgraph'))
    args = p.parse_args()
    return child(args) if args.child else orchestrate(args)


if __name__ == '__main__':
    raise SystemExit(main())
