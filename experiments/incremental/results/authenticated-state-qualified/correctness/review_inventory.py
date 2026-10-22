#!/usr/bin/env python3
"""Inventory actual CI summaries; no project imports, kernels, or economic arithmetic."""
import ast
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

SOURCE = 'cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5'
BASE = Path('/workspace/kernel-audit/authenticated-state/ci-cec9941')
TREE = BASE / 'extracted-compact'
DATA = TREE / 'artifacts'
OUT = BASE / 'actual-correctness-review'
REPO = Path('/workspace/mathgraph-lean-kernel-lifecycle')
FILES = {}
CHECKS = []

def require(value, message):
    if not value:
        raise ValueError(message)
    CHECKS.append(message)

def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()

def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            value.update(chunk)
    return value.hexdigest()

def strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON key: ' + key)
        value[key] = item
    return value

def parse(raw):
    return json.loads(raw, object_pairs_hook=strict_object)

def source_controls(filename):
    module = ast.parse((REPO / 'experiments/incremental' / filename).read_bytes())
    values = [ast.literal_eval(node.value) for node in module.body
              if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'REQUIRED_CONTROLS' for t in node.targets)]
    require(len(values) == 1 and len(set(values[0])) == len(values[0]), 'unique frozen control matrix: ' + filename)
    return list(values[0])

def metadata_stream(name):
    value = {}
    for line in (OUT / name).read_text().splitlines():
        path, item = parse(line)
        key = tuple(path)
        require(key not in value, 'unique selected JSON metadata path: ' + repr(key))
        value[key] = item
    return value

proof_path = TREE / 'transport-proof.json'
require(file_hash(proof_path) == '5f526db4549cafdf83c92964c6e1535e2cb1373cfaae561a609e2df976383f87', 'transport proof exact supplied hash')
proof = parse(proof_path.read_bytes())
require(proof['passed'] is True and proof['source_sha'] == SOURCE and proof['github_run_id'] == 39709067518, 'transport proof actual run/source/pass')
require(proof['files_verified'] == 8346 and proof['persisted_member_bytes_rechecked'] is True, 'transport verified persisted compact leaves')
manifest_path = TREE / 'package-manifest.json'
require(file_hash(manifest_path) == proof['index_manifest_sha256'], 'package manifest bound to transport proof')
manifest = parse(manifest_path.read_bytes())
require(manifest['source_sha'] == SOURCE and str(manifest['github_run_id']) == '39709067518', 'package manifest exact run/source')
all_files = {row['path']: row for row in manifest['all_files']}
require(len(all_files) == len(manifest['all_files']), 'package all-files paths unique')
compact_files = {row['path'] if isinstance(row, dict) else row for row in manifest['archives']['compact']['files']}
require(len(compact_files) == 8346, 'compact manifest exact member count')
require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip() == SOURCE, 'local frozen source exact CEC')

def bind(name, decode=False):
    path = DATA / name
    package_name = 'artifacts/' + name
    require(package_name in compact_files and package_name in all_files, 'selected summary in compact manifest: ' + name)
    identity = file_hash(path)
    expected = all_files[package_name]
    require(identity == expected['sha256'] and path.stat().st_size == expected['bytes'], 'selected summary bytes/hash match manifest: ' + name)
    record = dict(path=str(path), package_path=package_name, raw_bytes=path.stat().st_size, raw_sha256=identity)
    if decode:
        h = hashlib.sha256(); size = 0
        with gzip.open(path, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b''):
                h.update(chunk); size += len(chunk)
        record.update(decoded_bytes=size, decoded_sha256=h.hexdigest())
    FILES[name] = record
    return record

def load(name):
    bind(name)
    return parse((DATA / name).read_bytes())

ci = metadata_stream('ci-observations-metadata.stream.jsonl')
benchmark = metadata_stream('authenticated-state-flags.stream.jsonl')
require(ci[('source_sha',)] == SOURCE and ci[('correctness_passed',)] is True and ci[('failures',)] == [], 'CI publisher source/pass/no failures')
bind('ci-observations.json')
bind('authenticated-state/summary.json')
require(benchmark[('source_sha',)] == SOURCE and all(benchmark[(key,)] is True for key in ('source_tracked_clean','completed','correctness_passed','qualified','source_and_binary_stable')), 'qualified benchmark correctness flags and exact source')
require(benchmark[('repetitions',)] == 5 and benchmark[('cycles',)] == 10, 'qualified benchmark five complete forty-update trials')

