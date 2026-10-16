#!/usr/bin/env python3
"""Independently replay native qualification evidence and direct full kernels.

This script does not import the incremental engine or use it as an oracle. It
checks existing result/evidence files independently, then invokes three full
checkers on the exact pinned export bytes. Resource logs are review observations,
not a controlled benchmark.
"""
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import sys

from process import run, sha256

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
VARIANTS = ('baseline', 'early-definition', 'unrelated-definition', 'theorem-leaf',
            'invalid-proof', 'axiom-type', 'malformed-unused-typed-node')
NEGATIVE = {'invalid-proof', 'axiom-type', 'malformed-unused-typed-node'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique_object)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n')


def invocations(value):
    if isinstance(value, dict):
        if {'result_path', 'resources', 'result_sha256'} <= value.keys():
            yield value
        else:
            for item in value.values():
                yield from invocations(item)
    elif isinstance(value, list):
        for item in value:
            yield from invocations(item)


def argument(command, name):
    return Path(command[command.index(name) + 1])


def evaluate(args):
    out = args.out.resolve()
    if out.exists():
        raise ValueError('use a new output directory to preserve previous review evidence')
    qualification = args.qualification.resolve()
    current = read(qualification / 'summary.json')
    reference = read(args.reference)
    args.indexer_sha256 = args.indexer_sha256 or current['indexer_sha256']
    manifest = read(args.workloads / 'manifest.json')
    pins = read(HERE / 'pins.json')
    out.mkdir(parents=True)
    result = dict(schema='mathgraph.native-independent-review.v1',
                  qualification_summary=str(qualification / 'summary.json'),
                  qualification_summary_sha256=sha256(qualification / 'summary.json'),
                  reference_summary=str(args.reference.resolve()),
                  reference_summary_sha256=sha256(args.reference),
                  replay_source_sha256=sha256(__file__),
                  scope='Independent persisted-evidence checks and fresh exact-export full-kernel replay; no performance claim',
                  gates=[], evidence=[], direct={}, comparisons={})

    def gate(name, condition, **details):
        result['gates'].append(dict(name=name, passed=bool(condition), **details))
        if not condition:
            print('FAILED: ' + name, flush=True)

    historical_names = [g['name'] for g in reference['gates']]
    current_names = [g['name'] for g in current['gates']]
    gate('reference-has-exactly-197-gates', len(historical_names) == 197)
    gate('exact-original-gate-name-order', current_names == historical_names,
         reference_count=len(historical_names), current_count=len(current_names),
         missing=sorted(set(historical_names) - set(current_names)),
         added=sorted(set(current_names) - set(historical_names)))
    gate('original-gates-all-passed', all(g['passed'] for g in current['gates']) and current['qualification_passed'])
    gate('qualification-used-native-backend', current.get('identity_backend') == 'native')
    gate('frozen-native-indexer-pin', sha256(args.indexer) == args.indexer_sha256 == current.get('indexer_sha256'))
    gate('current-rust-full-checker-pin', sha256(args.full_checker) == current['full_checker_sha256'])
    gate('workload-manifest-pin', sha256(args.workloads / 'manifest.json') == current['workload_manifest_sha256'])
    for name, info in manifest['variants'].items():
        gate('exact-export:' + name, sha256(info['path']) == info['sha256'] == pins['export_sha256'][name])
    tool_paths = {'rust': args.full_checker.resolve(),
                  'cpp': Path(manifest['tools']['leanchecker']['path']),
                  'paranoid': Path(manifest['tools']['leanchecker-paranoid']['path'])}
    tool_pins = {name: sha256(path) for name, path in tool_paths.items()}
    for tool, label in (('leanchecker', 'cpp'), ('leanchecker-paranoid', 'paranoid')):
        gate('independent-release-pin:' + tool,
             tool_pins[label] == manifest['tools'][tool]['sha256'] == pins['lean_release_binaries_sha256'][tool])
    result['binary_sha256'] = {**tool_pins, 'indexer': sha256(args.indexer)}

    def invocation_key(command):
        recorded = argument(command, '--authority-key')
        if args.authority_key is None:
            return recorded
        return args.authority_key if recorded.name == 'issuer.key' else args.authority_key.with_name(recorded.name)

    checked_records = set()
    all_invocations = list(invocations(current))
    for invocation in all_invocations:
        location = Path(invocation['result_path'])
        value = read(location)
        label = str(location.relative_to(qualification))
        gate('retained-result-content-address:' + label, sha256(location) == invocation['result_sha256'])
        command = invocation['resources']['command']
        gate('native-invocation:' + label, '--identity-backend' in command and command[command.index('--identity-backend') + 1] == 'native')
        gate('process-exit-protocol:' + label,
             not invocation['resources']['timed_out'] and invocation['resources']['returncode'] ==
             {'VERIFIED': 0, 'REJECTED': 1, 'UNKNOWN': 2}.get(value.get('status')))
        if value['status'] != 'VERIFIED':
            gate('failed-invocation-no-evidence:' + label, value.get('evidence_id') is None)
            continue
        cache = argument(command, '--cache')
        key_path = invocation_key(command)
        evidence_id = value['evidence_id']
        record = cache / 'records' / (evidence_id + '.json')
        raw = record.read_bytes()
        signed = read(record)
        payload = signed['payload']
        key = key_path.read_bytes()
        gate('accepted-evidence-content-address:' + label, hashlib.sha256(raw).hexdigest() == evidence_id)
        gate('accepted-evidence-hmac:' + label, len(key) == 32 and
             hmac.compare_digest(signed['hmac_sha256'], hmac.new(key, encoded(payload), hashlib.sha256).hexdigest()))
        gate('accepted-evidence-provenance:' + label, payload['provenance'] == value['provenance'] and
             payload['provenance']['issuer_key_sha256'] == hashlib.sha256(key).hexdigest() and
             payload['provenance']['indexer_sha256'] == args.indexer_sha256)
        snapshot = cache / 'exports' / (payload['export_sha256'] + '.ndjson')
        gate('accepted-evidence-snapshot:' + label, sha256(snapshot) == payload['export_sha256'] == value['export_sha256'])
        gate('accepted-evidence-schema:' + label, payload['schema'] == value['schema'] == 'mathgraph.incremental-lean.v1' and
             payload['status'] == value['status'] == 'VERIFIED')
        index = payload['index']
        checked, reused = payload['checked_indices'], payload['reused_indices']
        count = index['count']
        gate('accepted-evidence-obligation-partition:' + label,
             all(type(i) is int for i in checked + reused) and checked == sorted(set(checked)) and
             reused == sorted(set(reused)) and not set(checked) & set(reused) and
             sorted(checked + reused) == list(range(count)))
        decisions = value['decisions']
        checked_from_decisions = [d['index'] for d in decisions if d['status'] == 'VERIFIED_NEW']
        reused_from_decisions = [d['index'] for d in decisions if d['status'] == 'VERIFIED_REUSED']
        gate('accepted-evidence-decision-partition:' + label,
             checked_from_decisions == checked and reused_from_decisions == reused and len(decisions) == count and
             value['counts']['total'] == count and value['counts']['rechecked'] == len(checked) and
             value['counts']['reused'] == len(reused) and value['counts']['scheduled'] == len(checked))
        witness_matches = len(index['declarations']) == len(decisions) and all(
            d['index'] == declaration['index'] == i and d['name'] == declaration['name'] and
            encoded(d['dependency_witness']) == encoded(dict(own=declaration['own'], closure=declaration['closure'], direct=declaration['deps']))
            for i, (d, declaration) in enumerate(zip(decisions, index['declarations'])))
        gate('accepted-evidence-witness-correspondence:' + label, witness_matches)
        if str(record) not in checked_records:
            checked_records.add(str(record))
            result['evidence'].append(dict(record=str(record), sha256=evidence_id, snapshot_sha256=payload['export_sha256'],
                                           total=count, checked=len(checked), reused=len(reused)))

    def invocation_result(name):
        return read(current['scenarios'][name]['result_path'])

    no_change = read(current['scenarios']['no-change']['runs'][0]['incremental']['result_path'])
    restart = invocation_result('cold-process-restart')
    gate('cold-process-zero-check-full-reuse', restart['status'] == 'VERIFIED' and restart['counts']['rechecked'] == 0 and
         restart['counts']['reused'] == restart['counts']['total'] and restart['counts']['scheduled'] == 0)
    fields = ('index', 'name', 'status', 'reason', 'dependency_witness')
    gate('cold-process-identical-decisions', encoded([{k: d[k] for k in fields} for d in restart['decisions']]) ==
         encoded([{k: d[k] for k in fields} for d in no_change['decisions']]))
    for name in ('cold-cache', 'missing-evidence', 'corrupt-record', 'corrupt-snapshot', 'foreign-authority', 'policy-change', 'checker-change', 'cache-disabled'):
        value = invocation_result(name)
        gate('control-full-recheck:' + name, value['status'] == 'VERIFIED' and value['counts']['reused'] == 0 and
             value['counts']['rechecked'] == value['counts']['total'])
        if name in ('cold-cache', 'missing-evidence', 'corrupt-record', 'corrupt-snapshot', 'foreign-authority'):
            gate('control-visible-cache-refusal:' + name, isinstance(value['cache_error'], str) and bool(value['cache_error']))
    for name in ('invalid-proof', 'axiom-type', 'malformed-unused-dag', 'malformed-unused-typed-node'):
        for repeat, pair in enumerate(current['scenarios'][name]['runs']):
            for mode in ('fresh', 'incremental'):
                value = read(pair[mode]['result_path'])
                gate(f'negative-no-evidence:{name}:{repeat}:{mode}', value.get('evidence_id') is None and value['status'] != 'VERIFIED')
                if name == 'malformed-unused-typed-node' and mode == 'incremental':
                    gate(f'unused-malformed-real-parser:{repeat}', value['counts']['scheduled'] == 0 and
                         value['counts']['reused'] == value['counts']['total'] and value['checker_result']['code'] == 1)

    baseline_id = read(current['baseline']['result_path'])['evidence_id']
    corrupt_record = qualification / 'corrupt-record-cache' / 'records' / (baseline_id + '.json')
    corrupt_signed = read(corrupt_record)
    baseline_command = current['baseline']['resources']['command']
    original_key = invocation_key(baseline_command).read_bytes()
    gate('corrupt-record-original-object-refused', sha256(corrupt_record) != baseline_id and
         not hmac.compare_digest(corrupt_signed['hmac_sha256'], hmac.new(original_key, encoded(corrupt_signed['payload']), hashlib.sha256).hexdigest()))
    quarantined = list((qualification / 'corrupt-snapshot-cache' / 'corrupt').glob('*'))
    gate('corrupt-snapshot-quarantine-retained', bool(quarantined) and all(
         p.is_file() and p.name[:64] == sha256(p) for p in quarantined))

    # These full-check processes consume exactly the retained original exports.
    # The existing incremental result is compared only after the independent run.
    for variant in VARIANTS:
        info = manifest['variants'][variant]
        config = out / 'configs' / (variant + '.json')
        write(config, dict(export_file_path=info['path'], use_stdin=False, permitted_axioms=['propext', 'Classical.choice', 'Quot.sound'],
                           unpermitted_axiom_hard_error=True, num_threads=1, nat_extension=True, string_extension=True,
                           print_success_message=True))
        result['direct'][variant] = {}
        expected = 1 if variant in NEGATIVE else 0
        for label, binary in tool_paths.items():
            command = [str(binary), str(config)] if label == 'rust' else [str(binary), '--from-export', info['path']]
            record = run(command, out / 'direct' / (variant + '-' + label), timeout=600)
            result['direct'][variant][label] = dict(record=record, binary_sha256=tool_pins[label], export_sha256=info['sha256'])
            gate('fresh-direct-full-kernel:' + variant + ':' + label, not record['timed_out'] and record['returncode'] == expected)
        if variant == 'baseline':
            observed = read(current['baseline']['result_path'])
            incremental_results = [observed]
        else:
            incremental_results = [read(pair[mode]['result_path']) for pair in current['scenarios'][variant]['runs'] for mode in ('fresh', 'incremental')]
        expected_incremental = 'REJECTED' if variant in NEGATIVE else 'VERIFIED'
        gate('fresh-full-kernels-versus-native-backend:' + variant,
             all(value['status'] == expected_incremental for value in incremental_results))
        result['comparisons'][variant] = dict(direct_expected_exit=expected,
                                             native_backend_expected_status=expected_incremental,
                                             native_backend_statuses=[v['status'] for v in incremental_results])
        write(out / 'progress.json', result)
        print('direct full kernels completed: ' + variant, flush=True)
    for label, path in tool_paths.items():
        gate('binary-unchanged-during-replay:' + label, sha256(path) == tool_pins[label])
    gate('indexer-unchanged-during-replay', sha256(args.indexer) == args.indexer_sha256)
    result['passed'] = all(g['passed'] for g in result['gates'])
    result['invocation_count'] = len(all_invocations)
    result['unique_evidence_record_paths_checked'] = len(checked_records)
    write(out / 'summary.json', result)
    print(json.dumps(dict(passed=result['passed'], gates=len(result['gates']),
                          failures=[g['name'] for g in result['gates'] if not g['passed']])), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification', type=Path, required=True)
    parser.add_argument('--reference', type=Path, default=HERE / 'results/local-qualified.json')
    parser.add_argument('--workloads', type=Path, required=True)
    parser.add_argument('--full-checker', '--checker', dest='full_checker', type=Path, default=REPO / 'target/release/sokonanoda')
    parser.add_argument('--authority-key', type=Path, help='Optional issuer.key override; sibling foreign.key is used for that control')
    parser.add_argument('--indexer', type=Path, default=REPO / 'target/release/export-index')
    parser.add_argument('--indexer-sha256', help='Expected frozen pin; defaults to the qualification indexer_sha256')
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    raise SystemExit(evaluate(arguments))
