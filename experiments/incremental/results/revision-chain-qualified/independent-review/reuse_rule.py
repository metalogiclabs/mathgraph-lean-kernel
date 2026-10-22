#!/usr/bin/env python3
"""Independent standard-library typed-index and selected-partition checks.

This file imports no implementation under review. Declaration ``own`` hashes
are witnessed by the actual complete native-index output; this reader recomputes
SCC closure and declaration schedule hashes from those own hashes/dependencies.
The flattened index omits inductive block boundaries, so its ``complex`` digest
cannot be regenerated from this representation alone and remains an exact
full-native witness. Neither these identities nor a partition are proof
acceptance or historical HMAC authentication.
"""
import hashlib
import json

SIMPLE = frozenset(('axiom', 'def', 'opaque', 'thm'))
KINDS = SIMPLE | frozenset(('quot', 'itype', 'ctor', 'rec'))
BUILTINS = tuple(('Quot Quot.mk Quot.lift Quot.ind String String.ofList Nat Nat.zero '
                 'Nat.succ Nat.add Nat.sub Nat.mul Nat.pow Nat.mod Nat.div Nat.div.go '
                 'Nat.modCore.go Nat.beq Nat.ble Nat.gcd Nat.land Nat.lor Nat.xor '
                 'Nat.shiftLeft Nat.shiftRight Bool.true Bool.false Char Char.ofNat '
                 'List List.nil List.cons').split())
_INDEX_KEYS = frozenset(('meta', 'declarations', 'count', 'builtins', 'complex', 'schedule'))
_DECL_KEYS = frozenset(('key', 'name', 'kind', 'own', 'deps', 'index', 'closure'))
_DECISION_KEYS = frozenset(('name', 'index', 'status', 'reason', 'dependency_witness', 'evidence_id'))
_VALIDATED_INDEXES = {}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def hexid(value):
    return (type(value) is str and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value))


def strict_object(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, 'duplicate JSON field')
        obj[key] = value
    return obj


def _json_tree(value):
    """Reject Python aliases/non-JSON objects before canonical comparison."""
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is float:
        # canonical rejects nonfinite IEEE numbers.
        canonical(value)
        return
    if type(value) is list:
        for child in value:
            _json_tree(child)
        return
    if type(value) is dict:
        require(all(type(k) is str for k in value), 'JSON object key is not a string')
        for child in value.values():
            _json_tree(child)
        return
    raise ValueError('non-JSON value in typed index')


def _components(adjacency):
    """Iterative Tarjan decomposition, emitting dependency components first."""
    numbering, low, active, on_active, groups = {}, {}, [], set(), []
    clock = 0
    for first in adjacency:
        if first in numbering:
            continue
        numbering[first] = low[first] = clock
        clock += 1
        active.append(first)
        on_active.add(first)
        frames = [(first, iter(adjacency[first]), None)]
        while frames:
            node, edges, parent = frames[-1]
            try:
                child = next(edges)
            except StopIteration:
                frames.pop()
                if parent is not None:
                    low[parent] = min(low[parent], low[node])
                if low[node] == numbering[node]:
                    group = []
                    while True:
                        member = active.pop()
                        on_active.remove(member)
                        group.append(member)
                        if member == node:
                            break
                    groups.append(group)
                continue
            if child not in numbering:
                numbering[child] = low[child] = clock
                clock += 1
                active.append(child)
                on_active.add(child)
                frames.append((child, iter(adjacency[child]), node))
            elif child in on_active:
                low[node] = min(low[node], numbering[child])
    return groups


