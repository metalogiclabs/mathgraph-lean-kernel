"""Cost attribution helpers. Never rank opportunities by call count alone."""
import json
import re
from collections import defaultdict
from pathlib import Path


def parse_callgrind(text):
    """Read single-event Ir data; exclude call-edge costs to avoid double counting."""
    names, costs = {}, defaultdict(int)
    active, edge, total = None, False, None
    if 'events: Ir\n' not in text:
        raise ValueError('Expected a single Ir event')
    for line in text.splitlines():
        if line.startswith('summary:'):
            total = int(line.split()[1])
        match = re.fullmatch(r'(c?fn)=\((\d+)\)(?: (.*))?', line)
        if match:
            kind, idx, name = match.groups()
            idx = int(idx)
            if name is not None:
                names[idx] = name
            if kind == 'fn':
                active, edge = idx, False
        elif line.startswith('calls='):
            edge = True
        elif line and line[0] in '0123456789+-*':
            fields = line.split()
            if len(fields) != 2 or active is None:
                raise ValueError('Unexpected cost row: ' + line)
            if edge:
                edge = False
            else:
                costs[active] += int(fields[1])
    by_name = defaultdict(int)
    for idx, n in costs.items():
        by_name[names.get(idx, f'fn#{idx}')] += n
    if total is None or sum(by_name.values()) != total:
        raise ValueError('Self costs do not reconcile to summary')
    return {'total_ir': total, 'self_ir': dict(by_name)}


def summarize_cost(obj):
    """Validate the schema before interpreting a sampled diagnostic record."""
    required = {'schema','seed','root_calls','nested_calls','samples',
                'sample_denominator','timer_floor_ns','rows'}
    if not isinstance(obj, dict) or not required.issubset(obj):
        raise ValueError('Missing diagnostic fields')
    if obj['schema'] != 1 or obj['sample_denominator'] != 1024:
        raise ValueError('Unsupported diagnostic schema or sample rate')
    rows = obj['rows']
    if not isinstance(rows, list):
        raise ValueError('Expected row list')
    by_shape, force, compare, count = defaultdict(int), 0, 0, 0
    for row in rows:
        fields = {'shape','raw','samples','force_ns','compare_ns','max_ns'}
        if not isinstance(row, dict) or not fields.issubset(row):
            raise ValueError('Malformed diagnostic row')
        for k in ('samples','force_ns','compare_ns','max_ns'):
            if type(row[k]) is not int or row[k] < 0:
                raise ValueError('Invalid nonnegative integer: ' + k)
        count += row['samples']
        force += row['force_ns']
        compare += row['compare_ns']
        by_shape[row['shape']] += row['force_ns'] + row['compare_ns']
    if count != obj['samples'] or not (0 < count <= obj['root_calls']):
        raise ValueError('Sample counts do not reconcile')
    total = force + compare
    if not total:
        raise ValueError('No measured work')
    ranked = sorted(by_shape, key=by_shape.get, reverse=True)
    return {
        'seed':obj['seed'], 'root_calls':obj['root_calls'], 'samples':count,
        'kind':'SAMPLED_NATIVE_TIME_NOT_RETIRED_INSTRUCTIONS',
        'force_share':force/total, 'compare_share':compare/total,
        'largest_shape':ranked[0], 'timer_floor_ns':obj['timer_floor_ns'],
        'shape_cost_shares':{k:by_shape[k]/total for k in ranked},
        'raw_record':obj,
    }


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('mode', choices=['callgrind','samples'])
    p.add_argument('paths', nargs='+')
    a=p.parse_args()
    if a.mode == 'callgrind':
        print(json.dumps(parse_callgrind(Path(a.paths[0]).read_text()),indent=2))
    else:
        results=[]
        for path in a.paths:
            lines=[s[len('QCKN_CONV_COST '):] for s in Path(path).read_text().splitlines()
                   if s.startswith('QCKN_CONV_COST ')]
            if len(lines) != 1:
                raise ValueError(f'{path}: expected one complete record, got {len(lines)}')
            results.append(summarize_cost(json.loads(lines[0])))
        if len({r['seed'] for r in results}) != len(results):
            raise ValueError('Repeated seed is not an independent sample schedule')
        print(json.dumps({'schema':1,'runs':results,
             'same_largest_shape':len({r['largest_shape'] for r in results})==1,
             'instruction_gain_claim':False},indent=2))