legacy = {}
for label, folder, flag, count in (
    ('original-197','original-qualification','qualification_passed',197),
    ('native-335','native-qualification','qualification_passed',335),
    ('independent-719','native-independent-replay','passed',719),
    ('old-binary-251','native-benchmark','correctness_passed',251)):
    name = folder + '/summary.json'; d = load(name); gates = d['gates']
    require(len(gates) == count and all(g.get('passed') is True for g in gates) and d[flag] is True, 'actual required gate records all passed: ' + label)
    require(FILES[name]['raw_sha256'] == ci[('reports',label,'summary_sha256')], 'publisher binds raw summary: ' + label)
    if label != 'independent-719':
        require(d['source_git_commit'] == SOURCE, 'legacy report exact source: ' + label)
    record = dict(schema=d['schema'], raw_summary=FILES[name], gate_count=len(gates), passed_gate_count=sum(g.get('passed') is True for g in gates),
                  unique_gate_names=len({g['name'] for g in gates}), gate_names=[g['name'] for g in gates], scope=d.get('scope'))
    if label == 'original-197':
        record['optional_kernel_statuses'] = {k:v.get('status') for k,v in d['optional_kernels'].items()}
        record['scenario_verdicts'] = {k:[(r.get('incremental') or {}).get('result',{}).get('status') for r in v.get('runs',[])] for k,v in d['scenarios'].items()}
    if label == 'native-335':
        require(d['original_qualification']['summary_sha256'] == FILES['original-qualification/summary.json']['raw_sha256'], 'native qualification binds actual original summary')
        record['original_qualification'] = d['original_qualification']
    if label == 'independent-719':
        require(d['qualification_summary_sha256'] == FILES['original-qualification/summary.json']['raw_sha256'], 'independent legacy reader binds actual original summary')
        require(d['replay_source_sha256'] == file_hash(REPO / 'experiments/incremental/replay_native.py'), 'independent legacy reader source hash matches frozen CEC')
        record.update(invocation_count=d['invocation_count'], unique_evidence_record_paths_checked=d['unique_evidence_record_paths_checked'],
                      qualification_summary_sha256=d['qualification_summary_sha256'], replay_source_sha256=d['replay_source_sha256'],
                      reference_summary_sha256=d['reference_summary_sha256'])
    if label == 'old-binary-251':
        record.update(repetitions=d['repetitions'], variants=d['variants'], arms=d['arms'], baseline_ref=d['baseline_ref'],
                      baseline_source_sha256=d['baseline_source_sha256'], historical_baseline_binary_matches=d['historical_baseline_binary_matches'],
                      binary_boundary='Separately compiled source-reference baseline; historical executable byte equality is not claimed.')
    legacy[label] = record

protected = load('receipt-protected/protected-summary.json')
require(protected['qualified'] is True and protected['source_sha'] == SOURCE, 'protected aggregator exact source and qualified flag')
for profile, count in (('original',246),('expanded',229)):
    p = protected['profiles'][profile]
    require(p['source_sha'] == SOURCE and p['qualification_status'] == 'PASS' and p['required_gates'] == count and p['failed_gates'] == [], 'protected aggregator actual required count/pass: ' + profile)
    require(p['signed_kernel_backend'] == 'sha-pinned-retained-parser-v1' and p['actual_samples'] == 21, 'protected actual retained-parser backend and samples: ' + profile)
    require(not (DATA / 'receipt-protected' / profile / 'protected-matrix/retained_selected/summary.json').exists(), 'compact protected detail boundary confirmed: ' + profile)
require(FILES['receipt-protected/protected-summary.json']['raw_sha256'] == ci[('reports','protected-shared-default','summary_sha256')], 'publisher binds protected aggregator')

