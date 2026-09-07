#!/usr/bin/env python3
"""Aggregate exclusive Ir across every Callgrind thread, never inclusive totals."""
import collections
import glob
import json
import re
import sys
from pathlib import Path


def parse(path):
    symbols = {}
    current = None
    costs = collections.Counter()
    total = None
    positions = None
    events = None
    for line in Path(path).read_text(errors='replace').splitlines():
        if line.startswith('positions: '):
            positions = len(line.split()) - 1
        elif line.startswith('events: '):
            events = line.split()[1:]
        elif line.startswith('summary: '):
            total = int(line.split()[1].replace(',', ''))
        elif line.startswith('fn='):
            match = re.match(r'fn=\((\d+)\)\s*(.*)', line)
            if match:
                current = match.group(1)
                if match.group(2):
                    symbols[current] = match.group(2)
            else:
                current = line[3:]
        elif current is not None and positions is not None and events == ['Ir']:
            fields = line.split()
            if len(fields) == positions + 1 and all(re.fullmatch(r'(?:0x[0-9a-fA-F]+|[+\-*]|[+-]?\d+)', x) for x in fields[:positions]):
                costs[current] += int(fields[-1].replace(',', ''))
    if total is None or events != ['Ir']:
        raise ValueError(f'{path}: missing or unsupported instruction totals')
    result = collections.Counter()
    for key, cost in costs.items():
        if key not in symbols:
            raise ValueError(f'{path}: unresolved function {key}')
        result[symbols[key]] += cost
    if sum(result.values()) != total:
        raise ValueError(f'{path}: exclusive sum {sum(result.values())} != total {total}')
    return total, result


def main(root):
    out = {}
    for corpus in ('std', 'cedar', 'mathlib'):
        files = sorted(glob.glob(str(root / 'out' / (corpus + '.callgrind*'))))
        files = [p for p in files if Path(p).is_file()]
        if not files:
            raise ValueError(f'{corpus}: no profiles')
        costs = collections.Counter()
        total = 0
        for path in files:
            n, c = parse(path)
            total += n
            costs.update(c)
        if total <= 0 or sum(costs.values()) != total:
            raise ValueError(f'{corpus}: incomplete accounting')
        rows = [{'function': k, 'exclusive_ir': v, 'percent': 100*v/total} for k,v in costs.most_common()]
        out[corpus] = {'total_ir': total, 'threads': len(files), 'functions': rows}
        print(f'V83_{corpus.upper()}_THREADS={len(files)}')
        print(f'V83_{corpus.upper()}_TOTAL_IR={total}')
        print(f'V83_{corpus.upper()}_EXCLUSIVE_ACCOUNTING=EXACT')
        for row in rows[:20]:
            print(f"V83_{corpus.upper()}_HOT {row['percent']:.3f}% {row['exclusive_ir']} {row['function']}")
        for row in rows:
            if any(s in row['function'] for s in ('prune_env', 'key_env', 'intern_frame', 'eval_no_cache', 'force_all', 'infer_value', 'store_lookup')):
                print(f"V83_{corpus.upper()}_TARGET {row['percent']:.3f}% {row['exclusive_ir']} {row['function']}")
    (root / 'cost-profile.json').write_text(json.dumps(out, indent=2))
    print('DECISION=EXCLUSIVE_COST_CENSUS__NO_REPAIR_PROMOTED')

if __name__ == '__main__':
    main(Path(sys.argv[1]))
