#!/usr/bin/env python3
"""Independent exact-object reconstruction and real kernel replay.

No producer_delta, incremental verifier or retained index session is imported or
executed. The old Python full indexer is extracted directly from qualified Git.
Diagnostic elapsed times are not benchmark or new economic evidence.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

REPO = EVIDENCE = OUT = SOURCE = None
ORIGINAL = 'c5ab12699338aa57b7e9d48b15d4a7409e453c7b'
SIMPLE = {'axiom', 'def', 'opaque', 'thm'}
DECLARATIONS = SIMPLE | {'quot', 'inductive'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for raw in iter(lambda: stream.read(1 << 20), b''):
            h.update(raw)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


def strict(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=strict)


def write_json(path, value):
    Path(path).write_bytes(json.dumps(value, indent=2, sort_keys=True).encode() + b'\n')


def content_object(root, category, ident, suffix):
    assert isinstance(ident, str) and len(ident) == 64 and set(ident) <= set('0123456789abcdef')
    path = root / 'cache' / category / (ident + suffix)
    assert file_hash(path) == ident, path
    return path


def config(path):
    return dict(export_file_path=str(path), permitted_axioms=['propext', 'Classical.choice', 'Quot.sound'],
                unpermitted_axiom_hard_error=True, nat_extension=True, string_extension=True,
                num_threads=1, use_stdin=False)


def command(name, arguments, expected):
    started = time.perf_counter()
    run = subprocess.run([str(x) for x in arguments], capture_output=True, timeout=180)
    stdout, stderr = OUT / (name + '.stdout'), OUT / (name + '.stderr')
    stdout.write_bytes(run.stdout)
    stderr.write_bytes(run.stderr)
    record = dict(command=[str(x) for x in arguments], returncode=run.returncode,
                  expected_returncode=expected, elapsed_seconds=time.perf_counter()-started,
                  stdout_path=str(stdout), stderr_path=str(stderr),
                  stdout_sha256=sha(run.stdout), stderr_sha256=sha(run.stderr))
    write_json(OUT / (name + '.command.json'), record)
    assert run.returncode == expected, record
    return record


def classify(raw):
    row = json.loads(raw, object_pairs_hook=strict)
    tags = set(row) & DECLARATIONS
    assert len(tags) <= 1
    return row, next(iter(tags)) if tags else None


def insert_name(names, row):
    if 'in' not in row:
        return
    ident = row['in']
    assert type(ident) is int and ident not in names
    tag = 'str' if 'str' in row else 'num'
    part = row[tag]
    component = part['str'] if tag == 'str' else part['i']
    assert part['pre'] in names
    names[ident] = (tag, names[part['pre']], component)


def baseline_layout(path):
    names = {0: ('anonymous',)}
    dags, declarations = [], []
    with path.open('rb') as stream:
        for raw in stream:
            row, tag = classify(raw)
            insert_name(names, row)
            if tag is None:
                dags.append(raw)
            else:
                key = (tag, names[row[tag]['name']]) if tag != 'inductive' else None
                declarations.append((key, raw))
    return names, dags, declarations


def reconstruct(baseline, delta, output):
    names, dags, declarations = baseline
    names = dict(names)
    replacements, additions = {}, []
    for raw in delta.read_bytes().splitlines(keepends=True):
        assert raw.endswith(b'\n')
        row, tag = classify(raw)
        insert_name(names, row)
        if tag:
            assert tag in SIMPLE
            key = tag, names[row[tag]['name']]
            assert key not in replacements
            replacements[key] = raw
        else:
            assert 'meta' not in row
            additions.append(raw)
    remaining = set(replacements)
    with output.open('wb') as stream:
        stream.writelines(dags)
        stream.writelines(additions)
        for key, raw in declarations:
            if key in replacements:
                stream.write(replacements[key])
                remaining.remove(key)
            else:
                stream.write(raw)
    assert not remaining
    return dict(path=str(output), sha256=file_hash(output), bytes=output.stat().st_size,
                delta_path=str(delta), delta_sha256=file_hash(delta),
                delta_bytes=delta.stat().st_size, replacements=len(replacements), appended_rows=len(additions))


def arguments():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example after generating a complete local expanded qualification:
  python replay-delta-evidence.py --repo . \
    --evidence artifacts/delta-expanded-qualification \
    --out artifacts/delta-expanded-independent

A copied evidence directory is automatically rebased from its recorded sample
paths. --artifact-root optionally relocates sibling workload/build artifacts
relative to the recorded evidence directory's parent. Repository-local binaries
are rebased to --repo. For tools outside those trees, repeat --tool NAME=PATH;
all replacements must still match the qualification's exact binary SHA256.
The helper is specific to the expanded 11,653-declaration profile. It requires
full persisted qualification artifacts, workload exports and actual tools;
a compact summaries-only archive cannot supply independent kernel inputs.
""")
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source', help='Qualified commit; defaults to report.source_git_commit')
    parser.add_argument('--artifact-root', type=Path,
                        help='New parent of the original evidence/workload/build artifact directories')
    parser.add_argument('--tool', action='append', default=[], metavar='NAME=PATH',
                        help='Relocate an actual tool; exact recorded binary hash remains mandatory')
    return parser.parse_args()


