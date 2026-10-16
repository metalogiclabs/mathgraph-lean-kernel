#!/usr/bin/env python3
"""Read-only compact-CI to independently executed local kernel-input comparison."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / 'ci-4496042-summaries.zip'
LOCAL = Path('/workspace/kernel-audit/delta-expanded-independent-portable-final/summary.json')
SOURCE = '4496042c75368f6c35675a9b131c960080afa518'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def main():
    local = load(LOCAL)
    assert local['status'] == 'PASS_INDEPENDENT_EXPANDED_RECONSTRUCTION_INDEX_AND_KERNEL_REPLAY'
    assert local['current_git_commit'] == SOURCE
    assert file_hash(local['input_report']) == local['input_report_sha256']
    local_qualification = load(local['input_report'])
    local_cases = {case['name']: case for case in local['cases']}
    with zipfile.ZipFile(ARCHIVE) as archive:
        raw_report = archive.read('delta-expanded-qualification/summary.json')
        report = json.loads(raw_report)
        observations = json.loads(archive.read('ci-observations.json'))
        source_ref = archive.read('source-ref.txt').decode().strip()
        source_stability = json.loads(archive.read('source-stability.json'))
        manifest = {line.split(None, 1)[1].lstrip('*'): line.split(None, 1)[0]
                    for line in archive.read('source-SHA256SUMS').decode().splitlines()}
    assert source_ref == report['source_git_commit'] == observations['source_sha'] == SOURCE
    assert report['source_git_status'] == ''
    assert source_stability == dict(source_sha=SOURCE, passed=True)
    assert not observations['failures']
    assert observations['reports']['producer-delta-expanded']['summary_sha256'] == sha(raw_report)
    assert observations['reports']['producer-delta-expanded']['report_passed'] is True
    assert report['run_completed'] and report['correctness_passed'] and report['qualification_status'] == 'PASS'
    assert report['profile'] == 'std-hashmap-expanded-v1'
    assert len(report['gates']) == 226 and all(g['passed'] is True for g in report['gates'])
    critical = {}
    for name, digest in local['critical_source_matches_qualified'].items():
        assert manifest[name] == digest
        critical[name] = dict(ci_sha256=manifest[name], independent_local_sha256=digest, equal=True)
    tools = {name: dict(ci_sha256=report['tools'][name]['sha256'],
                       independent_local_sha256=info['sha256'],
                       equal=report['tools'][name]['sha256'] == info['sha256'])
             for name, info in local['actual_tool_pins'].items()}
    assert tools['leanchecker']['equal'] and tools['leanchecker-paranoid']['equal']
    actual_commands = 0
    for case in local['cases']:
        materialized = case['reconstruction']
        assert file_hash(materialized['path']) == materialized['sha256']
        assert Path(materialized['path']).stat().st_size == materialized['bytes']
        for command in case['kernels']:
            assert command['returncode'] == command['expected_returncode']
            assert file_hash(command['stdout_path']) == command['stdout_sha256']
            assert file_hash(command['stderr_path']) == command['stderr_sha256']
            actual_commands += 1
    assert actual_commands == 17
    positive = []
    local_positive = local_cases['early-definition']['reconstruction']
    local_positive_sample = next(s for s in local_qualification['samples']
                                 if s['variant'] == 'early-definition' and not s['cold_replay'])
    local_partition = local_positive_sample['partition_audit']
    for sample in report['samples']:
        if sample['variant'] != 'early-definition':
            continue
        snapshot = sample['snapshot']
        assert snapshot['sha256'] == local_positive['sha256'] and snapshot['bytes'] == local_positive['bytes']
        assert snapshot['seals'] & 15 == 15
        assert sample['partition_audit'] == local_partition
        assert sample['direct_rust']['returncode'] == 0 and not sample['direct_rust']['timed_out']
        assert sample['evidence_id']
        positive.append(dict(repetition=sample['repetition'], cold_replay=sample['cold_replay'],
            sha256=snapshot['sha256'], bytes=snapshot['bytes'], exact_local_input_parity=True,
            actual_ci_checked=sample['partition_audit']['actual_kernel_checked'],
            actual_ci_total=sample['partition_audit']['actual_kernel_total'],
            ci_reused=sample['partition_audit']['independently_replayed_reused'],
            complete_partition_equal_local=True, ci_direct_rust_returncode=0))
    assert len(positive) == 6 and sum(s['cold_replay'] for s in positive) == 1
    typed_hash = local['positive_index_equality']['typed_index_sha256']
    assert report['references']['early-definition']['typed_index_sha256'] == typed_hash
    controls = []
    for name in ['signed-invalid-proof', 'signed-invalid-axiom',
                 'unused-invalid-node-zero-selection-parser',
                 'unused-invalid-node-dag-only-zero-selection-parser']:
        control = report['controls'][name]
        snapshot = control['snapshot']
        independent = local_cases[name]
        assert snapshot['sha256'] == independent['reconstruction']['sha256']
        assert snapshot['bytes'] == independent['reconstruction']['bytes']
        assert snapshot['seals'] & 15 == 15
        result = control['result']
        assert result['status'] == 'REJECTED' and result['checker_result']['code'] == 1
        assert result['evidence_id'] is None and result['receipt_id'] is None
        assert result['counts'] == local_qualification['controls'][name]['result']['counts']
        no_acceptance = next(g for g in report['gates'] if g['name'] == 'no_new_persisted_acceptance:' + name)
        assert no_acceptance['passed'] is True
        for tool in ['rust', 'leanchecker', 'leanchecker-paranoid']:
            command = control['independent_kernel_rejections'][tool]
            assert command['returncode'] == 1 and command['timed_out'] is False
        zero = 'unused-invalid' in name
        if zero:
            assert result['counts']['scheduled'] == 0
            assert control['independent_zero_selected_parser']['returncode'] == 1
            assert control['independent_zero_selected_parser']['timed_out'] is False
        controls.append(dict(name=name, sha256=snapshot['sha256'], bytes=snapshot['bytes'],
            exact_local_input_parity=True, ci_status=result['status'], ci_selected_returncode=1,
            ci_all_three_full_kernels_reject=True, independent_local_kernel_codes=[k['returncode'] for k in independent['kernels']],
            ci_no_evidence_id=True, ci_no_new_persisted_acceptance_gate=True,
            zero_selected_parser_rejection=zero, scheduled=result['counts']['scheduled']))
    verdict = dict(schema='mathgraph.independent-ci-kernel-input-parity.v1',
        status='PASS_EXACT_EXPANDED_CI_INPUT_PARITY_WITH_INDEPENDENT_LOCAL_REPLAY',
        ci_run_id=38945728644, ci_source=SOURCE,
        archive=dict(path=str(ARCHIVE), sha256=file_hash(ARCHIVE)),
        ci_report=dict(member='delta-expanded-qualification/summary.json', sha256=sha(raw_report),
            gates=226, all_gates_passed=True, source_clean=True, completed=True),
        independent_replay=dict(summary=str(LOCAL), summary_sha256=file_hash(LOCAL),
            actual_command_count=17, raw_command_output_hashes_revalidated=True,
            reconstructed_input_hashes_revalidated=True,
            helper_sha256=local['decoder_script_sha256']),
        positives=positive, controls=controls, critical_source_parity=critical,
        positive_typed_index_sha256=typed_hash, tool_binary_parity=tools,
        audit_script_sha256=file_hash(__file__),
        scope=['CI compact archive reports the same five distinct case roles as the independently reconstructed local inputs; both unused-node roles have identical bytes.',
               'All five warm accepted early-edit samples and its cold replay match the independently checked positive bytes and complete checked/reused partition.',
               'Normal/paranoid C++ executable SHA256s also match local independent replay. Rust/producer/index executables differ across builds; exact binary parity is not claimed for them.',
               'Compact ZIP includes summary metadata, not live CI memfd bytes or complete issuer caches. SHA256 input identity relies on reported CI hashes and collision resistance; no fresh CI-byte extraction or independent CI HMAC-secret validation is claimed.',
               'This comparison supplies input/outcome correspondence, not an independent rerun of CI economics, remote runner attestation, or a general correctness theorem.'])
    destination = ROOT / 'independent-kernel-input-parity.json'
    destination.write_text(json.dumps(verdict, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status=verdict['status'], positive_samples=len(positive), invalid_controls=len(controls),
                          output=str(destination), output_sha256=file_hash(destination))))


if __name__ == '__main__':
    main()