parity = {}
state = {}
expected_controls = source_controls('test_state_controls.py')
require(len(expected_controls) == 50, 'exact frozen fifty-control state matrix')
for profile in ('original','expanded'):
    name = 'state-parity-' + profile + '/summary.json'; d = load(name)
    require(d['passed'] is True and d['source_sha'] == SOURCE and len(d['steps']) == 4 and d['cold']['replayed_revisions'] == 4, 'actual four changed states and cold replay: ' + profile)
    require(d['unchanged']['scheduled'] == 0 and d['unchanged']['rechecked'] == 0, 'unchanged state zero selected: ' + profile)
    for s in d['steps']:
        require(len(s['state_id']) == len(s['export_sha256']) == 64 and s['state_id'] != s['export_sha256'], 'state/export identity domains distinct: ' + profile)
        require(s['fresh_rust_returncode'] == 0 and s['receipt_audit']['issuer_hmac_valid'] is True and s['receipt_audit']['all_content_addresses_valid'] is True and s['counts']['rechecked'] == s['counts']['scheduled'], 'parity actual recorded kernel/receipt/count audit: ' + profile)
    require(FILES[name]['raw_sha256'] == ci[('reports','authenticated-state-representation-parity',profile,'summary_sha256')], 'publisher binds parity summary: ' + profile)
    parity[profile] = dict(raw_summary=FILES[name], changed_revisions=4, cold_replayed_revisions=4, unchanged_counts=d['unchanged'],
        checked_counts_in_revision_order=[s['counts']['rechecked'] for s in d['steps']], total_obligations=d['steps'][0]['counts']['total'],
        latestness_scope=d['cold']['latestness_scope'], recorded_issuer_hmac_and_content_address_audits=True)
    name = 'state-controls-' + profile + '/summary.json'; d = load(name); controls = d['controls']; names=[c['name'] for c in controls]
    require(d['passed'] is True and d['source_sha'] == SOURCE and d['schema'] == 'mathgraph.authenticated-state-controls.v1', 'state controls schema/source/pass: ' + profile)
    require(len(names) == len(set(names)) == 50 and set(names) == set(d['required_controls']) == set(expected_controls) and len(d['required_controls']) == 50, 'actual complete unique frozen fifty-control matrix: ' + profile)
    require(all(c.get('passed') is True for c in controls), 'all actual state controls passed: ' + profile)
    brief=[]
    for c in controls:
        result=c.get('result') or {}; status=result.get('status'); oracles=c.get('independent_kernel_rejections')
        entry={k:c[k] for k in ('name','passed','observed_refusal','refusal_boundary','authority_scope','poisoned','accepted_records_unchanged','expected_head_and_state_unchanged','subsequent_in_place_update_refused','historical_orphan_receipt_only_after_genuine_kernel_acceptance','state_domain') if k in c}
        entry.update(result_status=status, result_reason=result.get('reason'), evidence_id=result.get('evidence_id'), scheduled=(result.get('counts') or {}).get('scheduled'))
        if oracles:
            require(status == 'REJECTED' and result['checker_result']['code'] == 1 and result['evidence_id'] is None, 'actual negative result rejects without evidence: ' + profile + ':' + c['name'])
            require(set(oracles) == {'rust','leanchecker','leanchecker-paranoid'} and all(o['returncode'] == 1 and o['timed_out'] is False for o in oracles.values()), 'recorded three-kernel negative agreement: ' + profile + ':' + c['name'])
            require(c['attempt_identity']['state_id'] is None and c['attempt_identity']['scope'] == 'unaccepted_attempt_for_independent_oracle_only', 'negative attempted export is not accepted state: ' + profile + ':' + c['name'])
            if c['name'] == 'unused-malformed-dag-zero-selected':
                require(result['counts']['scheduled'] == 0, 'malformed admitted DAG rejected with zero selected: ' + profile)
            entry.update(exact_negative_export_sha256=c['exact_negative_export_sha256'], attempt_identity=c['attempt_identity'],
                         recorded_kernel_returncodes={k:o['returncode'] for k,o in oracles.items()})
        if c['name'] in ('failed-receipt-persistence-does-not-promote-state','failed-persistence-does-not-promote-state'):
            require(status == 'UNKNOWN' and result['evidence_id'] is None and c['expected_head_and_state_unchanged'] is True and c['subsequent_in_place_update_refused'] is True, 'persistence failure refuses result/head promotion and poisoned reuse: ' + profile + ':' + c['name'])
        brief.append(entry)
    require(FILES[name]['raw_sha256'] == ci[('reports','authenticated-state-adversarial-controls',profile,'summary_sha256')], 'publisher binds state controls: ' + profile)
    state[profile] = dict(raw_summary=FILES[name], control_count=50, passed_control_count=50, adversary_scope=d['adversary_scope'],
        explicit_result_status_counts=dict(Counter((c.get('result') or {}).get('status','NO_RESULT_STATUS') for c in controls)),
        unknown_controls=[c['name'] for c in brief if c['result_status']=='UNKNOWN'], rejected_controls=[c['name'] for c in brief if c['result_status']=='REJECTED'], controls=brief)

