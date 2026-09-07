#!/usr/bin/env python3
"""Bounded experiment selector. No checker code or benchmark identities enter the policy."""
from __future__ import annotations
import hashlib, itertools, json
from pathlib import Path

ACTIONS = ('PUSH','REPAIR','REPEAT','REJECT','STOP','PROBE')
PREDICATES = ('blocked','measured_regression','unreachable','needs_replay')

def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':')).encode()

def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()

def validate(r):
    if set(r['state']) != set(PREDICATES):
        raise ValueError('unexpected or missing structural features')
    if any(type(v) is not bool for v in r['state'].values()):
        raise ValueError('features must be boolean')
    if r['action'] not in ACTIONS or not r.get('evidence'):
        raise ValueError('missing action or evidence')
    if r.get('outcome') not in ('observed','pending','unknown'):
        raise ValueError('invalid outcome provenance')
    return r

def choose(policy, state):
    if set(state) != set(PREDICATES):
        raise ValueError('unrecognized state')
    for predicate, action in policy['clauses']:
        if state[predicate]:
            return action
    return policy['default']

def compile_policy(records, max_clauses=3):
    """Minimum-error, minimum-description-length rule over a frozen grammar."""
    records=[validate(r) for r in records]
    best=None; ties=[]
    for default in ACTIONS:
        for n in range(max_clauses+1):
            for predicates in itertools.permutations(PREDICATES,n):
                for actions in itertools.product(ACTIONS,repeat=n):
                    p={'default':default,'clauses':list(zip(predicates,actions))}
                    errors=sum(choose(p,r['state']) != r['action'] for r in records)
                    key=(errors,1+2*n)
                    if best is None or key<best:
                        best=key;ties=[p]
                    elif key==best:
                        ties.append(p)
    states=[dict(zip(PREDICATES,bits)) for bits in itertools.product((False,True),repeat=len(PREDICATES))]
    consensus={}
    for state in states:
        votes={choose(p,state) for p in ties}
        consensus[''.join('1' if state[k] else '0' for k in PREDICATES)]=next(iter(votes)) if len(votes)==1 else None
    return {'policy':ties[0],'consensus':consensus,'training_errors':best[0], 'mdl':best[1],
            'optimal_policy_count':len(ties), 'training_records':len(records)}

def safe_decision(policy, state):
    if set(state)!=set(PREDICATES) or any(type(v) is not bool for v in state.values()):
        raise ValueError('unrecognized state')
    if not any(state.values()):
        return 'PROBE'
    if 'consensus' in policy:
        key=''.join('1' if state[k] else '0' for k in PREDICATES)
        action=policy['consensus'].get(key)
        if action is None:
            return 'PROBE'
    else:
        action=choose(policy,state)
    if state['blocked'] and action not in ('REPAIR','PROBE'):
        return 'PROBE'
    if state['measured_regression'] and action not in ('REJECT','PROBE'):
        return 'PROBE'
    if state['unreachable'] and action not in ('STOP','PROBE'):
        return 'PROBE'
    if state['needs_replay'] and action not in ('REPEAT','PROBE'):
        return 'PROBE'
    return action
