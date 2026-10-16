#!/usr/bin/env python3
"""Differential qualification of the optional native identity accelerator.

This calls the existing Python index and engine. It never implements a second
reuse predicate. A native decline is visible evidence, and must preserve the
Python fallback and the existing selected-checker's parser boundary.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import engine
from process import run, sha256
from test_predicate import Graph

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STANDARD_AXIOMS = ['propext', 'Classical.choice', 'Quot.sound']


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n')


def configuration(export):
    return dict(export_file_path=str(export), use_stdin=False,
                permitted_axioms=STANDARD_AXIOMS, unpermitted_axiom_hard_error=True,
                num_threads=1, nat_extension=True, string_extension=True,
                print_success_message=True)


def pinned_manifest(workloads):
    manifest = json.loads((workloads / 'manifest.json').read_text())
    pins = json.loads((HERE / 'pins.json').read_text())
    if set(manifest['variants']) != set(pins['export_sha256']):
        raise ValueError('qualification requires every exact pinned export')
    for name, info in manifest['variants'].items():
        if sha256(info['path']) != info['sha256'] or info['sha256'] != pins['export_sha256'][name]:
            raise ValueError('pinned export changed: ' + name)
    return manifest, pins


def invoke(export, backend, checker, indexer, cache, key, output, previous=None, disable=False):
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(HERE / 'engine.py'), '--export', str(export),
               '--checker', str(checker), '--cache', str(cache), '--authority-key', str(key),
               '--output', str(output), '--identity-backend', backend]
    if backend != 'python':
        command += ['--indexer', str(indexer)]
    if previous:
        command += ['--previous', previous]
    if disable:
        command += ['--disable-cache']
    resources = run(command, output.with_name(output.stem + '-process'), timeout=900)
    result = json.loads(output.read_text()) if output.exists() else dict(status='MISSING_RESULT')
    return dict(result_path=str(output), result_sha256=sha256(output) if output.exists() else None,
                resources=resources, result=result,
                protocol_valid=not resources['timed_out'] and resources['returncode'] ==
                {'VERIFIED': 0, 'REJECTED': 1, 'UNKNOWN': 2}.get(result.get('status')))


def projection(result):
    """Evidence identities and tool provenance intentionally differ by backend."""
    return dict(status=result.get('status'), counts=result.get('counts'),
        decisions=[{key: decision.get(key) for key in
                    ('name', 'index', 'status', 'reason', 'dependency_witness')}
                   for decision in result.get('decisions', [])],
        selected_indices=[d['index'] for d in result.get('decisions', [])
                          if d['status'] != 'VERIFIED_REUSED'],
        checker_code=result.get('checker_result', {}).get('code'))


def compact(value):
    if isinstance(value, dict):
        return {key: compact(item) for key, item in value.items()
                if key not in ('decisions', 'invalidation_events', 'checker_result')}
    if isinstance(value, list):
        return [compact(item) for item in value]
    return value


def fixtures(directory, metadata):
    """Independent small inputs target representations the parser discards.

    These are identity tests, including intentionally untypable graphs. Their
    kernel acceptance is never inferred from index equality.
    """
    cases = {}

    def add(name, rows=None, raw=None, category='adversarial'):
        path = directory / (name + '.ndjson')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw if raw is not None else
                         b''.join((json.dumps(r, ensure_ascii=True) + '\n').encode() for r in rows))
        cases[name] = dict(path=str(path), sha256=sha256(path), category=category)

    def graph():
        g = Graph()
        g.rows[0] = {'meta': copy.deepcopy(metadata)}
        prop = g.expr('sort', 0)
        g.definition('alpha', prop, prop)
        return g, prop

    g, prop = graph()
    add('simple', g.rows)
    add('minimal-metadata-python-only', Graph().rows, category='fallback')
    add('json-whitespace-reordered', raw=('\n'.join(json.dumps(r, indent=2, sort_keys=True)
        .replace('\n', ' ') for r in g.rows) + '\n').encode())
    for suffix in ['\x7f', '\x00\b\f\n\r\t', '"\\/', '\u00e9', '\U0001f642', '\ud800']:
        t, p = graph()
        t.definition('unicode.' + suffix, p, p)
        add('unicode-' + str(len(cases)), t.rows)
    t, p = graph()
    t.definition('unicode.é🙂', p, p)
    add('literal-unicode', raw=(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in t.rows)).encode())
    for tag, value in [('bvar', 0), ('natVal', '01'), ('natVal', '1'),
                       ('strVal', 'quoted " slash / backslash \\ é🙂')]:
        t, p = graph()
        expression = t.expr(tag, value)
        t.definition('scalar', p, expression)
        add('scalar-' + str(len(cases)), t.rows)
    for value in [True, -1, 1.25, 10**90, None]:
        t, p = graph()
        t.expr('bvar', value)
        add('scalar-boundary-' + str(len(cases)), t.rows)
    for value in [True, 1.25, 10**90, None, float('nan'), float('inf')]:
        t, p = graph()
        t.rows[0]['meta']['scalar'] = value
        add('metadata-scalar-' + str(len(cases)), t.rows)
    for binder in ['default', 'implicit', 'strictImplicit', 'instImplicit', 'unknown']:
        t, p = graph()
        x = t.name('binder.' + binder)
        expression = t.expr('lam', dict(name=x, type=p, body=p, binderInfo=binder))
        t.definition('lambda', p, expression)
        add('binder-' + binder, t.rows)
    for variant in ['missing', 'null', 'extra']:
        t, p = graph()
        obj = dict(name=t.name('binder'), type=p, body=p, binderInfo='default')
        if variant == 'missing':
            del obj['binderInfo']
        elif variant == 'null':
            obj['binderInfo'] = None
        else:
            obj['unexpected'] = 0
        t.expr('forallE', obj)
        add('binder-' + variant, t.rows)
    for nondep in [False, True]:
        t, p = graph()
        expression = t.expr('letE', dict(name=t.name('local'), type=p, value=p, body=p, nondep=nondep))
        t.definition('let', p, expression)
        add('let-' + str(nondep), t.rows)
    for field in ['all', 'hints', 'safety']:
        t, p = graph()
        decl = t.rows[-1]['def']
        decl[field] = [t.name('missing')] if field == 'all' else 'regular' if field == 'hints' else 'unsafe'
        if field == 'all':
            # Move the name row before the declaration that references it.
            t.rows[-1], t.rows[-2] = t.rows[-2], t.rows[-1]
        add('declaration-' + field, t.rows)
    for kind in [0, 1, 2, 3]:
        t, p = graph()
        t.rows.append({'quot': dict(name=t.name('Quot.' + str(kind)), levelParams=[], type=p, kind=kind)})
        add('quot-kind-' + str(kind), t.rows)
    for nested, reflexive in [(0, False), (1, False), (2, False), (0, True)]:
        t, p = graph()
        ty = t.itype('Family', p, constructors=['Family.mk'])
        ty.update(numNested=nested, isReflexive=reflexive)
        ctor = dict(name=t.name('Family.mk'), levelParams=[], type=p, induct=t.name('Family'),
                    cidx=0, numParams=0, numFields=0, isUnsafe=False)
        helper = t.const('missing')
        rec = dict(name=t.name('Family.rec'), levelParams=[], type=p, all=[t.name('Family')],
                   numParams=0, numIndices=0, numMotives=1, numMinors=1,
                   rules=[dict(ctor=t.name('Family.mk'), nfields=0, rhs=helper)], k=False, isUnsafe=False)
        t.block([ty], [ctor], [rec])
        add(f'inductive-nested-{nested}-reflexive-{reflexive}', t.rows)
    for split in [False, True]:
        t, p = graph()
        first = t.itype('First', p, family=['First', 'Second'])
        second = t.itype('Second', p, family=['First', 'Second'])
        if split:
            t.block([first]); t.block([second])
        else:
            t.block([first, second])
        add('block-regrouping-' + str(split), t.rows)
    t, p = graph()
    t.block([])
    add('empty-inductive-block', t.rows)
    for changed in [False, True]:
        t, p = graph()
        a, b = t.const('a'), t.const('b')
        missing = t.const('missing')
        t.definition('a', p, b)
        t.definition('b', p, t.expr('app', dict(fn=a, arg=missing)) if changed else a)
        t.definition('diamond.left', p, a)
        t.definition('diamond.right', p, b)
        left, right = t.const('diamond.left'), t.const('diamond.right')
        t.definition('consumer', p, t.expr('app', dict(fn=left, arg=right)))
        add('scc-diamond-' + str(changed), t.rows)
    for reverse in [False, True]:
        t = Graph(); t.rows[0] = {'meta': copy.deepcopy(metadata)}
        for n in (['beta', 'alpha'] if reverse else ['alpha', 'beta']):
            t.name(n)
        if reverse:
            t.expr('bvar', 0)
        p = t.expr('sort', 0)
        t.definition('alpha', p, p)
        t.definition('beta', p, t.const('alpha'))
        add('renumbering-' + str(reverse), t.rows)
    for declared in [False, True]:
        t, p = graph()
        if declared:
            t.definition('String.ofList', p, t.const('alpha'))
        else:
            t.name('String.ofList')
        add('builtin-' + str(declared), t.rows)
    t, p = graph()
    t.name('Nat.zero')
    t.rows.append({'in': len(t.names), 'str': {'pre': 0, 'str': 'Nat.zero'}})
    add('ambiguous-builtin-display', t.rows)
    for name, mutate in [
        ('forward-dag', lambda r: r.append({'ie': 99, 'app': {'fn': 100, 'arg': 0}})),
        ('duplicate-dag', lambda r: r.append({'ie': 0, 'sort': 0})),
        ('boolean-dag-index', lambda r: r.append({'ie': True, 'sort': 0})),
        ('boolean-dag-reference', lambda r: r.append({'ie': 99, 'sort': False})),
        ('negative-dag-reference', lambda r: r.append({'ie': 99, 'sort': -1})),
        ('extra-row-field', lambda r: r.append({'ie': 99, 'sort': 0, 'extra': 1})),
        ('unknown-tag', lambda r: r.append({'ie': 99, 'unknown': 0})),
        ('repeated-metadata', lambda r: r.append(copy.deepcopy(r[0]))),
        ('duplicate-declaration', lambda r: r.append(copy.deepcopy(r[-1]))),
    ]:
        rows = copy.deepcopy(g.rows); mutate(rows); add(name, rows)
    base = b''.join((json.dumps(r) + '\n').encode() for r in g.rows)
    for name, suffix in [('duplicate-key', b'{"ie":99,"sort":0,"sort":0}\n'),
                         ('duplicate-nested-key', b'{"in":99,"str":{"pre":0,"str":"x","str":"y"}}\n'),
                         ('invalid-json-leading-zero', b'{"ie":099,"sort":0}\n'),
                         ('invalid-json-control', b'{"ie":99,"strVal":"raw\x01control"}\n'),
                         ('json-array-row', b'[]\n'), ('truncated-json', b'{"ie":99')]:
        add(name, raw=base + suffix)
    # Sparse indices preserve identity; every graph edge, including names inside
    # declaration metadata, is renumbered without changing declaration order.
    t, p = graph()
    t.definition('consumer', p, t.const('alpha'))
    rows = copy.deepcopy(t.rows)
    name_fields = {'name', 'induct', 'ctor', 'pre', 'typeName'}
    expr_fields = {'type', 'value', 'rhs', 'fn', 'arg', 'body', 'struct'}
    def sparse(obj, key=None):
        if isinstance(obj, dict):
            return {k: sparse(v, k) for k, v in obj.items()}
        if isinstance(obj, list):
            if key in ('levelParams', 'all', 'ctors'):
                return [v * 11 if v else 0 for v in obj]
            return [sparse(v) for v in obj]
        if type(obj) is int and key in name_fields | expr_fields | {'in', 'ie'}:
            return obj * 11 if key != 'ie' else obj * 11 + 7
        return obj
    # Expression zero cannot share the names/levels zero convention.
    def renumber(row):
        out = sparse(row)
        def fix(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in expr_fields and type(v) is int:
                        obj[k] = v + 7
                    else:
                        fix(v)
            elif isinstance(obj, list):
                for v in obj:
                    fix(v)
        fix(out)
        return out
    add('sparse-indices', [renumber(r) for r in rows])
    return cases


def index_observation(name, info, indexer, out):
    export = Path(info['path'])
    location = out / 'indexes' / name
    location.mkdir(parents=True, exist_ok=True)
    python = run([sys.executable, str(Path(__file__).resolve()), '--python-index', str(export)],
                 location / 'python-process', timeout=900)
    config = location / 'native-config.json'
    write(config, configuration(export))
    native = run([str(indexer), str(config)], location / 'native-process', timeout=900)
    def read(record):
        try:
            return json.loads(Path(record['stdout_path']).read_bytes(), object_pairs_hook=engine.strict_object)
        except (ValueError, OSError):
            return None
    py, rust = read(python), read(native)
    python_ok = python['returncode'] == 0 and not python['timed_out'] and isinstance(py, dict)
    native_ok = native['returncode'] == 0 and not native['timed_out'] and isinstance(rust, dict)
    structured_decline = (not native_ok and not native['timed_out'] and isinstance(rust, dict)
        and bool(rust.get('error')) and rust.get('stage') in ('kernel_parse', 'identity')
        and type(rust.get('declined')) is bool
        and (not python_ok or rust['stage'] == 'kernel_parse' or rust['declined']))
    equality = python_ok and native_ok and engine.encoded(py) == engine.encoded(rust)
    passed = equality if native_ok else structured_decline
    if native_ok and not python_ok:
        passed = False
    # The ordinary, pinned inputs must exercise the accelerator successfully.
    if info['category'] == 'pinned' and name not in ('malformed-unused-dag', 'malformed-unused-typed-node'):
        passed = passed and equality
    return dict(export_sha256=info['sha256'], category=info['category'],
        python=dict(resources=python, indexed=python_ok, error=None if python_ok else py),
        native=dict(resources=native, indexed=native_ok, decline=None if native_ok else rust),
        index_equal=equality, python_fallback_required=python_ok and not native_ok,
        passed=passed)


def qualify(args):
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('use a new output directory to preserve all evidence')
    out.mkdir(parents=True, exist_ok=True)
    manifest, pins = pinned_manifest(args.workloads.resolve())
    tools = out / 'captured-tools'
    tools.mkdir()
    captured = {}
    for name, source in [('check-selected', args.checker), ('sokonanoda', args.full_checker),
                         ('export-index', args.indexer)]:
        target = tools / name
        shutil.copyfile(source.resolve(), target)
        target.chmod(0o500)
        captured[name] = target
    checker, indexer = captured['check-selected'], captured['export-index']
    sources = out / 'source-snapshot'
    sources.mkdir()
    source_hashes = {}
    for source in (HERE / 'engine.py', HERE / 'qualify.py', HERE / 'process.py',
                   HERE / 'test_predicate.py', Path(__file__).resolve()):
        shutil.copyfile(source, sources / source.name)
        source_hashes[source.name] = sha256(source)
    report = dict(schema='mathgraph.incremental-native-qualification.v1',
        source_git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        harness_sha256=sha256(__file__), adapter_sha256=sha256(HERE / 'engine.py'),
        checker_sha256=sha256(checker), full_checker_sha256=sha256(captured['sokonanoda']),
        indexer_sha256=sha256(indexer),
        source_sha256=source_hashes,
        workload_manifest_sha256=sha256(args.workloads / 'manifest.json'), pins=pins,
        correctness_passed=False, indexes={}, backend_comparisons={}, gates=[])
    baseline = Path(manifest['variants']['baseline']['path'])
    metadata = json.loads(baseline.open().readline())['meta']
    cases = {name: dict(info, category='pinned') for name, info in manifest['variants'].items()}
    cases.update(fixtures(out / 'adversarial-inputs', metadata))
    write(out / 'corpus.json', cases)
    for name, info in cases.items():
        observation = index_observation(name, info, indexer, out)
        report['indexes'][name] = observation
        report['gates'].append(dict(name='index:' + name, passed=observation['passed']))
        write(out / 'progress.json', compact(report))
        print('index', name, 'PASS' if observation['passed'] else 'FAIL', flush=True)
    authority = (args.authority_dir or Path(tempfile.mkdtemp(prefix='native-qualification-authority-'))).resolve()
    if authority == out or out in authority.parents:
        raise ValueError('authority secret must remain outside published evidence')
    authority.mkdir(parents=True, exist_ok=True)
    key = authority / 'issuer.key'
    init = run([sys.executable, str(HERE / 'engine.py'), '--init-key', str(key)], out / 'init-key')
    if init['returncode']:
        raise ValueError('fresh authority initialization failed')
    backends = ('python', 'native', 'differential')
    seeds = {}
    for backend in backends:
        seed = invoke(baseline, backend, checker, indexer, out / 'caches' / backend, key,
                      out / 'seeds' / (backend + '.json'), disable=True)
        seeds[backend] = seed
        report['gates'].append(dict(name='seed:' + backend,
            passed=seed['protocol_valid'] and seed['result'].get('status') == 'VERIFIED'))
    report['seeds'] = seeds
    report['gates'].append(dict(name='seed-backend-decisions-equal', passed=
        all(projection(seeds[b]['result']) == projection(seeds['python']['result']) for b in backends)))
    for name, info in cases.items():
        runs = {}
        for backend in backends:
            previous = seeds[backend]['result'].get('evidence_id')
            runs[backend] = invoke(Path(info['path']), backend, checker, indexer,
                out / 'caches' / backend, key, out / 'backend-results' / name / (backend + '.json'), previous)
        equal = all(projection(runs[b]['result']) == projection(runs['python']['result']) for b in backends)
        protocols = all(item['protocol_valid'] for item in runs.values())
        fallback_parser = True
        if report['indexes'][name]['python_fallback_required']:
            fallback_parser = all('checker_result' in runs[b]['result'] and
                runs[b]['result']['checker_result'].get('scope') != 'previously_warranted_exact_export'
                for b in ('native', 'differential'))
        report['backend_comparisons'][name] = dict(runs=runs, decisions_equal=equal,
            actual_checker_after_native_decline=fallback_parser)
        for label, passed in [('equal-decisions', equal), ('exit-protocol', protocols),
                              ('actual-parser-after-decline', fallback_parser)]:
            report['gates'].append(dict(name=name + ':' + label, passed=passed))
        print('backend', name, 'PASS' if equal and protocols and fallback_parser else 'FAIL', flush=True)
        write(out / 'progress.json', compact(report))
    original = args.original_qualification.resolve() if args.original_qualification else out / 'original-qualification'
    if not args.original_qualification:
        command = [sys.executable, str(HERE / 'qualify.py'), '--workloads', str(args.workloads.resolve()),
            '--out', str(original), '--checker', str(checker), '--full-checker', str(captured['sokonanoda']),
            '--authority-dir', str(authority / 'original'), '--identity-backend', 'native',
            '--indexer', str(indexer), '--repetitions', '3', '--optional-kernels']
        report['original_qualification_process'] = run(command, out / 'original-qualification-process', timeout=3600)
    original_summary = original / 'summary.json'
    original_data = json.loads(original_summary.read_text()) if original_summary.exists() else {}
    report['original_qualification'] = dict(path=str(original),
        summary_sha256=sha256(original_summary) if original_summary.exists() else None,
        gates=len(original_data.get('gates', [])), passed=original_data.get('qualification_passed') is True)
    report['gates'].append(dict(name='all-original-qualification-gates', passed=
        original_data.get('qualification_passed') is True and len(original_data.get('gates', [])) >= 197
        and all(g.get('passed') is True for g in original_data.get('gates', []))))
    report['gates'].append(dict(name='original-qualification-used-captured-native-tools', passed=
        original_data.get('identity_backend') == 'native'
        and original_data.get('indexer_sha256') == report['indexer_sha256']
        and original_data.get('checker_sha256') == report['checker_sha256']
        and original_data.get('full_checker_sha256') == report['full_checker_sha256']
        and original_data.get('adapter_sha256') == report['adapter_sha256']))
    report['gates'].append(dict(name='adapter-source-stable-during-qualification',
        passed=sha256(HERE / 'engine.py') == source_hashes['engine.py']))
    report['correctness_passed'] = all(g['passed'] for g in report['gates'])
    report['qualification_passed'] = report['correctness_passed']
    report['scope'] = ('Native identity is an optional accelerator. Successful native indexes equal the original '
        'Python structure exactly. Native declines use Python identity and still require the existing checker '
        'on changed bytes. Backend caches are populated separately; evidence IDs and tool provenance differ. '
        'This qualification makes no claim that incremental checking is faster than direct full checking.')
    write(out / 'summary.json', compact(report))
    rows = ['# Native identity qualification', '',
        f"Correctness passed: **{report['correctness_passed']}**", '',
        f"Index cases: {len(cases)}; original gates: {report['original_qualification']['gates']}.", '',
        '| Case | Python index | Native index | Equal or explicit decline | Backend decisions |',
        '|---|---|---|---|---|']
    for name, observation in report['indexes'].items():
        rows.append(f"| {name} | {observation['python']['indexed']} | {observation['native']['indexed']} | "
            f"{observation['passed']} | {report['backend_comparisons'][name]['decisions_equal']} |")
    rows += ['', report['scope'], '', 'Failed gates: ' + ', '.join(g['name'] for g in report['gates'] if not g['passed'])]
    (out / 'summary.md').write_text('\n'.join(rows) + '\n')
    print(json.dumps(dict(correctness_passed=report['correctness_passed'],
        failed_gates=[g['name'] for g in report['gates'] if not g['passed']])), flush=True)
    return 0 if report['correctness_passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-index', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--workloads', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--checker', type=Path, default=REPO / 'target/release/check-selected')
    parser.add_argument('--full-checker', type=Path, default=REPO / 'target/release/sokonanoda')
    parser.add_argument('--indexer', type=Path, default=REPO / 'target/release/export-index')
    parser.add_argument('--authority-dir', type=Path)
    parser.add_argument('--original-qualification', type=Path,
                        help='reuse an already completed native run of all original gates')
    args = parser.parse_args()
    if args.python_index:
        try:
            print(engine.encoded(engine.make_index(args.python_index)).decode('ascii'))
            return 0
        except (ValueError, OSError, KeyError, TypeError, RecursionError) as error:
            print(json.dumps(dict(error=type(error).__name__, message=str(error))))
            return 2
    if not args.workloads or not args.out:
        parser.error('--workloads and --out are required')
    return qualify(args)


if __name__ == '__main__':
    raise SystemExit(main())