def relative_to(path, root):
    try:
        return path.relative_to(root)
    except ValueError:
        return None


class InputPaths:
    def __init__(self, report, repo, evidence, artifact_root=None):
        # All qualification samples are written below <evidence>/samples/<case>.
        first = Path(report['samples'][0]['result_path'])
        if first.parent.parent.name != 'samples':
            raise ValueError('cannot infer recorded evidence root from sample path')
        self.old_evidence = first.parent.parent.parent
        self.old_artifacts = self.old_evidence.parent
        self.repo, self.evidence = repo, evidence
        self.artifacts = artifact_root
        raw = Path(report['tools']['full_checker']['path'])
        # Standard Cargo paths are portable when the checkout moves.
        self.old_repo = (raw.parent.parent.parent if raw.parent.name == 'release'
                         and raw.parent.parent.name == 'target' else None)
        self.relocations = {}

    def resolve(self, value):
        path = Path(value)
        suffix = relative_to(path, self.old_evidence)
        if suffix is not None:
            result = self.evidence / suffix
        elif self.artifacts is not None and relative_to(path, self.old_artifacts) is not None:
            result = self.artifacts / path.relative_to(self.old_artifacts)
        elif self.old_repo is not None and relative_to(path, self.old_repo) is not None:
            result = self.repo / path.relative_to(self.old_repo)
        elif path.is_absolute():
            result = path
        else:
            result = self.repo / path
        self.relocations[str(path)] = str(result)
        return result