reader = load('authenticated-state-independent/summary.json')
require(reader['schema'] == 'mathgraph.authenticated-state-independent-replay.v1' and reader['source_sha'] == SOURCE and reader['passed'] is True and reader['completed'] is True, 'actual CI reader exact source/schema/completed/pass')
require(reader['all_qualified_fingerprints_selected_sets_and_verdicts_agree'] is True and reader['historical_hmac_reauthenticated'] is False, 'CI reader explicitly separates identity/verdict agreement from historical HMAC reauthentication')
require(FILES['authenticated-state-independent/summary.json']['raw_sha256'] == ci[('reports','authenticated-state-lifecycle','independent_replay_sha256')], 'publisher binds actual CI independent reader')
positive = Counter(); negative=Counter(); profile_counts={}
for profile,p in reader['profiles'].items():
    require(p['passed'] is True and len(p['steps']) == 40 and len(p['primary_pairs']) == 5, 'CI reader forty observed states and five primary pairs: ' + profile)
    transitions=sum(a['transitions'] for q in p['primary_pairs'] for a in q['arms'].values())
    require(transitions == p['primary_transition_count'] == 400, 'CI reader two retained primary arms total four hundred transitions: ' + profile)
    for s in p['steps']:
        for backend,k in s['kernels'].items():
            require(k['returncode'] == 0 and k['timed_out'] is False, 'CI reader recorded positive kernel accepted: ' + profile + ':' + backend)
            positive[backend]+=1
    profile_counts[profile]={k:p[k] for k in ('fresh_kernel_processes','primary_transition_count','declaration_witnesses_checked','obligation_count','baseline_sha256')}
for c in reader['controls']:
    require(c['passed'] is True and c['control_count'] == 50 and len(c['negatives']) == 2, 'CI reader reviewed complete controls and two exact negative inputs: ' + c['profile'])
    for n in c['negatives']:
        for backend,k in n['kernels'].items():
            require(k['returncode'] == 1 and k['timed_out'] is False, 'CI reader recorded negative kernel rejected: ' + c['profile'] + ':' + backend)
            negative[backend]+=1
require(sum(positive.values()) + sum(negative.values()) == reader['fresh_kernel_processes'] == 108, 'CI reader exact one hundred eight recorded fresh kernel processes')
require(reader['primary_transition_count'] == 800 and reader['control_count'] == 100 and reader['archive_objects_validated'] == 190 and reader['declaration_witnesses_checked'] == 7242720, 'CI reader exact recorded inventory counters')
reader_brief={k:reader[k] for k in ('schema','source_sha','completed','passed','fresh_kernel_processes','primary_transition_count','control_count','archive_objects_validated','declaration_witnesses_checked','historical_hmac_reauthenticated','boundary','rust_binary_scope')}
reader_brief.update(raw_summary=FILES['authenticated-state-independent/summary.json'], profiles=profile_counts,
                    positive_kernel_processes_by_backend=dict(positive), negative_kernel_processes_by_backend=dict(negative))

shadow = load('retained-parser-shadow/summary.json')
require(shadow['complete'] is True and shadow['source_sha'] == SOURCE and shadow['profile_count'] == 2 and len(shadow['negative_controls']) == 4 and all(c['passed'] is True for c in shadow['negative_controls'].values()), 'actual retained-parser shadow four controls and two profiles')
require(FILES['retained-parser-shadow/summary.json']['raw_sha256'] == ci[('reports','retained-parser-shadow','summary_sha256')], 'publisher binds retained-parser shadow')
receipt = load('receipt-comparison/summary.json')
require(receipt['completed'] is True and receipt['qualified'] is True and receipt['correctness_passed'] is True and receipt['source_sha'] == SOURCE, 'actual canonical/shared receipt comparison correctness/source')
require(FILES['receipt-comparison/summary.json']['raw_sha256'] == ci[('reports','receipt-comparison','summary_sha256')], 'publisher binds canonical/shared receipt comparison')
additional = dict(retained_parser_shadow=dict(raw_summary=FILES['retained-parser-shadow/summary.json'],scope=shadow['scope'],negative_controls=shadow['negative_controls']),
    receipt_comparison=dict(raw_summary=FILES['receipt-comparison/summary.json'],scope=receipt['scope'],pairs=ci[('reports','receipt-comparison','pairs')],actual_arms=ci[('reports','receipt-comparison','actual_arms')],cold_replays=ci[('reports','receipt-comparison','cold_replays')]))
