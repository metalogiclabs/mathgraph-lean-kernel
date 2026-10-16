#!/usr/bin/env python3
"""Authenticated reuse of actual MathGraph/Flash checking obligations.

Trust boundary: the authority key authenticates earlier successful checking. It
must be outside the untrusted cache. This module is an executable, audited
conservative model; dependency congruence is not a proved kernel metatheorem.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from contextlib import ExitStack

SCHEMA = 'mathgraph.incremental-lean.v1'
BUILTINS = ('Quot Quot.mk Quot.lift Quot.ind String String.ofList Nat Nat.zero '
            'Nat.succ Nat.add Nat.sub Nat.mul Nat.pow Nat.mod Nat.div Nat.div.go '
            'Nat.modCore.go Nat.beq Nat.ble Nat.gcd Nat.land Nat.lor Nat.xor '
            'Nat.shiftLeft Nat.shiftRight Bool.true Bool.false Char Char.ofNat '
            'List List.nil List.cons').split()
SIMPLE = {'axiom', 'def', 'opaque', 'thm'}
STANDARD_AXIOMS = ['propext', 'Classical.choice', 'Quot.sound']


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def strict_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate JSON key: ' + k)
        result[k] = v
    return result


def read_json(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=strict_object)


def make_index(path):
    """Hash all typed DAG edges, not their unstable serialization indices."""
    names = {0: (digest(['anonymous']), '')}
    levels = {0: digest(['zero'])}
    exprs = {}
    decls = []
    blocks = []
    seen = set()
    meta = None
    count = 0
    def node(table, i):
        if type(i) is not int or i < 0 or i not in table:
            raise ValueError('invalid or forward DAG reference: ' + str(i))
        return table[i]
    def nm(i):
        return node(names, i)[0]
    def ex(i):
        return node(exprs, i)
    def fields(obj, required, optional=()):
        if not isinstance(obj, dict) or set(obj) - set(required) - set(optional) or set(required) - set(obj):
            raise ValueError('unsupported fields: ' + str(obj)[:160])
    def declaration(kind, obj):
        nonlocal count
        common = ['name', 'levelParams', 'type']
        required = {
            'axiom': common + ['isUnsafe'],
            'def': common + ['value', 'hints', 'safety', 'all'],
            'thm': common + ['value', 'all'],
            'opaque': common + ['value', 'isUnsafe', 'all'],
            'quot': common + ['kind'],
            'itype': common + ['numParams', 'numIndices', 'all', 'ctors', 'numNested', 'isRec', 'isUnsafe', 'isReflexive'],
            'ctor': common + ['induct', 'cidx', 'numParams', 'numFields', 'isUnsafe'],
            'rec': common + ['all', 'numParams', 'numIndices', 'numMotives', 'numMinors', 'rules', 'k', 'isUnsafe'],
        }[kind]
        fields(obj, required)
        if obj.get('isUnsafe', False) or ('safety' in obj and obj['safety'] != 'safe'):
            raise ValueError('unsafe or partial declaration is unsupported')
        deps = set()
        def normalize(k, v):
            if k in ('name', 'induct', 'ctor'):
                key = nm(v)
                deps.add(key)
                return ['name', key]
            if k in ('levelParams', 'all', 'ctors'):
                vals = [nm(i) for i in v]
                # Universe params are names but not environment dependencies.
                if k != 'levelParams':
                    deps.update(vals)
                return ['names', vals]
            if k in ('type', 'value', 'rhs'):
                eh, ed = ex(v)
                deps.update(ed)
                return ['expr', eh]
            if k == 'rules':
                for r in v:
                    fields(r, ['ctor', 'nfields', 'rhs'])
                return [{a: normalize(a, b) for a, b in r.items()} for r in v]
            return v
        canonical = {k: normalize(k, v) for k, v in obj.items()}
        key, display = node(names, obj['name'])
        deps.discard(key)
        if key in seen:
            raise ValueError('duplicate declaration')
        seen.add(key)
        if kind == 'axiom' and display not in STANDARD_AXIOMS:
            raise ValueError('nonstandard axiom forbidden: ' + display)
        result = dict(key=key, name=display, kind=kind, own=digest([kind, canonical]),
                      deps=sorted(deps), index=count)
        count += 1
        return result
    with open(path, 'rb') as f:
        for lineno, line in enumerate(f, 1):
            row = json.loads(line, object_pairs_hook=strict_object)
            if not isinstance(row, dict):
                raise ValueError('export row is not an object')
            tags = set(row) - {'in', 'il', 'ie'}
            if len(tags) != 1:
                raise ValueError('ambiguous export row')
            tag = next(iter(tags))
            value = row[tag]
            if tag == 'meta':
                if meta is not None or lineno != 1 or set(row) != {'meta'}:
                    raise ValueError('metadata must be unique and first')
                meta = value
                if value['format']['version'] != '3.1.0':
                    raise ValueError('unsupported export format')
                continue
            if meta is None:
                raise ValueError('metadata missing')
            if tag in ('str', 'num'):
                fields(value, ['pre', tag if tag == 'str' else 'i'])
                parent, display = node(names, value['pre'])
                suffix = value['str' if tag == 'str' else 'i']
                if (tag == 'str' and type(suffix) is not str) or (tag == 'num' and type(suffix) is not int):
                    raise ValueError('ill-typed name component')
                item = (digest([tag, parent, suffix]), display + ('.' if display else '') + str(suffix))
                table, ident = names, row.get('in')
            elif tag in ('succ', 'max', 'imax', 'param'):
                norm = nm(value) if tag == 'param' else ([node(levels, x) for x in value] if isinstance(value, list) else node(levels, value))
                item = digest([tag, norm])
                table, ident = levels, row.get('il')
            elif tag in ('bvar', 'sort', 'const', 'app', 'lam', 'forallE', 'letE', 'proj', 'natVal', 'strVal'):
                deps = set()
                if tag == 'sort':
                    norm = node(levels, value)
                elif tag == 'const':
                    fields(value, ['name', 'us'])
                    key = nm(value['name'])
                    deps.add(key)
                    norm = [key, [node(levels, x) for x in value['us']]]
                elif tag in ('bvar', 'natVal', 'strVal'):
                    norm = value
                else:
                    req = {'app': ['fn', 'arg'], 'lam': ['name', 'type', 'body', 'binderInfo'],
                           'forallE': ['name', 'type', 'body', 'binderInfo'],
                           'letE': ['name', 'type', 'value', 'body', 'nondep'],
                           'proj': ['typeName', 'idx', 'struct']}[tag]
                    fields(value, req)
                    norm = {}
                    for k, v in value.items():
                        if k in ('fn', 'arg', 'type', 'body', 'value', 'struct'):
                            eh, ed = ex(v)
                            norm[k] = eh
                            deps.update(ed)
                        elif k in ('typeName', 'name'):
                            norm[k] = nm(v)
                            if k == 'typeName':
                                deps.add(norm[k])
                        else:
                            norm[k] = v
                item = (digest([tag, norm]), frozenset(deps))
                table, ident = exprs, row.get('ie')
            elif tag in SIMPLE | {'quot'}:
                if set(row) != {tag}:
                    raise ValueError('index attached to declaration')
                decls.append(declaration(tag, value))
                continue
            elif tag == 'inductive':
                fields(value, ['types', 'ctors', 'recs'])
                if set(row) != {tag}:
                    raise ValueError('index attached to inductive')
                block_start = count
                for field, kind in [('types', 'itype'), ('ctors', 'ctor'), ('recs', 'rec')]:
                    decls.extend(declaration(kind, v) for v in value[field])
                blocks.append([block_start, count - block_start])
                continue
            else:
                raise ValueError('unsupported export item: ' + tag)
            if type(ident) is not int or ident < 0 or ident in table or set(row) != {tag, 'in' if table is names else 'il' if table is levels else 'ie'}:
                raise ValueError('duplicate, invalid or ambiguous DAG index')
            table[ident] = item
    by_key = {d['key']: d for d in decls}
    # SCC Merkle fingerprints: cycles hash all member contents and outgoing SCC
    # roots. This is equality of a dependency overapproximation, not semantic EQ.
    adjacency = {d['key']: [k for k in d['deps'] if k in by_key] for d in decls}
    reverse = {k: [] for k in by_key}
    for k, vals in adjacency.items():
        for v in vals:
            reverse[v].append(k)
    visited, order = set(), []
    for start in by_key:
        if start in visited:
            continue
        stack = [(start, False)]
        while stack:
            k, done = stack.pop()
            if done:
                order.append(k)
            elif k not in visited:
                visited.add(k)
                stack.append((k, True))
                stack.extend((v, False) for v in adjacency[k] if v not in visited)
    components, comp = [], {}
    for start in reversed(order):
        if start in comp:
            continue
        number = len(components)
        members, stack = [], [start]
        comp[start] = number
        while stack:
            k = stack.pop()
            members.append(k)
            for v in reverse[k]:
                if v not in comp:
                    comp[v] = number
                    stack.append(v)
        components.append(members)
    roots = {}
    # Kosaraju emits source SCCs first, so reverse is dependency-first.
    for number in reversed(range(len(components))):
        members = components[number]
        outgoing = {comp[v] for k in members for v in adjacency[k] if comp[v] != number}
        negatives = {v for k in members for v in by_key[k]['deps'] if v not in by_key}
        roots[number] = digest(['scc', sorted((k, by_key[k]['own']) for k in members),
                                sorted(roots[c] for c in outgoing), sorted(negatives)])
    for d in decls:
        d['closure'] = roots[comp[d['key']]]
    builtin_ids = {display: key for key, display in names.values() if display in BUILTINS}
    # The exact name kind/path is part of each id; ambiguous display disables reuse.
    if len([1 for _, display in names.values() if display in BUILTINS]) != len(builtin_ids):
        raise ValueError('ambiguous builtin name')
    builtin = {n: [builtin_ids.get(n), by_key[builtin_ids[n]]['closure'] if n in builtin_ids and builtin_ids[n] in by_key else None] for n in BUILTINS}
    return dict(meta=meta, declarations=decls, count=count, builtins=builtin,
                complex=digest([blocks, [(d['key'], d['own']) for d in decls if d['kind'] not in SIMPLE]]),
                schedule=digest([d['key'] for d in decls]))


def load_evidence(cache, evidence_id, key):
    if len(evidence_id) != 64 or any(c not in '0123456789abcdef' for c in evidence_id):
        raise ValueError('invalid evidence identifier')
    raw = (cache / 'records' / (evidence_id + '.json')).read_bytes()
    if hashlib.sha256(raw).hexdigest() != evidence_id:
        raise ValueError('evidence content address mismatch')
    signed = json.loads(raw, object_pairs_hook=strict_object)
    payload = signed['payload']
    expected = hmac.new(key, encoded(payload), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signed['hmac_sha256']):
        raise ValueError('evidence issuer authentication failed')
    if payload['schema'] != SCHEMA or payload['status'] != 'VERIFIED':
        raise ValueError('not accepted verification evidence')
    snapshot = cache / 'exports' / (payload['export_sha256'] + '.ndjson')
    if file_hash(snapshot) != payload['export_sha256']:
        raise ValueError('persisted export corruption')
    return payload


def immutable_write(path, data, repair_corruption=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError:
        existing = path.read_bytes()
        if existing != data:
            if not repair_corruption:
                raise ValueError('immutable content-address collision or corruption')
            # Only checked export bytes use this recovery path. Preserve the
            # corrupt object before restoring the correct content address.
            quarantine = path.parent.parent / 'corrupt' / (hashlib.sha256(existing).hexdigest() + '-' + path.name)
            immutable_write(quarantine, existing)
            path.unlink()
            immutable_write(path, data)
        return
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def verify_incremental(previous_evidence, changed_development, verifier_policy):
    """Return inspectable decisions; a previous warrant is not a fresh check."""
    start = time.perf_counter()
    cache = Path(verifier_policy['cache'])
    key = Path(verifier_policy['authority_key']).read_bytes()
    if len(key) != 32:
        raise ValueError('authority key must be 32 bytes')
    checker_source = Path(verifier_policy['checker']).resolve()
    # Execute the same captured binary bytes that provenance identifies.
    with ExitStack() as resources:
        binary_temp = Path(resources.enter_context(tempfile.TemporaryDirectory(prefix='mathgraph-checker-')))
        checker = binary_temp / 'check-selected'
        shutil.copyfile(checker_source, checker)
        checker.chmod(0o500)
        return _verify_with_binary(previous_evidence, changed_development, verifier_policy,
                                   start, cache, key, checker)


def _verify_with_binary(previous_evidence, changed_development, verifier_policy, start, cache, key, checker):
    provenance = dict(checker_sha256=file_hash(checker), adapter_sha256=file_hash(__file__),
                      issuer_key_sha256=hashlib.sha256(key).hexdigest(),
                      policy=verifier_policy.get('policy', 'default'),
                      configuration=dict(nat_extension=True, string_extension=True,
                                         permitted_axioms=STANDARD_AXIOMS, num_threads=1,
                                         unpermitted_axiom_hard_error=True))
    timings = {}
    old, cache_error = None, None
    tick = time.perf_counter()
    if previous_evidence and not verifier_policy.get('disable_cache'):
        try:
            old = load_evidence(cache, previous_evidence, key)
        except (ValueError, OSError, KeyError, TypeError) as e:
            cache_error = str(e)
    timings['cache_validation_seconds'] = time.perf_counter() - tick
    with tempfile.TemporaryDirectory(prefix='mathgraph-incremental-') as temp:
        temp = Path(temp)
        snapshot = temp / 'current.ndjson'
        shutil.copyfile(changed_development, snapshot)
        tick = time.perf_counter()
        export_hash = file_hash(snapshot)
        compatible = old is not None and old['provenance'] == provenance
        identical = compatible and old['export_sha256'] == export_hash
        index = old['index'] if identical else make_index(snapshot)
        timings['identity_seconds'] = time.perf_counter() - tick
        if compatible and old['index']['meta'] != index['meta']:
            compatible = False
        globals_same = compatible and old['index']['builtins'] == index['builtins'] and old['index']['complex'] == index['complex']
        schedule_same = globals_same and old['index']['schedule'] == index['schedule']
        old_by_key = {d['key']: d for d in old['index']['declarations']} if compatible else {}
        prefix, selected, decisions = True, [], []
        for d in index['declarations']:
            prior = old_by_key.get(d['key'])
            prefix = prefix and globals_same and prior is not None and prior['index'] == d['index'] and prior['own'] == d['own']
            local = schedule_same and d['kind'] in SIMPLE and prior is not None and prior['own'] == d['own'] and prior['closure'] == d['closure']
            reuse = identical or prefix or local
            if reuse:
                reason = 'exact_export' if identical else 'exact_verified_prefix' if prefix else 'dependency_closure_unchanged'
            else:
                selected.append(d['index'])
                reason = ('cache_disabled' if verifier_policy.get('disable_cache') else
                          'cache_refused:' + cache_error if cache_error else
                          'no_previous_evidence' if old is None else
                          'toolchain_or_policy_changed' if not compatible else
                          'global_builtin_or_complex_assumption_changed' if not globals_same else
                          'declaration_schedule_changed' if not schedule_same else
                          'complex_outside_verified_prefix' if d['kind'] not in SIMPLE else
                          'content_or_transitive_dependency_changed')
            decisions.append(dict(name=d['name'], index=d['index'], status='VERIFIED_REUSED' if reuse else 'UNKNOWN',
                                  reason=reason, dependency_witness=dict(own=d['own'], closure=d['closure'],
                                  direct=d['deps']), evidence_id=previous_evidence if reuse else None))
        counts = dict(total=index['count'], rechecked=0, reused=index['count']-len(selected),
                      invalidated=len(selected) if previous_evidence else 0, scheduled=len(selected))
        tick = time.perf_counter()
        result = dict(code=0, stdout='', stderr='', scope='previously_warranted_exact_export')
        # A semantic index is not a parser acceptance certificate. Even when
        # every obligation is reusable, changed bytes must pass the real parser
        # (including unused DAG rows). Only exact attested bytes skip parsing.
        if selected or not identical:
            config = dict(provenance['configuration'], export_file_path=str(snapshot))
            (temp / 'config.json').write_bytes(encoded(config))
            (temp / 'indices.json').write_bytes(encoded(selected))
            try:
                run = subprocess.run([str(checker), str(temp / 'config.json'), str(temp / 'indices.json')], capture_output=True, timeout=verifier_policy.get('timeout', 600))
                result = dict(code=run.returncode, stdout=run.stdout.decode(errors='replace'), stderr=run.stderr.decode(errors='replace'))
                if run.returncode == 0:
                    report = json.loads(run.stdout)
                    if report['checked'] != len(selected) or report['total_declarations'] != index['count']:
                        raise ValueError('checker obligation count mismatch')
                    counts['rechecked'] = report['checked']
            except subprocess.TimeoutExpired:
                result = dict(code=124, stdout='', stderr='checker timeout')
        timings['checking_seconds'] = time.perf_counter() - tick
        status = 'VERIFIED' if result['code'] == 0 else 'UNKNOWN' if result['code'] in (2, 124) else 'REJECTED'
        for d in decisions:
            if d['status'] == 'UNKNOWN':
                d['status'] = 'VERIFIED_NEW' if status == 'VERIFIED' else 'UNKNOWN'
        evidence_id = None
        if status == 'VERIFIED':
            payload = dict(schema=SCHEMA, status=status, export_sha256=export_hash, index=index,
                           provenance=provenance, previous_evidence=previous_evidence,
                           checked_indices=selected, reused_indices=[d['index'] for d in decisions if d['status']=='VERIFIED_REUSED'])
            raw = encoded(dict(payload=payload, hmac_sha256=hmac.new(key, encoded(payload), hashlib.sha256).hexdigest()))
            evidence_id = hashlib.sha256(raw).hexdigest()
            immutable_write(cache / 'exports' / (export_hash + '.ndjson'), snapshot.read_bytes(), repair_corruption=True)
            immutable_write(cache / 'records' / (evidence_id + '.json'), raw)
            for d in decisions:
                if d['status'] == 'VERIFIED_NEW':
                    d['evidence_id'] = evidence_id
        else:
            # A selected-check process stops at failure: completed work is unknown,
            # and previous per-obligation warrants cannot accept the new environment.
            counts['rechecked'] = None
        timings['total_seconds'] = time.perf_counter() - start
        selected_set = set(selected)
        return dict(schema=SCHEMA, status=status, evidence_id=evidence_id,
                    export_sha256=export_hash, previous_evidence=previous_evidence,
                    counts=counts, decisions=decisions, timings=timings,
                    provenance=provenance, checker_result=result, cache_error=cache_error,
                    invalidation_events=[dict(index=d['index'], status='INVALIDATED', reason=d['reason']) for d in decisions if d['index'] in selected_set] if previous_evidence else [],
                    rejection=dict(status='REJECTED', scope='changed_environment', reason='selected_kernel_rejected') if status=='REJECTED' else None,
                    action_authorization='NONE')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--init-key', type=Path)
    for flag in ('export', 'checker', 'cache', 'authority-key', 'output', 'previous', 'policy'):
        p.add_argument('--' + flag)
    p.add_argument('--disable-cache', action='store_true')
    args = p.parse_args()
    if args.init_key:
        args.init_key.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(args.init_key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(os.urandom(32))
        return 0
    if not all((args.export, args.checker, args.cache, args.authority_key, args.output)):
        p.error('--export --checker --cache --authority-key --output are required')
    try:
        result = verify_incremental(args.previous, args.export, dict(checker=args.checker,
                    cache=args.cache, authority_key=args.authority_key,
                    policy=args.policy or 'default', disable_cache=args.disable_cache))
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as e:
        result = dict(schema=SCHEMA, status='UNKNOWN', evidence_id=None, error=str(e))
    Path(args.output).write_bytes(encoded(result) + b'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('decisions', 'invalidation_events', 'checker_result')}))
    return 0 if result['status'] == 'VERIFIED' else 1 if result['status']=='REJECTED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
