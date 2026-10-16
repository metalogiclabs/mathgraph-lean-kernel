#!/usr/bin/env python3
"""Qualify the bounded import of an independently checked early-edit result.

The local qualification summary is a trusted caller artifact, not an untrusted
uploaded receipt. Its two exact-export full-check oracles and completed gates
supply admission policy. This script then tests the real pinned MathGraph
consumer in separate processes; it does not rerun those native oracles.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from mathgraph_integration import (
    MATHGRAPH_COMMIT, canonical, pinned_resolver, require, strict_json,
)
from process import run, sha256

HERE = Path(__file__).resolve().parent
SCHEMA = 'mathgraph.incremental-lean.mathgraph-integration-qualification.v1'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b'\n')


def qualify(qualification, mathgraph, out):
    qualification, mathgraph, out = (Path(path).resolve()
                                    for path in (qualification, mathgraph, out))
    require(not (out / 'summary.json').exists(),
            'USE_NEW_OUTPUT_DIRECTORY_TO_PRESERVE_PRIOR_EVIDENCE')
    out.mkdir(parents=True, exist_ok=True)
    report = dict(schema=SCHEMA, qualification_passed=False, status='UNKNOWN',
                  cases=[], mathgraph_commit=MATHGRAPH_COMMIT,
                  action_authorization='NONE', production_check_binder=False)
    try:
        summary_path = qualification / 'summary.json'
        summary_raw = summary_path.read_bytes()
        summary = strict_json(summary_raw)
        report['source_qualification'] = dict(path=str(summary_path),
            sha256=hashlib.sha256(summary_raw).hexdigest(),
            boundary='TRUSTED_LOCAL_QUALIFIER_OUTPUT_NOT_SELF_AUTHENTICATING_RECEIPT')
        require(type(summary) is dict
                and summary.get('schema') == 'mathgraph.incremental-qualification.v1'
                and summary.get('qualification_passed') is True,
                'SOURCE_QUALIFICATION_NOT_PASSED')
        gates = summary.get('gates')
        require(type(gates) is list and gates
                and all(type(gate) is dict and gate.get('passed') is True
                        for gate in gates), 'SOURCE_QUALIFICATION_GATES_NOT_PASSED')
        # Export authority is selected from the independent full-check records,
        # before the incremental result supplies any evidence identifier.
        oracles = summary['oracles']['early-definition']
        roots = set()
        for name in ('leanchecker', 'leanchecker-paranoid'):
            oracle = oracles[name]
            require(oracle.get('status') == oracle.get('expected') == 'ACCEPT'
                    and oracle['resources'].get('returncode') == 0
                    and oracle['resources'].get('timed_out') is False,
                    'EXACT_EXPORT_ORACLE_NOT_ACCEPTED:' + name)
            roots.add(oracle['export_sha256'])
        require(len(roots) == 1, 'INDEPENDENT_ORACLE_EXPORTS_DIFFER')
        expected_export = roots.pop()
        pair = summary['scenarios']['early-definition']['runs'][0]
        require(pair['fresh']['result']['status'] == 'VERIFIED',
                'FRESH_EXACT_EXPORT_COMPARATOR_NOT_ACCEPTED')
        result_path = qualification / 'scenarios/early-definition/0/incremental.json'
        result_raw = result_path.read_bytes()
        result = strict_json(result_raw)
        expected_result = pair['incremental']['result_sha256']
        require(hashlib.sha256(result_raw).hexdigest() == expected_result,
                'RESULT_BYTES_DIFFER_FROM_QUALIFIED_SUMMARY')
        compact_result = pair['incremental']['result']
        require(type(compact_result) is dict
                and all(key in result and canonical(value) == canonical(result[key])
                        for key, value in compact_result.items()),
                'RESULT_DIFFERS_FROM_QUALIFIED_SUMMARY')
        require(result.get('status') == 'VERIFIED'
                and result.get('export_sha256') == expected_export,
                'QUALIFIED_RESULT_EXPORT_IDENTITY_MISMATCH')
        require(result['counts']['rechecked'] > 0 and result['counts']['reused'] > 0,
                'EARLY_EDIT_MUST_INCLUDE_CHECKED_AND_REUSED_OBLIGATIONS')
        # Only now, after exact-export qualification, may this trusted caller
        # select the successful result's evidence identity and exact byte pin.
        expected_evidence = result['evidence_id']
        _, resolver_digest = pinned_resolver(mathgraph)
        report['resolver_source_sha256'] = resolver_digest
        report['admission'] = dict(result_path=str(result_path),
            result_sha256=expected_result, expected_evidence_id=expected_evidence,
            expected_export_sha256=expected_export,
            oracle_sources=['leanchecker', 'leanchecker-paranoid'],
            qualification_gates=len(gates),
            boundary='COMPLETE_RESULT_QUALIFIED_BY_LOCAL_ORACLE_HARNESS',
            engine_hmac_checked_in_this_consumer=False)
        # Preserve original bytes for a reviewable, exact-input import.
        admitted = out / 'qualified-result.json'
        admitted.write_bytes(result_raw)

        def consume(name, path, *, evidence=expected_evidence,
                    export=expected_export, byte_pin=expected_result,
                    success=False, error=None):
            destination = out / 'cases' / name / 'result.json'
            destination.parent.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(HERE / 'mathgraph_integration.py'),
                       '--mathgraph', str(mathgraph), '--result', str(path),
                       '--output', str(destination), '--expected-evidence-id', evidence,
                       '--expected-export-sha256', export,
                       '--expected-result-sha256', byte_pin]
            resources = run(command, destination.with_name('process'), timeout=120)
            observation = strict_json(destination.read_bytes()) if destination.exists() else None
            if success:
                passed = (resources['returncode'] == 0 and not resources['timed_out']
                    and observation is not None
                    and observation['status'] == 'WARRANTED_BOUNDED_CALLER_QUALIFIED_IMPORT'
                    and observation['mathgraph']['commit'] == MATHGRAPH_COMMIT
                    and observation['admission']['result_byte_pin_supplied_externally'] is True
                    and observation['withdrawal']['dependent_after'] == 'UNKNOWN'
                    and observation['withdrawal']['independent_after'] == 'WARRANTED_BOUNDED'
                    and {item['origin'] for item in observation['obligations']} ==
                        {'CHECKED_THIS_RUN', 'REUSED_PREVIOUS_EVIDENCE'})
            else:
                passed = (resources['returncode'] == 2 and not resources['timed_out']
                    and observation is not None and observation['status'] == 'UNKNOWN'
                    and observation.get('error') == error
                    and observation.get('action_authorization') == 'NONE')
            case = dict(name=name, passed=passed, resources=resources,
                        input_path=str(path), input_sha256=sha256(path),
                        result_path=str(destination), result=observation)
            report['cases'].append(case)
            write(out / 'summary.json', report)

        consume('qualified-import', admitted, success=True)
        changed = copy.deepcopy(result)
        old_digest = changed['decisions'][0]['dependency_witness']['own']
        changed['decisions'][0]['dependency_witness']['own'] = (
            '0' * 64 if old_digest != '0' * 64 else '1' * 64)
        changed_path = out / 'same-id-changed-result.json'
        write(changed_path, changed)
        consume('changed-bytes-same-evidence-id', changed_path,
                error='QUALIFIED_RESULT_BYTES_CHANGED')
        wrong_export = '0' * 64 if expected_export != '0' * 64 else '1' * 64
        consume('wrong-export-root', admitted, export=wrong_export,
                error='EXPORT_PIN_MISMATCH')
        wrong_evidence = '0' * 64 if expected_evidence != '0' * 64 else '1' * 64
        consume('wrong-evidence-root', admitted, evidence=wrong_evidence,
                error='EVIDENCE_PIN_MISMATCH')
        unknown = copy.deepcopy(result)
        unknown['status'] = 'UNKNOWN'
        unknown_path = out / 'unknown-result.json'
        write(unknown_path, unknown)
        # Give this control its own correct byte pin: UNKNOWN must still refuse.
        consume('unknown-result', unknown_path, byte_pin=sha256(unknown_path),
                error='ENGINE_RESULT_NOT_QUALIFIED')
        report['qualification_passed'] = all(case['passed'] for case in report['cases'])
        report['status'] = ('QUALIFIED_BOUNDED_EXISTING_MATHGRAPH_IMPORT'
                            if report['qualification_passed'] else 'UNKNOWN')
        report['scope'] = (
            'Caller-qualified early-edit checking obligations imported into the '
            'unchanged pinned MathGraph resolver. Receipt-origin preservation and '
            'declared support-projection withdrawal are bounded conformance '
            'observations, not new Lean checking or a production Check adapter.')
    except (ValueError, KeyError, TypeError, OSError, IndexError, AttributeError,
            subprocess.SubprocessError) as error:
        report['error'] = str(error)
    write(out / 'summary.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('qualification', 'mathgraph', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = qualify(args.qualification, args.mathgraph, args.out)
    print(json.dumps({key: result[key] for key in ('schema', 'status', 'qualification_passed')}))
    return 0 if result['qualification_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
