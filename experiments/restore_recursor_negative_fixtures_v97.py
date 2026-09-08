#!/usr/bin/env python3
"""Restore missing recursor negative fixtures from the pinned Nat export.

Keep the complete Nat declaration and change exactly one imported recursor
field per case. This is fixture repair, not a kernel optimization.
"""
import copy
import json
from pathlib import Path

SOURCE = Path('test_resources/KReduceDepthAlias/export')
ROOT = Path('test_resources')


def nat_prefix():
    records = [json.loads(line) for line in SOURCE.read_text().splitlines() if line.strip()]
    assert records[0]['meta']['format']['version'] == '3.1.0'
    end = next(i for i, r in enumerate(records) if 'inductive' in r)
    records = copy.deepcopy(records[:end + 1])
    block = records[-1]['inductive']
    assert len(block['types']) == 1 and block['types'][0]['name'] == 1
    assert len(block['ctors']) == 2 and len(block['recs']) == 1
    assert block['recs'][0]['name'] == 5
    assert block['recs'][0]['rules'][0]['rhs'] == 24
    return records


def make_cases():
    original = nat_prefix()
    forged = copy.deepcopy(original)
    expr = next(r for r in forged if r.get('ie') == 24)
    assert expr['lam']['type'] == 4
    expr['lam']['type'] = 1  # Nat instead of the motive.

    unlisted = copy.deepcopy(original)
    block = unlisted[-1]['inductive']
    new_name = max(r['in'] for r in unlisted if 'in' in r) + 1
    unlisted.insert(-1, {'in': new_name, 'str': {'pre': 1, 'str': 'unlistedRec'}})
    extra = copy.deepcopy(block['recs'][0])
    extra['name'] = new_name
    block['recs'].append(extra)
    assert len(block['recs']) == 2
    return {'RuleDomainMismatch': forged, 'UnlistedRecursor': unlisted}


def write_cases():
    for name, records in make_cases().items():
        dest = ROOT / name
        dest.mkdir(parents=True, exist_ok=True)
        (dest / 'export').write_text(''.join(json.dumps(r, separators=(',', ':'), ensure_ascii=False) + '\n' for r in records))
        (dest / 'config.json').write_text(json.dumps({
            'export_file_path': str(dest / 'export'),
            'permitted_axioms': [],
            'unpermitted_axiom_hard_error': True,
            'nat_extension': True,
        }, indent=2) + '\n')
        print('V97_FIXTURE=' + name, flush=True)


if __name__ == '__main__':
    write_cases()
