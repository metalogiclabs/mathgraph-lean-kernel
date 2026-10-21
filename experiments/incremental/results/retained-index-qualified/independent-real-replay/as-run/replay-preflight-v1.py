#!/usr/bin/env python3
"""Independent exact-object reconstruction and real kernel replay.

No producer_delta, incremental verifier or retained index session is imported or
executed. The old Python full indexer is extracted directly from qualified Git.
Diagnostic elapsed times are not benchmark or new economic evidence.
"""
import gzip
import shutil
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

REPO = Path('/workspace/mathgraph-lean-kernel')
EVIDENCE = Path('/workspace/kernel-audit/delta-expanded-qualified-v2')
OUT = Path(__file__).resolve().parent
SOURCE = 'ef434eb2477fb64d7fd90fdf23f55bd0b35a0243'
ORIGINAL = '4496042c75368f6c35675a9b131c960080afa518'
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


def raw_file(path):
    path=Path(path)
    if path.exists():return path.read_bytes()
    compressed=path.with_name(path.name+'.gz')
    return gzip.decompress(compressed.read_bytes())


def object_raw(root,category,ident,suffix):
    assert type(ident)is str and len(ident)==64 and set(ident)<=set('0123456789abcdef')
    raw=raw_file(root/'cache'/category/(ident+suffix))
    assert sha(raw)==ident
    return raw


