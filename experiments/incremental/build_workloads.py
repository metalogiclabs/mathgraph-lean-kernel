#!/usr/bin/env python3
"""Compile pinned source edits; retain genuine Lean 4.35 exports and mutations."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from process import run, sha256

HERE = Path(__file__).resolve().parent
TOOLCHAIN = 'leanprover/lean4:v4.35.0'
ROOTS = [
    'IncrementalWorkload.early', 'IncrementalWorkload.dependent',
    'IncrementalWorkload.dependent_spec',
    'Std.HashMap.getElem?_insert', 'Std.HashMap.getElem?_erase',
    'IncrementalWorkload.unrelated', 'IncrementalWorkload.leaf',
    'IncrementalWorkload.typed', 'IncrementalWorkload.typed_identity',
]
EDITS = {
    'baseline': None,
    'early-definition': ('IncrementalWorkload/Base.lean', 'def early : Nat := 17', 'def early : Nat := 23'),
    'unrelated-definition': ('IncrementalWorkload/Leaves.lean', 'n * n + 3', 'n * n + 5'),
    'theorem-leaf': ('IncrementalWorkload/Leaves.lean', ':= Eq.refl n', ':= Eq.symm (Eq.refl n)'),
    'type-change': ('IncrementalWorkload/Base.lean', 'def typed : Nat := 7', 'def typed : Bool := true'),
}


def decode_names(records):
    names = {0: ''}
    for obj in records:
        if 'in' in obj:
            val = obj.get('str', obj.get('num'))
            pre = names[val['pre']]
            part = val.get('str', str(val.get('i', '')))
            names[obj['in']] = pre + ('.' if pre else '') + part
    return names


def describe(path):
    counts = {}
    names = {}
    for line in path.open():
        obj = json.loads(line)
        for kind in ('axiom', 'def', 'thm', 'opaque', 'quot', 'inductive'):
            if kind in obj:
                counts[kind] = counts.get(kind, 0) + 1
    return dict(path=str(path), sha256=sha256(path), bytes=path.stat().st_size,
                record_counts=counts, declaration_records=sum(counts.values()))


def mutate(baseline, out, kind):
    records = [json.loads(line) for line in baseline.open()]
    names = decode_names(records)
    if kind == 'invalid-proof':
        # An existing Nat literal is valid syntax but has the wrong theorem type.
        nat_value = next(obj['ie'] for obj in records if 'natVal' in obj)
        target = next(obj['thm'] for obj in records if 'thm' in obj and names[obj['thm']['name']] == 'IncrementalWorkload.leaf')
        target['value'] = nat_value
    elif kind == 'axiom-type':
        prop = next(obj['ie'] for obj in records if obj.get('sort') == 0)
        target = next(obj['axiom'] for obj in records if 'axiom' in obj and names[obj['axiom']['name']] == 'propext')
        target['type'] = prop
    elif kind == 'toolchain-metadata':
        records[0]['meta']['lean']['githash'] = '0' * 40
    elif kind == 'malformed-unused-dag':
        # All declarations remain byte-for-byte identical. Parsing the complete
        # stream must still fail; reusing the old declarations cannot accept it.
        records.append({'ie':999999999,'app':{'fn':999999997,'arg':999999998}})
    elif kind == 'malformed-unused-typed-node':
        # The identity extractor can hash this unused scalar row without
        # changing any declaration. The real Rust parser must still run even
        # when the scheduled kernel obligation list is empty, and reject it.
        records.append({'ie':max(obj['ie'] for obj in records if 'ie' in obj)+1,
                        'bvar':'not-an-integer'})
    else:
        raise ValueError(kind)
    with out.open('w') as stream:
        for obj in records:
            stream.write(json.dumps(obj, separators=(',', ':'), ensure_ascii=False) + '\n')


def build(out, elan):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    pin = json.loads((HERE / 'pins.json').read_text())
    for rel, expected in pin['workload_sources_sha256'].items():
        if sha256(HERE / 'workload' / rel) != expected:
            raise ValueError('pinned workload source changed: ' + rel)
    manifest = dict(toolchain=TOOLCHAIN, roots=ROOTS, variants={}, tools={})
    toolprefix = Path(subprocess.check_output([elan, 'run', TOOLCHAIN, 'lean', '--print-prefix'], text=True).strip())
    for name in ('lean', 'leanexport', 'leanchecker', 'leanchecker-paranoid', 'lean4lean', 'nanoda_bin', 'con-leche', 'con-ron'):
        binary = toolprefix / 'bin' / name
        manifest['tools'][name] = dict(path=str(binary), exists=binary.is_file(),
                                       sha256=sha256(binary) if binary.is_file() else None)
        if manifest['tools'][name]['sha256'] != pin['lean_release_binaries_sha256'][name]:
            raise ValueError('pinned Lean release executable missing or changed: ' + name)
    for variant, edit in EDITS.items():
        target = out / variant
        source = target / 'source'
        if source.exists():
            shutil.rmtree(source)
        shutil.copytree(HERE / 'workload', source, ignore=shutil.ignore_patterns('.lake', '*.olean', '*.ilean', 'lake-manifest.json'))
        if edit:
            path = source / edit[0]
            text = path.read_text()
            if text.count(edit[1]) != 1:
                raise ValueError('edit marker not unique: ' + variant)
            path.write_text(text.replace(edit[1], edit[2]))
        built = run([elan, 'run', TOOLCHAIN, 'lake', 'build', 'Workload'], target / 'build', cwd=source)
        if built['returncode']:
            raise RuntimeError('source build failed: ' + variant)
        command = [elan, 'run', TOOLCHAIN, 'lake', 'env', 'leanexport', 'Workload', '--', *ROOTS]
        exported = run(command, target / 'export', cwd=source)
        export = target / 'export.ndjson'
        shutil.copyfile(exported['stdout_path'], export)
        stderr = Path(exported['stderr_path']).read_text()
        if exported['returncode'] or 'Constant ' in stderr or 'PANIC' in stderr or not export.stat().st_size:
            raise RuntimeError('incomplete export: ' + variant + ': ' + stderr)
        info = describe(export)
        if info['sha256'] != pin['export_sha256'][variant]:
            raise RuntimeError('generated export differs from exact development pin: '+variant)
        metadata = json.loads(export.open().readline())['meta']['lean']
        if metadata['githash'] != pin['lean_githash'] or metadata['version'] != '4.35.0':
            raise RuntimeError('export compiler metadata differs from pinned toolchain')
        if info['declaration_records'] < 3000:
            raise RuntimeError('real dependency workload unexpectedly small')
        info.update(build=built, export_process=exported, source_sha256={str(p.relative_to(source)):sha256(p) for p in source.rglob('*.lean')})
        manifest['variants'][variant] = info
    baseline = out / 'baseline' / 'export.ndjson'
    for variant in ('invalid-proof', 'axiom-type', 'toolchain-metadata', 'malformed-unused-dag', 'malformed-unused-typed-node'):
        target = out / variant
        target.mkdir(exist_ok=True)
        export = target / 'export.ndjson'
        mutate(baseline, export, variant)
        manifest['variants'][variant] = dict(**describe(export), mutation=variant,
            original_export_sha256=sha256(baseline), scope='NDJSON boundary mutation; not a source proof')
        if manifest['variants'][variant]['sha256'] != pin['export_sha256'][variant]:
            raise RuntimeError('boundary mutation differs from exact export pin: '+variant)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--elan', default=shutil.which('elan') or str(Path.home() / '.elan/bin/elan'))
    args = parser.parse_args()
    result = build(args.out, args.elan)
    print(json.dumps({name: {k: val for k, val in entry.items() if k in ('sha256', 'bytes', 'declaration_records')} for name, entry in result['variants'].items()}, indent=2))