def validate_index(index):
    """Reject malformed full indexes and independently rederive their SCC roots."""
    require(type(index) is dict and set(index) == _INDEX_KEYS, 'incomplete full native index')
    _json_tree(index)
    identity = digest(index)
    if identity in _VALIDATED_INDEXES:
        return dict(_VALIDATED_INDEXES[identity])
    require(type(index['count']) is int and index['count'] >= 0, 'invalid declaration count')
    require(type(index['declarations']) is list and len(index['declarations']) == index['count'],
            'declaration count differs from complete rows')
    require(type(index['meta']) is dict and type(index['meta'].get('format')) is dict and
            index['meta']['format'].get('version') == '3.1.0', 'invalid export metadata domain')
    require(hexid(index['complex']) and hexid(index['schedule']), 'invalid global/schedule fingerprint')
    by_key, names = {}, set()
    for position, row in enumerate(index['declarations']):
        require(type(row) is dict and set(row) == _DECL_KEYS, 'incomplete full declaration identity')
        require(type(row['index']) is int and row['index'] == position,
                'noninteger or out-of-order declaration index')
        require(type(row['name']) is str and row['name'] and row['name'] not in names,
                'missing/duplicate displayed declaration name')
        require(type(row['kind']) is str and row['kind'] in KINDS, 'unsupported declaration kind')
        require(all(hexid(row[k]) for k in ('key', 'own', 'closure')) and row['key'] not in by_key,
                'invalid or duplicate declaration fingerprint')
        require(type(row['deps']) is list and all(hexid(x) for x in row['deps']) and
                row['deps'] == sorted(set(row['deps'])) and row['key'] not in row['deps'],
                'dependencies are not canonical unique direct identities')
        by_key[row['key']] = row
        names.add(row['name'])
    require(index['schedule'] == digest([r['key'] for r in index['declarations']]),
            'declaration schedule fingerprint differs from rows')
    graph = {key: [dep for dep in row['deps'] if dep in by_key] for key, row in by_key.items()}
    groups = _components(graph)
    group_for = {key: n for n, group in enumerate(groups) for key in group}
    roots = {}
    for number, group in enumerate(groups):
        outgoing = {group_for[dep] for key in group for dep in graph[key]
                    if group_for[dep] != number}
        require(all(other in roots for other in outgoing), 'SCC dependency order failed')
        unresolved = {dep for key in group for dep in by_key[key]['deps'] if dep not in by_key}
        roots[number] = digest(['scc', sorted([[key, by_key[key]['own']] for key in group]),
                                sorted(roots[other] for other in outgoing), sorted(unresolved)])
        require(all(by_key[key]['closure'] == roots[number] for key in group),
                'SCC closure fingerprint differs from actual own/dependency rows')
    builtins = index['builtins']
    require(type(builtins) is dict and set(builtins) == set(BUILTINS),
            'incomplete or unexpected builtin identity universe')
    by_name = {r['name']: r for r in index['declarations']}
    for name, pair in builtins.items():
        require(type(pair) is list and len(pair) == 2 and
                all(part is None or hexid(part) for part in pair), 'invalid builtin fingerprint pair')
        key, root = pair
        if key is None:
            require(root is None and name not in by_name, 'missing declared builtin identity')
        elif key in by_key:
            require(by_key[key]['name'] == name and root == by_key[key]['closure'],
                    'builtin closure/name differs from full declaration')
        else:
            require(root is None and name not in by_name, 'unresolved builtin carries a false closure')
    proof = dict(index_sha256=identity, declarations=index['count'], strongly_connected_components=len(groups),
                 independently_recomputed_closures=True, independently_recomputed_schedule=True,
                 own_and_complex_scope='actual full-native index witnesses; not independently reconstructed from export DAG')
    if len(_VALIDATED_INDEXES) >= 256:
        _VALIDATED_INDEXES.clear()
    _VALIDATED_INDEXES[identity] = proof
    return dict(proof)


def independent_partition(parent_index, current_index, *, compatible=True):
    """Return the authorized prefix/dependency rule and its exact reasons."""
    validate_index(parent_index)
    validate_index(current_index)
    same_metadata = canonical(parent_index['meta']) == canonical(current_index['meta'])
    compatible = bool(compatible and same_metadata)
    globals_same = bool(compatible and
        canonical(parent_index['builtins']) == canonical(current_index['builtins']) and
        parent_index['complex'] == current_index['complex'])
    schedule_same = bool(globals_same and parent_index['schedule'] == current_index['schedule'])
    previous = {r['key']: r for r in parent_index['declarations']} if compatible else {}
    prefix, checked, reused, reasons = True, [], [], []
    for row in current_index['declarations']:
        prior = previous.get(row['key'])
        prefix = bool(prefix and globals_same and prior is not None and
                      prior['index'] == row['index'] and prior['own'] == row['own'])
        local = bool(schedule_same and row['kind'] in SIMPLE and prior is not None and
                     prior['own'] == row['own'] and prior['closure'] == row['closure'])
        reuse = prefix or local
        (reused if reuse else checked).append(row['index'])
        if reuse:
            reason = 'exact_verified_prefix' if prefix else 'dependency_closure_unchanged'
        elif not compatible:
            reason = 'toolchain_or_policy_changed'
        elif not globals_same:
            reason = 'global_builtin_or_complex_assumption_changed'
        elif not schedule_same:
            reason = 'declaration_schedule_changed'
        elif row['kind'] not in SIMPLE:
            reason = 'complex_outside_verified_prefix'
        else:
            reason = 'content_or_transitive_dependency_changed'
        reasons.append(reason)
    return checked, reused, reasons