def main():
    global REPO, EVIDENCE, OUT, SOURCE
    if not __debug__:
        raise ValueError('run without Python -O: audit assertions must remain enabled')
    args = arguments()
    REPO, EVIDENCE, OUT = (path.resolve() for path in (args.repo, args.evidence, args.out))
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError('use a fresh output directory; preserve earlier replay evidence')
    if relative_to(OUT, EVIDENCE) is not None or relative_to(EVIDENCE, OUT) is not None:
        raise ValueError('output and input evidence directories must be separate')
    OUT.mkdir(parents=True, exist_ok=True)
    report = read_json(EVIDENCE / 'summary.json')
    SOURCE = args.source or report['source_git_commit']
    assert report['source_git_commit'] == SOURCE and report['run_completed']
    assert report['correctness_passed'] and report['qualification_status'] == 'PASS'
    assert report['profile'] == 'std-hashmap-expanded-v1'
    assert len(report['gates']) >= 226 and all(g['passed'] is True for g in report['gates'])
    paths = InputPaths(report, REPO, EVIDENCE,
                       args.artifact_root.resolve() if args.artifact_root else None)
    tools = copy.deepcopy(report['tools'])
    overrides = {}
    for value in args.tool:
        name, separator, path = value.partition('=')
        if not separator or name not in tools or name in overrides:
            raise ValueError('tool override must be a unique recorded NAME=PATH')
        overrides[name] = Path(path).resolve()
    for name, info in tools.items():
        info['recorded_path'] = info['path']
        info['path'] = str(overrides.get(name) or paths.resolve(info['path']))
    tool_pins = {}
    for name, info in tools.items():
        actual = file_hash(info['path'])
        assert actual == info['sha256'], (name, actual, info['sha256'])
        tool_pins[name] = dict(path=info['path'], sha256=actual)
    files = ['experiments/incremental/engine.py', 'experiments/incremental/producer_delta.py',
             'experiments/incremental/DeltaProducer.lean', 'src/identity.rs', 'src/parser.rs',
             'src/bin/index_session.rs', 'experiments/incremental/delta-pins.json']
    source_pins = {}
    for name in files:
        raw = subprocess.check_output(['git', 'show', SOURCE + ':' + name], cwd=REPO)
        assert sha(raw) == file_hash(REPO / name), name
        source_pins[name] = sha(raw)
    sample = next(s for s in report['samples'] if s['variant'] == 'early-definition' and not s['cold_replay'])
    root = paths.resolve(sample['result_path']).parent / 'session'
    receipt_path = content_object(root, 'records', sample['evidence_id'], '.json')
    receipt = read_json(receipt_path)['payload']
    representation = read_json(content_object(root, 'representations', receipt['delta_representation'], '.json'))
    delta_path = content_object(root, 'deltas', representation['delta_sha256'], '.ndjson')
    baseline_path = root / 'baseline-cache' / 'exports' / (
        report['profile_pins']['export_sha256']['baseline'] + '.ndjson')
    assert file_hash(baseline_path) == report['profile_pins']['export_sha256']['baseline']
    baseline = baseline_layout(baseline_path)
    cases = [('early-definition', sample, root, delta_path, 0)]
    for name in ['signed-invalid-proof', 'signed-invalid-axiom',
                 'unused-invalid-node-zero-selection-parser',
                 'unused-invalid-node-dag-only-zero-selection-parser']:
        control = report['controls'][name]
        control_root = paths.resolve(control['result_path']).parent / 'session'
        cases.append((name, control, control_root, paths.resolve(control['result_path']).parent / 'fixture-delta.ndjson', 1))
    results = []
    for name, evidence, case_root, changed, expected in cases:
        materialized = reconstruct(baseline, changed, OUT / (name + '.ndjson'))
        assert materialized['sha256'] == evidence['snapshot']['sha256'], (name, materialized, evidence['snapshot'])
        assert materialized['bytes'] == evidence['snapshot']['bytes']
        if expected:
            assert evidence['result']['status'] == 'REJECTED'
            assert evidence['result'].get('evidence_id') is None
            assert evidence['result'].get('receipt_id') is None
            assert not list((case_root / 'cache' / 'records').glob('*.json'))
            attestation = read_json(paths.resolve(evidence['result_path']).parent / 'fixture-attestation.json')['payload']
            assert attestation['delta_sha256'] == materialized['delta_sha256']
        path = Path(materialized['path'])
        configuration = OUT / (name + '.config.json')
        write_json(configuration, config(path))
        runs = [command(name + '-rust', [tools['full_checker']['path'], configuration], expected)]
        for tool in ['leanchecker', 'leanchecker-paranoid']:
            runs.append(command(name + '-' + tool,
                                [tools[tool]['path'], '--silent', '--from-export', path], expected))
        if 'unused-invalid' in name:
            indices = OUT / (name + '.indices.json')
            indices.write_bytes(b'[]\n')
            runs.append(command(name + '-zero-selected',
                                [tools['checker']['path'], configuration, indices], 1))
        results.append(dict(name=name, reconstruction=materialized, kernels=runs,
                            no_new_acceptance=expected == 1,
                            zero_selection_verified='unused-invalid' in name))
        write_json(OUT / 'progress.json', dict(completed=[r['name'] for r in results]))
        print(json.dumps(dict(completed=name, sha256=materialized['sha256'], kernel_codes=[x['returncode'] for x in runs])), flush=True)
    reference = paths.resolve(report['references']['early-definition']['export_path'])
    assert file_hash(reference) == report['profile_pins']['export_sha256']['early-definition']
    index_runs, indexes = [], {}
    for name, path in [('composite', OUT / 'early-definition.ndjson'), ('original-source-export', reference)]:
        configuration = OUT / (name + '.index-config.json')
        write_json(configuration, config(path))
        index_runs.append(command(name + '-fresh-native-index', [tools['indexer']['path'], configuration], 0))
        indexes[name] = read_json(OUT / (name + '-fresh-native-index.stdout'))
    assert canonical(indexes['composite']) == canonical(indexes['original-source-export'])
    assert canonical(indexes['composite']) == canonical(receipt['index'])
    assert len(indexes['composite']['declarations']) == 11653
    raw_python = subprocess.check_output(['git', 'show', ORIGINAL + ':experiments/incremental/engine.py'], cwd=REPO)
    old_source = OUT / 'original_pinned_full_indexer.py'
    old_source.write_bytes(raw_python)
    old_spec = importlib.util.spec_from_file_location('original_full_index_oracle', old_source)
    old = importlib.util.module_from_spec(old_spec)
    old_spec.loader.exec_module(old)
    # Full-input oracle only; no current adapter or incremental function executes.
    python_index = old.make_index(OUT / 'early-definition.ndjson')
    assert canonical(python_index) == canonical(indexes['composite'])
    write_json(OUT / 'original-python-full-index.json', python_index)
    final = dict(status='PASS_INDEPENDENT_EXPANDED_RECONSTRUCTION_INDEX_AND_KERNEL_REPLAY',
        input_report=str(EVIDENCE / 'summary.json'), input_report_sha256=file_hash(EVIDENCE / 'summary.json'),
        qualified_source=SOURCE, current_git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        critical_source_matches_qualified=source_pins, actual_tool_pins=tool_pins,
        decoder_script_sha256=file_hash(__file__), path_relocations=paths.relocations,
        tool_overrides={name: str(path) for name, path in overrides.items()}, baseline=dict(path=str(baseline_path), sha256=file_hash(baseline_path)),
        cases=results, positive_fresh_index_commands=index_runs,
        positive_index_equality=dict(native_reconstruction_equals_native_pinned_source_export=True,
            original_c5_python_equals_native_reconstruction=True, accepted_receipt_equals_full_index=True,
            count=11653, typed_index_sha256=sha(canonical(indexes['composite'])),
            original_python_source_commit=ORIGINAL, original_python_source_sha256=sha(raw_python)),
        source_export=dict(path=str(reference), sha256=file_hash(reference)),
        limitations=['Independent exact-byte reconstruction/full checking; not a new economic benchmark.',
            'No producer_delta or incremental verifier or retained-index APIs executed.',
            'Signed envelope content addresses checked; no independent old-secret HMAC authentication performed.',
            'No general completeness theorem or unrestricted source replacement claim.'])
    write_json(OUT / 'summary.json', final)
    print(json.dumps(dict(status=final['status'], case_count=len(results), full_kernel_commands=sum(3 for _ in results),
                          zero_selected_commands=2, positive_full_index_agreement=True)), flush=True)


if __name__ == '__main__':
    main()
