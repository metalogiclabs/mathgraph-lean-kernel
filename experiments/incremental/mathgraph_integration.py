#!/usr/bin/env python3
"""Bounded import into an existing, pinned MathGraph warrant resolver.

The caller must first qualify the complete result, including its decisions,
against the authenticated engine evidence and an independent full-check oracle.
Expected identities supplied outside that result constrain admission; they do
not perform that qualification. This consumer neither checks Lean nor verifies
an engine HMAC and is not a generic production MathGraph Check receipt adapter.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

MATHGRAPH_COMMIT = 'cf359686c74549a132c7a651cd7aabc7c1a870fe'
RESOLVER_PATH = 'mathgraph_check/warrant_resolution.py'
SCHEMA = 'mathgraph.incremental-lean.warrant-integration.v1'
HEX = re.compile(r'^[0-9a-f]{64}$')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'DUPLICATE_JSON_KEY')
            value[key] = item
        return value

    def constant(_):
        raise ValueError('NONFINITE_JSON_NUMBER')

    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    canonical(result)
    return result


def pinned_resolver(mathgraph):
    """Execute only the audited resolver bytes, regardless of Python import paths."""
    root = Path(mathgraph).resolve()
    git = lambda *args: subprocess.check_output(
        ['git', '-C', str(root), *args], stderr=subprocess.PIPE).strip()
    require(git('rev-parse', 'HEAD').decode() == MATHGRAPH_COMMIT,
            'MATHGRAPH_COMMIT_MISMATCH')
    original = subprocess.check_output(
        ['git', '-C', str(root), 'show', MATHGRAPH_COMMIT + ':' + RESOLVER_PATH],
        stderr=subprocess.PIPE)
    path = root / RESOLVER_PATH
    raw = path.read_bytes()
    require(raw == original, 'MATHGRAPH_RESOLVER_BYTES_CHANGED')
    name = '_qualified_mathgraph_warrant_resolution'
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, 'RESOLVER_IMPORT_FAILED')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses consult their defining module.
    # Execute the bytes just checked, rather than reopening a mutable path.
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module, hashlib.sha256(raw).hexdigest()


def consume_qualified_result(result, *, mathgraph, expected_evidence_id,
                             expected_export_sha256):
    """Import caller-qualified obligations; no new receipt authority is created.

    The expected identities and the qualification of result's complete contents
    are trusted caller inputs, never claims authenticated by this function.
    Each admitted receipt is specific to one exact environment and obligation.
    """
    require(type(result) is dict and result.get('schema') == 'mathgraph.incremental-lean.v1',
            'UNSUPPORTED_ENGINE_RESULT')
    require(result.get('status') == 'VERIFIED', 'ENGINE_RESULT_NOT_QUALIFIED')
    require(isinstance(expected_evidence_id, str) and HEX.fullmatch(expected_evidence_id),
            'INVALID_EXTERNAL_EVIDENCE_PIN')
    require(isinstance(expected_export_sha256, str) and HEX.fullmatch(expected_export_sha256),
            'INVALID_EXTERNAL_EXPORT_PIN')
    require(result.get('evidence_id') == expected_evidence_id, 'EVIDENCE_PIN_MISMATCH')
    require(result.get('export_sha256') == expected_export_sha256, 'EXPORT_PIN_MISMATCH')
    require(result.get('action_authorization') == 'NONE', 'FORBIDDEN_ACTION_AUTHORITY')
    provenance = result.get('provenance')
    require(type(provenance) is dict and type(provenance.get('configuration')) is dict,
            'MISSING_ENVIRONMENT_IDENTITY')
    for key in ('checker_sha256', 'adapter_sha256', 'issuer_key_sha256'):
        require(isinstance(provenance.get(key), str) and HEX.fullmatch(provenance[key]),
                'INVALID_ENVIRONMENT_DIGEST')
    require(isinstance(provenance.get('policy'), str) and provenance['policy'],
            'MISSING_VERIFIER_POLICY')
    decisions = result.get('decisions')
    require(type(decisions) is list and len(decisions) >= 2,
            'DEMO_REQUIRES_TWO_QUALIFIED_OBLIGATIONS')
    native_counts = {'VERIFIED_NEW': 0, 'VERIFIED_REUSED': 0}
    names, indices = set(), set()
    for decision in decisions:
        require(type(decision) is dict, 'INVALID_OBLIGATION')
        status, name, index = (decision.get(key) for key in ('status', 'name', 'index'))
        require(status in native_counts, 'OBLIGATION_NOT_QUALIFIED')
        require(isinstance(name, str) and name and name not in names,
                'INVALID_OR_DUPLICATE_OBLIGATION_NAME')
        require(type(index) is int and index >= 0 and index not in indices,
                'INVALID_OR_DUPLICATE_OBLIGATION_INDEX')
        names.add(name)
        indices.add(index)
        native_counts[status] += 1
        witness = decision.get('dependency_witness')
        require(type(witness) is dict and set(witness) == {'own', 'closure', 'direct'},
                'INVALID_DEPENDENCY_WITNESS')
        require(all(isinstance(witness.get(key), str) and HEX.fullmatch(witness[key])
                    for key in ('own', 'closure')), 'INVALID_DEPENDENCY_DIGEST')
        require(type(witness['direct']) is list and
                all(isinstance(key, str) and HEX.fullmatch(key) for key in witness['direct']),
                'INVALID_DIRECT_DEPENDENCIES')
        expected_origin = (expected_evidence_id if status == 'VERIFIED_NEW'
                           else result.get('previous_evidence'))
        require(isinstance(expected_origin, str) and HEX.fullmatch(expected_origin)
                and decision.get('evidence_id') == expected_origin,
                'OBLIGATION_EVIDENCE_ORIGIN_MISMATCH')
    counts = result.get('counts', {})
    require(type(counts) is dict and all(type(counts.get(key)) is int
            for key in ('total', 'rechecked', 'reused'))
            and counts.get('total') == len(decisions)
            and counts.get('rechecked') == native_counts['VERIFIED_NEW']
            and counts.get('reused') == native_counts['VERIFIED_REUSED'],
            'QUALIFIED_OBLIGATION_COUNT_MISMATCH')

    resolver, source_digest = pinned_resolver(mathgraph)
    environment = digest(provenance)
    claims, receipts, routes, obligations = [], [], [], []
    for decision in sorted(decisions, key=lambda item: item['index']):
        identity = digest({key: decision[key] for key in
                           ('name', 'index', 'dependency_witness')})
        scope = ('lean-export:' + expected_export_sha256 + ':environment:' +
                 environment + ':obligation:' + identity)
        cid = 'lean-obligation:' + identity
        rid = 'qualified-lean-receipt:' + digest([scope, decision['evidence_id']])
        claims.append(resolver.Claim(cid, 'formal', scope))
        receipts.append(resolver.Receipt(rid, 'formal', scope))
        routes.append(resolver.Route(cid, (rid,)))
        obligations.append(dict(name=decision['name'], index=decision['index'],
            native_status=decision['status'],
            origin=('CHECKED_THIS_RUN' if decision['status'] == 'VERIFIED_NEW'
                    else 'REUSED_PREVIOUS_EVIDENCE'),
            evidence_id=decision['evidence_id'], claim_id=cid, receipt_id=rid,
            scope=scope, dependency_witness=decision['dependency_witness']))

    # This is an explicitly declared conformance descendant, not a new theorem
    # or an inferred Lean dependency. Another independently admitted obligation
    # supplies the unrelated-receipt control.
    victim, independent = obligations[:2]
    dependent = 'support-projection:' + victim['claim_id']
    claims.append(resolver.Claim(dependent, 'formal', victim['scope']))
    routes.append(resolver.Route(dependent, (victim['receipt_id'],),
                                 (victim['claim_id'],)))
    before = resolver.resolve_graph(claims, routes, receipts)
    after = resolver.resolve_graph(claims, routes, receipts,
                                    withdrawn=frozenset({victim['receipt_id']}))
    require(after.states[victim['claim_id']] == 'UNKNOWN'
            and after.states[dependent] == 'UNKNOWN'
            and after.states[independent['claim_id']] == 'WARRANTED_BOUNDED',
            'EXISTING_RESOLVER_WITHDRAWAL_CONTROL_FAILED')
    for obligation in obligations:
        obligation['warrant_state'] = before.states[obligation['claim_id']]
    return dict(schema=SCHEMA, status='WARRANTED_BOUNDED_CALLER_QUALIFIED_IMPORT',
        mathgraph=dict(commit=MATHGRAPH_COMMIT, path=RESOLVER_PATH,
                       source_sha256=source_digest),
        admission=dict(boundary='EXTERNAL_CALLER_QUALIFIED_RESULT',
            expected_evidence_id=expected_evidence_id,
            expected_export_sha256=expected_export_sha256,
            result_contents='CALLER_MUST_QUALIFY_COMPLETE_DECISIONS_AND_EVIDENCE',
            authentication_performed_here=False, original_lean_rerun=False),
        environment_sha256=environment, obligations=obligations,
        withdrawal=dict(kind='HYPOTHETICAL_SINGLE_OBLIGATION_ADMISSION_WITHDRAWAL',
            withdrawn_receipt=victim['receipt_id'], affected_claim=victim['claim_id'],
            affected_after=after.states[victim['claim_id']], dependent_claim=dependent,
            dependent_after=after.states[dependent],
            independent_claim=independent['claim_id'],
            independent_after=after.states[independent['claim_id']],
            descendant_basis='DECLARED_CONFORMANCE_SUPPORT_PROJECTION_NOT_LEAN_DEPENDENCY',
            source_withdrawal_observed=False,
            resolutions=resolver.compare_snapshots(before.states, after.states)),
        current_source_freshness='NOT_CHECKED', action_authorization='NONE',
        production_mathgraph_check_binder=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('mathgraph', 'result', 'output', 'expected-evidence-id',
                 'expected-export-sha256'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--expected-result-sha256',
                        help='Optional independently qualified exact result byte pin')
    args = parser.parse_args()
    try:
        raw = Path(args.result).read_bytes()
        result_hash = hashlib.sha256(raw).hexdigest()
        if args.expected_result_sha256 is not None:
            require(HEX.fullmatch(args.expected_result_sha256)
                    and result_hash == args.expected_result_sha256,
                    'QUALIFIED_RESULT_BYTES_CHANGED')
        report = consume_qualified_result(strict_json(raw), mathgraph=args.mathgraph,
            expected_evidence_id=args.expected_evidence_id,
            expected_export_sha256=args.expected_export_sha256)
        report['admission']['result_sha256'] = result_hash
        report['admission']['result_byte_pin_supplied_externally'] = args.expected_result_sha256 is not None
    except (ValueError, KeyError, TypeError, OSError, RecursionError,
            subprocess.SubprocessError) as error:
        report = dict(schema=SCHEMA, status='UNKNOWN', error=str(error),
                      action_authorization='NONE', production_mathgraph_check_binder=False)
    Path(args.output).write_bytes(canonical(report) + b'\n')
    print(json.dumps({key: report[key] for key in ('schema', 'status')}))
    return 0 if report['status'] == 'WARRANTED_BOUNDED_CALLER_QUALIFIED_IMPORT' else 2


if __name__ == '__main__':
    raise SystemExit(main())