for kind,label in (('revision-chain-tests','revision-chain-acceptance-recovery-smoke'),('revision-chain-controls','revision-chain-adversarial-controls')):
    for profile in ('original','expanded'):
        name=kind+'-'+profile+'/summary.json.gz'; record=bind(name,decode=True)
        require(record['decoded_sha256'] == ci[('reports',label,profile,'summary_sha256')], 'publisher binds exact decoded legacy lineage report: ' + name)
        additional[kind+'-'+profile]=dict(raw_summary=record,publisher_metadata={str(k[-1]):v for k,v in ci.items() if k[:3]==('reports',label,profile)})

for kind in ('source','binaries'):
    before=DATA/(kind+'-before.sha256');after=DATA/(kind+'-after.sha256')
    bind(kind+'-before.sha256');bind(kind+'-after.sha256')
    require(before.read_bytes() == after.read_bytes(), 'CI recorded before/after manifest bytes equal: ' + kind)
    key='source_manifest_sha256' if kind=='source' else 'binary_manifest_sha256'
    require(file_hash(before) == ci[('reports','source-and-binaries',key)], 'publisher binds before/after manifest: ' + kind)

require(FILES['authenticated-state/summary.json']['raw_sha256'] == ci[('reports','authenticated-state-lifecycle','summary_sha256')], 'publisher binds actual benchmark summary without economic recomputation')
result=dict(schema='mathgraph.actual-ci-correctness-inventory.v1', classification='ACTUAL_CI_SUMMARY_INVENTORY_ONLY',
    inventory_consistent=True, source_sha=SOURCE, ci_run=39709067518, transport_proof_sha256=file_hash(proof_path),
    transport_scope=proof['scope'], selected_raw_summaries=FILES, legacy=legacy,
    retained_protected=dict(raw_summary=FILES['receipt-protected/protected-summary.json'],profiles=protected['profiles'],
        review_boundary='Compact contains the protected aggregator only. The raw 246/229 retained matrices are absent; their individual records were checked by the CI publisher, not independently inspected in this inventory.'),
    state_parity=parity,state_controls=state,ci_reader=reader_brief,additional_preserved_reports=additional,
    benchmark_correctness_flags={k[0]:v for k,v in benchmark.items()},
    scope_limits=[
        'Summary inventory and hash/source/count bindings only. No local kernel replay, project import, new gate execution or economic arithmetic was performed.',
        'Gate records overlap, include repeated invocations and protocol checks, and must not be summed as independent theorem counts.',
        'Historical issuer HMACs were not reauthenticated by the public CI reader; its explicit false flag and boundary are retained. Runtime parity summaries separately record issuer-HMAC checks.',
        'Key-resigned parser adversaries possess issuer authority; injected bytes are not asserted to be outputs of the source producer.',
        'Cold latestness depends on a caller-supplied expected head; there is no external monotonic service or general rollback-freshness proof.',
        'The bounded Lean theorem does not verify the NDJSON dependency extractor, source/export/parser/identity executable bridge, or production kernel locality.',
        'Workloads are frozen original and expanded Lean/Std universes and scheduled source changes; no all-Lean, unrestricted edit, new axiom-policy, asymptotic or memory-peak conclusion follows.',
        'An UNKNOWN update is a refusal to issue evidence, not a kernel proof of invalidity. Exception refusals without result status are kept separate from UNKNOWN and REJECTED.',
        'Persistence failures prevent head/state promotion and in-place reuse; a genuine prior-kernel-acceptance orphan receipt may exist, as explicitly recorded by those controls.',
        'Separately compiled historical source baselines do not imply historical executable byte identity.'
    ], verification=dict(fresh_inventory_assertions=len(CHECKS),checks=CHECKS))
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'review.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
with (OUT/'summary-hashes.tsv').open('w') as f:
    f.write('path\traw_bytes\traw_sha256\tdecoded_bytes\tdecoded_sha256\n')
    for name,r in sorted(FILES.items()):
        f.write('\t'.join(str(v) for v in (name,r['raw_bytes'],r['raw_sha256'],r.get('decoded_bytes',''),r.get('decoded_sha256','')))+'\n')