def validate_partition(result, parent_index, current_index, parent_evidence, *, parent_provenance=None):
    """Validate every accepted decision, evidence origin, and actual selected count.

    A caller that supplies only indexes must independently bind unchanged
    verifier provenance in its receipt-chain review. Supplying parent_provenance
    additionally enforces that binding here.
    """
    require(type(result) is dict and result.get('schema') == 'mathgraph.incremental-lean.v1' and
            result.get('status') == 'VERIFIED' and result.get('action_authorization') == 'NONE',
            'result is not bounded verified evidence')
    require(hexid(parent_evidence) and result.get('previous_evidence') == parent_evidence and
            hexid(result.get('evidence_id')), 'result evidence parent is missing or substituted')
    require(type(result.get('provenance')) is dict, 'missing verifier provenance')
    compatible = parent_provenance is None or canonical(result['provenance']) == canonical(parent_provenance)
    require(compatible, 'verifier provenance changed across accepted predecessor chain')
    checked, reused, reasons = independent_partition(parent_index, current_index, compatible=compatible)
    decisions = result.get('decisions')
    require(type(decisions) is list and len(decisions) == current_index['count'],
            'complete per-declaration decisions missing')
    selected = set(checked)
    for position, (decision, row, reason) in enumerate(zip(decisions, current_index['declarations'], reasons)):
        require(type(decision) is dict and set(decision) == _DECISION_KEYS,
                'incomplete or unexpected decision fields')
        require(type(decision['index']) is int and decision['index'] == position and
                decision['name'] == row['name'], 'decision declaration identity/order differs')
        expected_status = 'VERIFIED_NEW' if position in selected else 'VERIFIED_REUSED'
        expected_evidence = result['evidence_id'] if position in selected else parent_evidence
        require(decision['status'] == expected_status and decision['reason'] == reason and
                decision['evidence_id'] == expected_evidence,
                'decision status/reason/evidence origin differs from independent rule')
        witness = dict(own=row['own'], closure=row['closure'], direct=row['deps'])
        require(canonical(decision['dependency_witness']) == canonical(witness),
                'decision witness differs from complete native index')
    expected_counts = dict(total=current_index['count'], rechecked=len(checked), scheduled=len(checked),
                           invalidated=len(checked), reused=len(reused))
    counts = result.get('counts')
    require(type(counts) is dict and set(counts) == set(expected_counts) and
            all(type(counts[name]) is int and counts[name] == value for name, value in expected_counts.items()),
            'reported actual counts differ from complete selected partition')
    checker = result.get('checker_result')
    require(type(checker) is dict and type(checker.get('code')) is int and checker['code'] == 0 and
            type(checker.get('stdout')) is str, 'actual selected kernel did not succeed')
    report = json.loads(checker['stdout'], object_pairs_hook=strict_object,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON number')))
    require(type(report) is dict and set(report) == {'checked', 'total_declarations', 'scope'} and
            type(report['checked']) is int and report['checked'] == len(checked) and
            type(report['total_declarations']) is int and report['total_declarations'] == current_index['count'] and
            report['scope'] == 'selected_obligations_under_caller_trusted_environment',
            'actual selected kernel report differs from scheduled obligations')
    return dict(actual_kernel_checked=len(checked), actual_kernel_total=current_index['count'],
                independently_replayed_reused=len(reused), checked_indices=checked,
                reused_indices=reused, identity_witnesses_checked=len(decisions),
                evidence_parent=parent_evidence, decision_evidence_origins_checked=True)