def main():
    roots=Path('/workspace/kernel-audit/retained-index')
    report_paths={'original-current':roots/'original-delta-regression/summary.json',
                  'expanded-current-smoke':roots/'harness-final-smoke-2/summary.json',
                  'expanded-historical-controls':Path('/workspace/kernel-audit/delta-expanded-qualified-v2/summary.json')}
    reports={name:read_json(path) for name,path in report_paths.items()}
    current=reports['original-current'];smoke=reports['expanded-current-smoke'];historical=reports['expanded-historical-controls']
    assert current['run_completed'] and current['correctness_passed'] and len(current['gates'])==243
    assert all(g['passed']is True for g in current['gates'])
    assert smoke['run_completed'] and not smoke['correctness_passed'] and smoke['qualification_status']=='INCOMPLETE'
    assert len(smoke['gates'])==53 and all(g['passed']is True for g in smoke['gates'])
    source_matches={}
    for label,report in [('original-current',current),('expanded-current-smoke',smoke)]:
        source_matches[label]={}
        for filename,digest in report['measured_source_sha256'].items():
            raw=subprocess.check_output(['git','show',SOURCE+':'+filename],cwd=REPO)
            assert sha(raw)==digest==file_hash(REPO/filename),(label,filename)
            source_matches[label][filename]=digest
    now=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    assert now==SOURCE
    specifications={
        'current-rust':current['tools']['full_checker'],
        'qualified449-rust':smoke['tools']['qualified449_sokonanoda'],
        'normal-cpp':current['tools']['leanchecker'],
        'paranoid-cpp':current['tools']['leanchecker-paranoid'],
        'current-zero-selected':current['tools']['checker'],
        'qualified449-zero-selected':smoke['tools']['qualified449_check-selected'],
        'current-index':current['tools']['indexer'],
        'qualified449-index':smoke['tools']['qualified449_export-index']}
    tools={}
    (OUT/'tools').mkdir(exist_ok=True)
    for name,info in specifications.items():
        assert file_hash(info['path'])==info['sha256'],(name,info)
        destination=OUT/'tools'/name
        shutil.copyfile(info['path'],destination);destination.chmod(0o500)
        assert file_hash(destination)==info['sha256']
        tools[name]=dict(input_path=info['path'],path=str(destination),sha256=info['sha256'])
    original_pins=json.loads(subprocess.check_output(['git','show',SOURCE+':experiments/incremental/pins.json'],cwd=REPO))
    expanded_pins=json.loads(subprocess.check_output(['git','show',SOURCE+':experiments/incremental/delta-pins.json'],cwd=REPO))
    positive=next(s for s in current['samples'] if s['variant']=='early-definition' and not s['cold_replay'])
    root=Path(positive['result_path']).parent/'session'
    receipt=json.loads(object_raw(root,'records',positive['evidence_id'],'.json'),object_pairs_hook=strict)['payload']
    representation=json.loads(object_raw(root,'representations',receipt['delta_representation'],'.json'),object_pairs_hook=strict)
    delta=root/'cache/deltas'/(representation['delta_sha256']+'.ndjson')
    assert file_hash(delta)==representation['delta_sha256']
    raw=raw_file(root/'baseline-cache/exports'/(original_pins['export_sha256']['baseline']+'.ndjson'))
    assert sha(raw)==original_pins['export_sha256']['baseline']
    original_baseline=OUT/'original-baseline.ndjson';original_baseline.write_bytes(raw)
    expanded_sample=next(s for s in smoke['samples'] if s['profile']=='expanded' and s['variant']=='early-definition')
    arm=expanded_sample['arms']['retained'];expanded_root=Path(arm['result_path']).parent/'session'
    expanded_result=json.loads(raw_file(arm['result_path']),object_pairs_hook=strict)
    assert sha(raw_file(arm['result_path']))==arm['result_sha256']
    expanded_receipt=json.loads(object_raw(expanded_root,'records',expanded_result['evidence_id'],'.json'),object_pairs_hook=strict)['payload']
    expanded_representation=json.loads(object_raw(expanded_root,'representations',expanded_receipt['delta_representation'],'.json'),object_pairs_hook=strict)
    expanded_delta=Path(arm['result_path']).parent/'delta.ndjson'
    assert file_hash(expanded_delta)==arm['delta_sha256']==expanded_representation['delta_sha256']
    raw=raw_file(expanded_root/'baseline-cache/exports'/(expanded_pins['export_sha256']['baseline']+'.ndjson'))
    assert sha(raw)==expanded_pins['export_sha256']['baseline']
    expanded_baseline=OUT/'expanded-baseline.ndjson';expanded_baseline.write_bytes(raw)
    layouts={'original':baseline_layout(original_baseline),'expanded':baseline_layout(expanded_baseline)}
    cases=[dict(profile='original',name='early-definition',snapshot=positive['snapshot'],delta=delta,
                source_report='original-current',expected=0),
           dict(profile='expanded',name='early-definition',snapshot=arm['sealed_snapshot'],delta=expanded_delta,
                source_report='expanded-current-smoke',expected=0)]
    control_names=['signed-invalid-proof','signed-invalid-axiom','unused-invalid-node-zero-selection-parser',
                   'unused-invalid-node-dag-only-zero-selection-parser']
    for profile,report,label in [('original',current,'original-current'),('expanded',historical,'expanded-historical-controls')]:
        for name in control_names:
            control=report['controls'][name]
            assert control['result']['status']=='REJECTED' and control['result']['evidence_id']is None
            assert control['result']['receipt_id']is None
            parent=Path(control['result_path']).parent
            assert not list((parent/'session/cache/records').glob('*.json'))
            cases.append(dict(profile=profile,name=name,snapshot=control['snapshot'],delta=parent/'fixture-delta.ndjson',
                source_report=label,expected=1,original_control_status=control['result']['status']))
    results=[]
    for case in cases:
        name=case['profile']+'-'+case['name'];expected=case['expected']
        materialized=reconstruct(layouts[case['profile']],case['delta'],OUT/(name+'.ndjson'))
        assert materialized['sha256']==case['snapshot']['sha256'] and materialized['bytes']==case['snapshot']['bytes']
        configuration=OUT/(name+'.config.json');write_json(configuration,config(materialized['path']))
        runs=[]
        for tool in ['current-rust','qualified449-rust','normal-cpp','paranoid-cpp']:
            args=[tools[tool]['path'],configuration] if tool.endswith('rust') else [tools[tool]['path'],'--silent','--from-export',materialized['path']]
            runs.append(dict(tool=tool,**command(name+'-'+tool,args,expected)))
        zero='unused-invalid' in case['name']
        if zero:
            indices=OUT/(name+'.indices.json');indices.write_bytes(b'[]\n')
            for tool in ['current-zero-selected','qualified449-zero-selected']:
                runs.append(dict(tool=tool,**command(name+'-'+tool,[tools[tool]['path'],configuration,indices],1)))
        results.append(dict(profile=case['profile'],name=case['name'],source_report=case['source_report'],
            reconstruction=materialized,kernels=runs,zero_selection_verified=zero,
            original_no_acceptance_record=expected==1,expected=expected))
        write_json(OUT/'progress.json',dict(completed=[c['profile']+':'+c['name'] for c in results]))
        print(json.dumps(dict(completed=name,kernel_codes=[r['returncode'] for r in runs],sha256=materialized['sha256'])),flush=True)
    references={'original':Path(current['references']['early-definition']['export_path']),
                'expanded':Path(historical['references']['early-definition']['export_path'])}
    pins={'original':original_pins,'expanded':expanded_pins}
    oracle_source=subprocess.check_output(['git','show',ORIGINAL+':experiments/incremental/engine.py'],cwd=REPO)
    oracle_file=OUT/'qualified449_full_python_index.py';oracle_file.write_bytes(oracle_source)
    spec=importlib.util.spec_from_file_location('qualified449_full_python_index',oracle_file)
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    indexes={}
    for profile,reference in references.items():
        assert file_hash(reference)==pins[profile]['export_sha256']['early-definition']
        composite=OUT/(profile+'-early-definition.ndjson')
        outputs={};commands=[]
        for label,path,tool in [('current-composite',composite,'current-index'),
                                ('qualified449-composite',composite,'qualified449-index'),
                                ('current-pinned-source-export',reference,'current-index')]:
            cfg=OUT/(profile+'-'+label+'.config.json');write_json(cfg,config(path))
            commands.append(command(profile+'-'+label+'-index',[tools[tool]['path'],cfg],0))
            outputs[label]=read_json(OUT/(profile+'-'+label+'-index.stdout'))
        values=list(outputs.values())
        assert all(canonical(index)==canonical(values[0]) for index in values)
        python=oracle.make_index(composite)
        assert canonical(python)==canonical(values[0])
        accepted=receipt if profile=='original' else expanded_receipt
        assert canonical(accepted['index'])==canonical(values[0])
        write_json(OUT/(profile+'-qualified449-python-index.json'),python)
        indexes[profile]=dict(count=values[0]['count'],typed_index_sha256=sha(canonical(values[0])),
            fresh_current_native_equals_qualified449_native_equals_frozen449_python=True,
            equals_pinned_ordinary_source_export=True,equals_actual_accepted_index=True,commands=commands,
            source_export=dict(path=str(reference),sha256=file_hash(reference)))
    metadata={label:dict(path=str(path),sha256=file_hash(path),
        recorded_source=reports[label].get('source_git_commit',reports[label].get('source_sha')),
        recorded_worktree_status=reports[label].get('source_git_status'),
        recorded_tracked_clean=reports[label].get('source_worktree_tracked_clean'),
        run_completed=reports[label].get('run_completed'),qualification_status=reports[label].get('qualification_status'),
        correctness_passed=reports[label].get('correctness_passed')) for label,path in report_paths.items()}
    final=dict(status='PASS_INDEPENDENT_CURRENT_AND_QUALIFIED449_REAL_KERNEL_REPLAY',
        current_clean_source=SOURCE,input_reports=metadata,measured_source_matches_current_commit=source_matches,
        actual_tools=tools,helper_sha256=file_hash(__file__),oracle_source=ORIGINAL,
        oracle_source_sha256=sha(oracle_source),cases=results,positive_full_index_parity=indexes,
        full_kernel_commands=40,zero_selected_parser_commands=8,
        scope=['No producer_delta, current incremental verifier or retained-index execution occurs here.',
               'Forty fresh full kernel commands and eight zero-selected parser commands execute exact independently reconstructed inputs.',
               'Current local reports retain recorded initial1e20 dirty-source metadata. Their measured file hashes match ef434 independently; this does not retroactively make them clean-source CI runs.',
               'Expanded positive comes from final incomplete one-repetition smoke; four expanded fault inputs are explicitly attributed to historical f397 qualification and independently rechecked now.',
               'This is correctness/input replay, not economic qualification, source completeness proof, historical HMAC-secret authentication or a runtime-results promotion.'])
    assert sum(len(c['kernels']) for c in results)==48
    write_json(OUT/'summary.json',final)
    print(json.dumps(dict(status=final['status'],cases=len(results),full_kernel_commands=40,zero_selected_parser_commands=8)),flush=True)


if __name__=='__main__':main()
