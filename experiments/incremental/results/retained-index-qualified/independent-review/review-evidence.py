#!/usr/bin/env python3
"""Independent structural, source, command and arithmetic audit of delta evidence.

No engine/controller imports, no kernel execution and no historical HMAC
reauthentication. Compact archives are reviewed as retained reports; --full
also inspects retained outputs/configurations/results and native index witnesses.
Never treats an in-progress report or a green provider badge as qualification.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import re
import subprocess
import sys

VARIANTS = ('early-definition', 'unrelated-definition', 'theorem-leaf', 'baseline')
CONTINUED = 'c5ab12699338aa57b7e9d48b15d4a7409e453c7b'
SCHEMA = 'mathgraph.authenticated-producer-delta-qualification.v1'
KERNEL_CONTROLS = ('signed-invalid-proof', 'signed-invalid-axiom',
                   'unused-invalid-node-zero-selection-parser',
                   'unused-invalid-node-dag-only-zero-selection-parser')
CAUSES = {
    'forged-attestation': 'issuer authentication failed',
    'authenticated-attestation-version-drift': 'wrong authority domain',
    'authenticated-baseline-environment-drift': 'transition environment/version/base mismatch',
    'authenticated-base-export-drift': 'transition environment/version/base mismatch',
    'authenticated-producer-version-drift': 'transition environment/version/base mismatch',
    'unannounced-source-change': 'source modifications outside the reported patch',
    'false-announced-name': 'expected_changed_names differs from complete local comparison',
    'outside-announced-region': 'source modifications outside the reported patch',
    'import-environment-drift': 'source modifications outside the reported patch',
}
STORAGE_CAUSES = {
    'corrupt-baseline-receipt': 'evidence content address mismatch',
    'corrupt-baseline-export': 'baseline storage corruption',
    'corrupt-genesis': 'delta storage corruption: genesis',
    'corrupt-accepted-delta-receipt': 'delta storage corruption: records',
    'corrupt-persisted-delta-bytes': 'delta storage corruption: deltas',
    'corrupt-persisted-transition': 'delta storage corruption: transitions',
    'corrupt-persisted-representation': 'delta storage corruption: representations',
    'foreign-issuer-authority': 'evidence issuer authentication failed',
}
ORIGINAL_COUNTS = {'baseline': (0,3436), 'early-definition': (413,3023),
                   'unrelated-definition': (1,3435), 'theorem-leaf': (1,3435)}
HEX64 = re.compile(r'[0-9a-f]{64}\Z')


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('nonfinite JSON constant: ' + value)


def decode(raw):
    return json.loads(raw, object_pairs_hook=strict_object, parse_constant=reject_constant)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


def object_hash(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def hash_file(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1 << 20), b''):
            result.update(part)
    return result.hexdigest()


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle-1] + ordered[middle]) / 2


def economics(samples):
    updates = [sample['apply_wall_seconds'] for sample in samples]
    directs = [sample['direct_wall_seconds'] for sample in samples]
    middle_update, middle_direct = median(updates), median(directs)
    ratio = middle_update / middle_direct
    rng = random.Random(20261016)
    bootstrap = []
    for _ in range(10000):
        selected = [rng.randrange(len(samples)) for _ in samples]
        bootstrap.append(median([updates[i] for i in selected]) /
                         median([directs[i] for i in selected]))
    bootstrap.sort()
    bounds = [bootstrap[int(q * 9999)] for q in (.025, .975)]
    wins = sum(left < right for left, right in zip(updates, directs))
    passed = ratio < 1 and 2*wins > len(samples) and bounds[1] < 1
    return dict(apply_median_wall_seconds=middle_update,
                direct_median_wall_seconds=middle_direct, median_ratio=ratio,
                paired_wins=wins, paired_count=len(samples),
                bootstrap_ratio_interval_95=bounds, bootstrap_repetitions=10000,
                bootstrap_seed=20261016, passed=passed,
                status='SPEEDUP' if passed else 'NO_SPEEDUP',
                median_setup_wall_seconds=median([sample['setup_wall_seconds'] for sample in samples]),
                median_setup_plus_apply_component_sum=median([
                    sample['setup_wall_seconds'] + sample['apply_wall_seconds'] for sample in samples]))


class Reviewer:
    def __init__(self, summary, expected_source, source_root=None, full=False):
        self.summary_path = Path(summary).resolve()
        self.root = self.summary_path.parent
        self.expected_source = expected_source
        self.source_root = Path(source_root).resolve() if source_root else None
        self.full = full
        self.checks = []
        self.report = None
        self.sources = {}
        self.index_cache = {}
        self.available_files = set()
        self.absent_files = set()

    def check(self, name, condition, detail=None):
        self.checks.append(dict(name=name, passed=bool(condition), detail=detail))
        return bool(condition)

    def require(self, name, condition, detail=None):
        if not self.check(name, condition, detail):
            raise ValueError(name)

    def duration(self, name, value, allow_zero=False):
        return self.require(name, type(value) in (int,float) and math.isfinite(value)
                            and (value >= 0 if allow_zero else value > 0), value)

    def hex(self, name, value):
        return self.require(name, type(value) is str and HEX64.fullmatch(value) is not None)

    def near(self, name, left, right):
        return self.require(name, type(left) in (float,int) and type(right) in (float,int)
                            and math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12),
                            dict(recorded=left, recomputed=right))

    def gate(self, name):
        gate = self.gates.get(name)
        return self.require('required-gate:' + name, gate is not None and
                            gate.get('required') is True and gate.get('passed') is True
                            and gate.get('status') == 'PASS')

    def locate(self, stored, required=False):
        candidate = Path(stored) if isinstance(stored,str) else None
        choices = [candidate] if candidate else []
        if candidate:
            for marker in ('samples', 'controls', 'references'):
                if marker in candidate.parts:
                    choices.append(self.root.joinpath(*candidate.parts[candidate.parts.index(marker):]))
        found = next((path for path in choices if path.is_file()), None)
        if found:
            self.available_files.add(str(found))
        else:
            self.absent_files.add(str(stored))
            if required:
                raise ValueError('missing retained file: ' + str(stored))
        return found

    def source(self, relative):
        if relative in self.sources:
            return self.sources[relative]
        self.require('safe-source-path:' + relative,
                     not Path(relative).is_absolute() and '..' not in Path(relative).parts)
        if self.source_root:
            raw = subprocess.check_output(['git', 'show', self.expected_source + ':' + relative],
                                          cwd=self.source_root)
            self.sources[relative] = raw
            return raw
        return None

    def command(self, name, record, code, cpp=False, snapshot=None):
        self.require(name + ':record', type(record) is dict)
        command = record.get('command')
        self.require(name + ':argv', type(command) is list and len(command) >= 2 and
                     all(type(value) is str for value in command))
        self.require(name + ':verdict', record.get('timed_out') is False and
                     type(record.get('returncode')) is int and record['returncode'] == code)
        self.duration(name + ':wall', record.get('wall_seconds'))
        if 'completed_child_cpu_seconds' in record:
            self.duration(name + ':cpu', record['completed_child_cpu_seconds'], allow_zero=True)
        for stream in ('stdout','stderr'):
            self.hex(name + ':' + stream + '-sha', record.get(stream + '_sha256'))
            self.require(name + ':' + stream + '-path',
                         type(record.get(stream + '_path')) is str and bool(record[stream + '_path']))
            path = self.locate(record.get(stream + '_path'), required=self.full)
            if path and self.full:
                self.require(name + ':' + stream + '-bytes', hash_file(path) == record[stream + '_sha256'])
        if cpp:
            self.require(name + ':cpp-native-input', len(command) == 3 and command[1] == '--from-export'
                         and (snapshot is None or command[2] == snapshot))
        elif snapshot is not None:
            config = self.locate(command[1], required=self.full)
            if config:
                config = decode(config.read_bytes())
                self.require(name + ':same-live-composite', config.get('export_file_path') == snapshot)
                self.require(name + ':real-policy', config.get('use_stdin') is False and
                             config.get('num_threads') == 1 and config.get('nat_extension') is True and
                             config.get('string_extension') is True and
                             config.get('unpermitted_axiom_hard_error') is True and
                             config.get('permitted_axioms') == ['propext','Classical.choice','Quot.sound'])
        return record

    def command_json(self, record):
        path = self.locate(record.get('stdout_path'), required=self.full)
        return decode(path.read_bytes()) if path else None

    def partition(self, name, sample, count):
        audit = sample.get('partition_audit', {})
        self.require(name + ':partition-audit', type(audit) is dict)
        checked, reused = audit.get('checked_indices'), audit.get('reused_indices')
        self.require(name + ':integer-partition', type(checked) is list and type(reused) is list
                     and all(type(value) is int for value in checked + reused))
        self.require(name + ':disjoint-complete-partition', len(checked) + len(reused) == count
                     and len(set(checked + reused)) == count and set(checked + reused) == set(range(count)))
        self.require(name + ':actual-kernel-count', audit.get('actual_kernel_checked') == len(checked)
                     and audit.get('actual_kernel_total') == count and
                     audit.get('independently_replayed_reused') == len(reused) and
                     audit.get('identity_witnesses_checked') == count)
        accepted = sample.get('persisted_acceptance_audit', {})
        self.require(name + ':record-authentication-observed', accepted.get('issuer_hmac_valid') is True
                     and accepted.get('all_content_addresses_valid') is True)
        self.require(name + ':actual-receipt-size', type(accepted.get('receipt_bytes')) is int and
                     accepted['receipt_bytes'] > 0 and type(accepted.get('delta_bytes')) is int
                     and accepted['delta_bytes'] >= 0 and accepted.get('contains_complete_index') is True)
        return checked, reused

    def full_partition(self, name, old, current, actual_checked, actual_reused):
        same_global = (encoded(old['meta']) == encoded(current['meta']) and
                       encoded(old['builtins']) == encoded(current['builtins']) and
                       old['complex'] == current['complex'])
        same_schedule = same_global and old['schedule'] == current['schedule']
        before = {declaration['key']: declaration for declaration in old['declarations']}
        prefix_end = 0
        for declaration in current['declarations']:
            previous = before.get(declaration['key'])
            if not (same_global and previous is not None and
                    previous['index'] == declaration['index'] and
                    previous['own'] == declaration['own']):
                break
            prefix_end += 1
        expected_reused = []
        for declaration in current['declarations']:
            previous = before.get(declaration['key'])
            local = (same_schedule and declaration['kind'] in {'axiom','def','thm','opaque'}
                     and previous is not None and previous['own'] == declaration['own']
                     and previous['closure'] == declaration['closure'])
            if declaration['index'] < prefix_end or local:
                expected_reused.append(declaration['index'])
        reused_set = set(expected_reused)
        expected_checked = [declaration['index'] for declaration in current['declarations']
                            if declaration['index'] not in reused_set]
        self.require(name + ':fresh-identity-replay', expected_checked == actual_checked
                     and expected_reused == actual_reused)

    def sample(self, sample, count, warm):
        variant, repetition = sample.get('variant'), sample.get('repetition')
        name = variant + ':' + str(repetition)
        self.require(name + ':no-execution-error', 'error' not in sample)
        self.require(name + ':baseline-verdict', sample.get('baseline_result',{}).get('status') == 'VERIFIED')
        self.hex(name + ':acceptance-id', sample.get('evidence_id'))
        for field in ('apply_wall_seconds','direct_wall_seconds','start_wall_seconds',
                      'session_constructor_wall_seconds','setup_wall_seconds'):
            self.duration(name + ':' + field, sample.get(field))
        self.require(name + ':setup-includes-constructor', sample['setup_wall_seconds'] + 1e-6 >=
                     sample['start_wall_seconds'] + sample['session_constructor_wall_seconds'])
        snapshot = sample.get('snapshot',{})
        self.hex(name + ':snapshot-sha', snapshot.get('sha256'))
        self.require(name + ':sealed-input', type(snapshot.get('seals')) is int and
                     snapshot['seals'] & 15 == 15 and snapshot.get('required_seals') == 15
                     and type(snapshot.get('bytes')) is int and snapshot['bytes'] > 0 and
                     re.fullmatch(r'/proc/[0-9]+/fd/[0-9]+', snapshot.get('path','')) is not None)
        self.command(name + ':direct', sample.get('direct_rust'), 0, snapshot=snapshot['path'])
        self.require(name + ':direct-tool', sample['direct_rust']['command'][0] ==
                     self.report['tools']['full_checker']['path'])
        self.near(name + ':direct-measurement-consistency', sample['direct_wall_seconds'],
                  sample['direct_rust']['wall_seconds'])
        checked, reused = self.partition(name, sample, count)
        if self.report['profile'] in ('original-qualified-3436','original-v1'):
            self.require(name + ':original-qualified-counts', (len(checked),len(reused)) == ORIGINAL_COUNTS[variant])
        oracle = sample.get('full_index_oracle')
        self.command(name + ':native-index', oracle, 0, snapshot=snapshot['path'])
        self.require(name + ':indexer-tool', oracle['command'][0] == self.report['tools']['indexer']['path'])
        for gate in ('baseline_accepted','snapshot_hash_matches_controller',
                     'fresh_full_rust_accepts_exact_composite',
                     'composite_index_equals_independent_pinned_export',
                     'actual_kernel_counts_and_independent_reuse_partition',
                     'independently_authenticated_persisted_acceptance'):
            self.gate(gate + ':' + variant + '-' + str(repetition))
        if not self.report.get('profile_pins'):
            self.gate('preserved_original_qualified_counts:' + variant + '-' + str(repetition))
        if repetition == 0:
            self.gate('composite_python_native_exact:' + variant + '-0')
            self.command(name + ':python-index', sample.get('python_index_oracle'), 0)
            for tool in ('leanchecker','leanchecker-paranoid'):
                self.gate('actual_full_' + tool + ':' + variant + '-0')
                record = sample.get('independent_kernels',{}).get(tool)
                self.command(name + ':' + tool, record, 0, cpp=True, snapshot=snapshot['path'])
                self.require(name + ':' + tool + '-pin', record['command'][0] == self.report['tools'][tool]['path'])
        if self.full:
            current = self.command_json(oracle)
            self.require(name + ':fresh-pinned-index-identity', object_hash(current) ==
                         self.report['references'][variant]['typed_index_sha256'])
            self.full_partition(name, self.index_cache['baseline'], current, checked, reused)
            result_path = self.locate(sample.get('result_path'), required=True)
            result = decode(result_path.read_bytes())
            self.require(name + ':actual-result', result.get('status') == 'VERIFIED' and
                         result.get('evidence_id') == sample['evidence_id'] and
                         result.get('export_sha256') == snapshot['sha256'])
            proof = decode(result.get('checker_result',{}).get('stdout',''))
            self.require(name + ':actual-kernel-stdout', result['checker_result'].get('code') == 0 and
                         proof.get('checked') == len(checked) and proof.get('total_declarations') == count and
                         proof.get('scope') == 'selected_obligations_under_caller_trusted_environment')
            decisions = result.get('decisions',[])
            self.require(name + ':actual-decision-partition',
                         [d['index'] for d in decisions if d['status']=='VERIFIED_NEW'] == checked and
                         [d['index'] for d in decisions if d['status']=='VERIFIED_REUSED'] == reused and
                         len(decisions) == count)
            for decision,declaration in zip(decisions,current['declarations']):
                self.require(name + ':actual-witness:' + str(declaration['index']),
                    decision['name'] == declaration['name'] and decision['index'] == declaration['index'] and
                    encoded(decision['dependency_witness']) == encoded(dict(
                        own=declaration['own'], closure=declaration['closure'], direct=declaration['deps'])))
            self.require(name + ':outer-timing-includes-controller', sample['apply_wall_seconds'] + 1e-6 >=
                         result['timings']['end_to_end_seconds'])
            baseline = self.locate(sample.get('baseline_result_path'), required=True)
            self.require(name + ':baseline-result-digest', hash_file(baseline) == sample['baseline_result_sha256'])

    def controls(self):
        controls = self.report.get('controls',{})
        for name in KERNEL_CONTROLS:
            self.require('control-present:' + name, name in controls)
            record = controls[name]
            result = record.get('result',{})
            self.require(name + ':actual-rejection', result.get('status') == 'REJECTED' and
                         result.get('checker_result',{}).get('code') == 1 and
                         result.get('evidence_id') is None and result.get('receipt_id') is None)
            self.gate('control_refuses_and_issues_no_acceptance:' + name)
            self.gate('genuine_selected_parser_or_kernel_rejects:' + name)
            self.gate('no_new_persisted_acceptance:' + name)
            for tool in ('rust','leanchecker','leanchecker-paranoid'):
                self.gate('fresh_full_' + tool + '_rejects:' + name)
                self.command(name + ':' + tool, record.get('independent_kernel_rejections',{}).get(tool),
                             1, cpp=tool!='rust', snapshot=record['snapshot']['path'])
            if name.startswith('unused-invalid'):
                self.require(name + ':zero-selected', result.get('counts',{}).get('scheduled') == 0)
                self.gate('genuine_parser_invoked_with_zero_selected:' + name)
                self.gate('independent_zero_selected_parser_rejects:' + name)
                actual = record.get('independent_zero_selected_parser')
                self.command(name + ':fresh-zero-parser', actual, 1, snapshot=record['snapshot']['path'])
                self.require(name + ':actual-zero-parser-command', len(actual['command']) == 3 and
                             actual['command'][0] == self.report['tools']['checker']['path'])
                indices = self.locate(actual['command'][2], required=self.full)
                if indices:
                    self.require(name + ':empty-selected-file', decode(indices.read_bytes()) == [])
            if self.full:
                path = self.locate(record.get('result_path'), required=True)
                self.require(name + ':result-file-digest', hash_file(path) == record['result_sha256'])
                self.require(name + ':result-file-verdict', decode(path.read_bytes())['status'] == 'REJECTED')
        for name,cause in CAUSES.items():
            self.require('control-present:' + name, name in controls)
            record = controls[name]
            self.gate('no_new_persisted_acceptance:' + name)
            result = record.get('result')
            if result is not None:
                self.require(name + ':specific-refusal', result.get('status') == 'UNKNOWN' and
                             result.get('evidence_id') is None and result.get('receipt_id') is None and
                             cause in str(result.get('reason','')))
                self.gate('control_refuses_and_issues_no_acceptance:' + name)
            else:
                self.require(name + ':specific-exception', cause in record.get('exception_refusal','') and
                             'execution_error' not in record)
                self.gate('control_refuses_before_acceptance:' + name)
        for name,cause in STORAGE_CAUSES.items():
            self.require('control-present:' + name, name in controls)
            record = controls[name]
            refusal = record.get('observed_refusal','')
            if 'result' in record:
                result = record['result']
                self.require(name + ':no-acceptance', result.get('status') in ('UNKNOWN','REJECTED') and
                             result.get('evidence_id') is None and cause in str(result.get('reason','')))
            else:
                self.require(name + ':actual-storage-auth-cause', cause in refusal and
                             'execution_error' not in record)
            if name == 'foreign-issuer-authority':
                self.gate('foreign_issuer_cannot_replay_acceptance')
            else:
                self.gate('cold_restart_corrupt_storage_refused:' + name.removeprefix('corrupt-'))

    def audit(self, report=None):
        self.report = report if report is not None else decode(self.summary_path.read_bytes())
        r = self.report
        try:
            self.require('schema', r.get('schema') == SCHEMA)
            self.require('completed-qualification', r.get('run_completed') is True and
                         r.get('correctness_passed') is True and r.get('qualification_status') == 'PASS'
                         and r.get('observed_gates_status') == 'PASS')
            self.require('exact-source', r.get('source_git_commit') == self.expected_source and
                         re.fullmatch('[0-9a-f]{40}', self.expected_source) is not None)
            self.require('continued-qualified-source', r.get('continued_qualified_source') == CONTINUED)
            gates = r.get('gates')
            self.require('nonempty-gates', type(gates) is list and bool(gates))
            self.require('unique-gate-names', len({gate['name'] for gate in gates}) == len(gates))
            self.gates = {gate['name']:gate for gate in gates}
            self.require('all-required-gates-pass', all(type(gate.get('required')) is bool and
                         (not gate['required'] or (gate.get('passed') is True and gate.get('status') == 'PASS'))
                         for gate in gates) and any(gate['required'] for gate in gates))
            profile = r.get('profile')
            self.require('known-profile', profile in ('original-qualified-3436','original-v1','std-hashmap-expanded-v1'))
            self.require('host-retained', type(r.get('host')) is dict and all(
                r['host'].get(field) for field in ('hostname','system','kernel','machine','cpu_model')))
            policy = r.get('measurement_policy',{})
            self.require('economic-scope-preserved', policy == dict(os_file_cache='warm',
                pair_order='apply_then_direct_on_same_live_sealed_snapshot',
                setup_in_timed_update=False,pool_hosts=False,pool_profiles=False))
            sources = r.get('measured_source_sha256',{})
            self.require('required-source-pins', all(name in sources for name in (
                'experiments/incremental/producer_delta.py','experiments/incremental/engine.py',
                'experiments/incremental/qualify_delta.py','src/identity.rs',
                'src/parser.rs','src/bin/index_session.rs')))
            for name,identity in sources.items():
                self.hex('source-sha:' + name,identity)
                self.gate('source_bytes_stable_through_qualification:' + name)
                raw = self.source(name)
                if raw is not None:
                    self.require('exact-committed-source:' + name,hashlib.sha256(raw).hexdigest() == identity)
            self.require('harness-sha-pin', r.get('harness_sha256') == sources['experiments/incremental/qualify_delta.py'])
            self.hex('harness-sha-format',r['harness_sha256'])
            for filename,key in [('pins.json','pins'),('delta-pins.json','profile_pins')]:
                raw = self.source('experiments/incremental/' + filename)
                if raw is not None and (key=='pins' or profile=='std-hashmap-expanded-v1'):
                    self.require('exact-committed-' + filename,encoded(decode(raw)) == encoded(r[key]))
            expanded = profile == 'std-hashmap-expanded-v1'
            pins = r['profile_pins'] if expanded else r['pins']
            count = pins['declaration_count'] if expanded else 3436
            if expanded:
                self.require('expanded-profile-exact', pins.get('profile') == profile and
                             pins.get('root_count') == 5318 and count == 11653 and
                             pins.get('roots_sha256') == sources.get('experiments/incremental/expanded-roots.json'))
            self.gate('all_pinned_exports_and_independent_checkers_exact')
            for tool,info in r.get('tools',{}).items():
                self.hex('tool-sha:' + tool,info.get('sha256'))
                self.gate('tool_bytes_stable_through_qualification:' + tool)
                if tool in ('leanchecker','leanchecker-paranoid'):
                    self.require('official-release-pin:' + tool,info['sha256'] == r['pins']['lean_release_binaries_sha256'][tool])
            for variant in VARIANTS:
                reference = r.get('references',{}).get(variant,{})
                self.require('reference-export-pin:' + variant,reference.get('export_sha256') == pins['export_sha256'][variant])
                export = self.locate(reference.get('export_path'), required=False)
                if self.full and export:
                    self.require('retained-reference-export-bytes:' + variant,
                                 hash_file(export) == pins['export_sha256'][variant])
                self.hex('reference-index-pin:' + variant,reference.get('typed_index_sha256'))
                self.gate('reference_python_native_exact:' + variant)
                if expanded:
                    self.gate('reference_exact_profile_obligation_count:' + variant)
                for backend in ('native','python'):
                    self.command('reference:' + variant + ':' + backend,reference.get(backend),0)
                if self.full:
                    native = self.command_json(reference['native'])
                    python = self.command_json(reference['python'])
                    self.require('full-reference-index:' + variant,object_hash(native) == object_hash(python)
                                 == reference['typed_index_sha256'] and native.get('count') == count)
                    self.index_cache[variant] = native
            repetitions = r.get('repetitions')
            self.require('at-least-five-pairs',type(repetitions) is int and repetitions >= 5)
            samples = r.get('samples',[])
            self.require('only-four-variants',all(sample.get('variant') in VARIANTS for sample in samples))
            self.require('explicit-cold-flags',all(type(sample.get('cold_replay')) is bool for sample in samples))
            warm = [sample for sample in samples if not sample['cold_replay']]
            self.require('complete-total-warm-count',len(warm) == 4*repetitions)
            for variant in VARIANTS:
                group = [sample for sample in warm if sample['variant'] == variant]
                self.require('exact-pairs:' + variant,len(group) == repetitions and
                             sorted(sample['repetition'] for sample in group) == list(range(repetitions)))
                self.gate('complete_required_positive_pairs:' + variant)
            for sample in samples:
                self.sample(sample,count,warm)
            cold = [sample for sample in samples if sample['cold_replay']]
            first = next(sample for sample in warm if sample['variant']=='early-definition')
            self.require('actual-cold-replay',len(cold) == 1 and cold[0]['variant']=='early-definition' and
                         cold[0]['repetition']=='cold-restart' and
                         encoded(cold[0]['partition_audit']) == encoded(first['partition_audit']) and
                         cold[0]['snapshot']['sha256'] == first['snapshot']['sha256'])
            self.gate('cold_restart_reauthenticates_and_repeats_partition')
            self.controls()
            recomputed = {}
            for variant in VARIANTS:
                group = [sample for sample in warm if sample['variant']==variant]
                expected = economics(group)
                actual = r.get('economics',{}).get(variant,{})
                for field in ('apply_median_wall_seconds','direct_median_wall_seconds','median_ratio'):
                    self.near('recomputed:' + variant + ':' + field,actual.get(field),expected[field])
                for field in ('paired_wins','paired_count','bootstrap_repetitions','bootstrap_seed','passed','status'):
                    self.require('recomputed:' + variant + ':' + field,
                                 type(actual.get(field)) is type(expected[field]) and actual[field] == expected[field])
                for position in (0,1):
                    self.near('recomputed:' + variant + ':bootstrap:' + str(position),
                              actual.get('bootstrap_ratio_interval_95',[None,None])[position],
                              expected['bootstrap_ratio_interval_95'][position])
                self.require('warm-scope:' + variant,actual.get('setup_in_timed_update') is False and
                             actual.get('scope') == 'warm authenticated session update versus fresh full Rust command')
                self.near('setup-median:' + variant,r.get('setup_medians_wall_seconds',{}).get(variant),
                          expected['median_setup_wall_seconds'])
                recomputed[variant] = expected
            self.require('primary-only-early',r.get('primary_economic_gate') == 'early-definition' and
                         r.get('economic_status') == recomputed['early-definition']['status'])
            self.recomputed = recomputed
        except Exception as error:
            self.check('review-completed-without-missing-malformed-or-false-evidence',False,repr(error))
        passed = bool(self.checks) and all(check['passed'] for check in self.checks)
        return dict(schema='mathgraph.producer-delta-independent-report-review.v1',
            passed=passed,status='PASS_WITH_STATED_LIMITS' if passed else 'FAIL_CLOSED',
            reviewer_sha256=hash_file(__file__),input_object_sha256=object_hash(r),
            expected_source=self.expected_source,summary_path=str(self.summary_path),
            summary_sha256=hash_file(self.summary_path) if self.summary_path.exists() else None,
            mode='retained-files-and-report' if self.full else 'compact-report',
            check_count=len(self.checks),failed_checks=[check for check in self.checks if not check['passed']],
            economics=getattr(self,'recomputed',None),
            available_retained_files=len(self.available_files),absent_retained_files=len(self.absent_files),
            limits=['No kernels were executed by this review.',
                    'No historical issuer HMAC was reauthenticated; live issuer audit status is checked.',
                    'Compact mode checks reported commands/verdicts; missing raw outputs are not invented.',
                    'Warm authenticated update excludes constructor/startup/baseline costs.',
                    'Setup-plus-apply values are sums of separately measured components, not a cold command.',
                    'Fixed apply-then-direct ordering, warm OS cache and each profile/host remain separate.',
                    'Full baseline authentication/hash, SCC reclosure, composite hashing/parsing and full receipt remain O(total).'])


def falsifiers(summary, expected_source, source_root):
    original = decode(Path(summary).read_bytes())
    cases = {}
    def run(name, mutate):
        value = copy.deepcopy(original)
        mutate(value)
        result = Reviewer(summary,expected_source,source_root,False).audit(value)
        cases[name] = dict(refused=not result['passed'],failed_checks=result['failed_checks'])
    run('missing-gates',lambda value:value.update(gates=[]))
    run('incomplete-run',lambda value:value.update(run_completed=False))
    run('altered-direct-timing',lambda value:value['samples'][0].update(
        direct_wall_seconds=value['samples'][0]['direct_wall_seconds']*2))
    run('wrong-source',lambda value:value.update(source_git_commit='0'*40))
    run('wrong-control-cause',lambda value:value['controls']['forged-attestation'].update(
        result=dict(status='UNKNOWN',evidence_id=None,receipt_id=None,reason='producer/index session timeout')))
    run('false-issuer-audit',lambda value:value['samples'][0]['persisted_acceptance_audit'].update(
        issuer_hmac_valid=False))
    run('altered-bootstrap',lambda value:value['economics']['early-definition'].update(
        bootstrap_ratio_interval_95=[.00001,.00002]))
    def overlap(value):
        audit=next(sample['partition_audit'] for sample in value['samples']
                   if sample['partition_audit']['checked_indices'] and sample['partition_audit']['reused_indices'])
        audit['checked_indices'][0]=audit['reused_indices'][0]
    run('overlapping-partition',overlap)
    return dict(status='PASS_FALSIFIERS' if all(value['refused'] for value in cases.values())
                else 'FAIL_FALSIFIERS',cases=cases)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary',type=Path,required=True)
    parser.add_argument('--expected-source',required=True)
    parser.add_argument('--source-root',type=Path)
    parser.add_argument('--full',action='store_true')
    parser.add_argument('--falsifiers',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    reviewer=Reviewer(args.summary,args.expected_source,args.source_root,args.full)
    result=reviewer.audit()
    if args.falsifiers and result['passed']:
        result['falsifiers']=falsifiers(args.summary,args.expected_source,args.source_root)
        result['passed']=result['falsifiers']['status']=='PASS_FALSIFIERS'
        if not result['passed']:
            result['status']='FAIL_CLOSED'
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('status','passed','check_count','failed_checks')}))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    sys.exit(main())