lines=['ACTUAL CI CORRECTNESS SUMMARY INVENTORY — CONSISTENT', 'Source '+SOURCE+'; run39709067518.',
    'Transport proof '+file_hash(proof_path)+' binds 8,346 compact members / 3,528,974,155 uncompressed bytes.',
    'This inventory freshly checks selected raw summary hashes, exact source, literal gate/control counts and stored result/domain fields. It does not rerun any kernel, reauthenticate private historical HMACs, or recompute economic arithmetic.', '',
    'Legacy raw gate records: original197/197; native335/335; independent719/719; old-binary251/251. All recorded passed flags are literally true. Native and independent reports bind the actual original-summary hash; the independent reader source hash matches frozen CEC.',
    'Independent legacy reader reports72 invocations and35 unique evidence-record paths. Original-binary251 uses separately compiled baseline source '+legacy['old-binary-251']['baseline_ref']+'; historical executable byte-match flags are false for check-selected and sokonanoda.',
    'Retained protected aggregator: original246 required gates, expanded229; PASS, no failed gates,21 samples/profile, backend sha-pinned-retained-parser-v1. Its detailed matrices are NOT in compact; individual raw protected records were not re-inspected here.', '',
    'New representation parity: four changed revisions/profile, four cold-replayed revisions/profile, unchanged scheduled/rechecked0. Actual selected counts in revision order: original413/1/413/1 of3436; expanded672/260/672/260 of11653. Each recorded state ID differs from its materialized-export SHA; runtime receipt HMAC/content-address audits and fresh-Rust returncode0 are recorded.',
    'New adversarial matrix:50 distinct required controls/profile,100 total, all passed; frozen source names match exactly. Per profile:3 controls with explicit VERIFIED results,7 UNKNOWN,2 REJECTED,38 without a result-status field. Absence of a status is not relabeled UNKNOWN.',
    'Explicit UNKNOWN names (each profile): '+', '.join(state['original']['unknown_controls'])+'.',
    'Explicit REJECTED names (each profile): '+', '.join(state['original']['rejected_controls'])+'. Both have checker code1, no evidence ID, unaccepted-attempt state_id null, and recorded Rust/C++/paranoid returncode1 without timeout. The malformed admitted DAG case schedules0 obligations.',
    'Persistence UNKNOWN controls preserve expected head/state and refuse subsequent in-place reuse. They do not imply zero durable writes: historical orphan-receipt scope is separately recorded.',
    'Authority/domain refusals cover forged/foreign issuer HMACs, wrong parent/environment/version, modified prepared source capture, malformed/changed deltas, persisted-object corruption, missing/pinned heads, and full-export/sparse-export/state receipt-domain separation. Key-resigned parser fixtures possess issuer authority and are not asserted to be source-produced exports.', '',
    'Actual CI reader:108 recorded fresh kernel processes =96 positive and12 negative; backend totals Rust84,C++12,paranoid12. It reports800 primary retained-arm transitions,100 controls,190 archive objects and7,242,720 declaration witnesses (repeated witnesses across arms/revisions, not distinct theorems).',
    'Per profile:400 primary transitions,48 positive fresh kernels; original3436 obligations/1,649,280 declaration witnesses; expanded11653/5,593,440. Five pairs/profile each contain40 full-export and40 state transitions. The CI reader historical_hmac_reauthenticated flag is FALSE.',
    'CI reader boundary: '+reader['boundary'], '',
    'Additional preserved correctness evidence: retained-parser shadow has4 passing unsigned parser-only negative controls; canonical/shared receipt comparison is completed/qualified/correctness_passed with20 pairs,40 arms,4 cold replays. Legacy chain smoke/control reports are byte-hash bound (raw gzip and exact decoded JSON digests both preserved), without rerunning their controls.', '',
    'Limits:', *['- '+s for s in result['scope_limits']], '',
    'Exact raw/decoded hashes: summary-hashes.tsv. Detailed per-control statuses/refusals/domain fields and all raw legacy gate names: review.json.',
    'Fresh verification assertions: '+str(len(CHECKS))+'.']
(OUT/'review.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(inventory_consistent=True,source_sha=SOURCE,ci_run=39709067518,selected_files=len(FILES),fresh_assertions=len(CHECKS),output=str(OUT))))
