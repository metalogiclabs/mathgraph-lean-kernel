#!/usr/bin/env python3
"""Attribute direct memset costs and call sites in preserved Callgrind profiles."""
import collections
import glob
import json
import re
import sys
from pathlib import Path

SYM = re.compile(r'(?:c?fn)=\((\d+)\)\s+(.+)')
POS = re.compile(r'(?:0x[0-9a-fA-F]+|[+*]|[+-]?\d+)')

def parse(path, symbols):
    total = None
    events = None
    positions = None
    current = None
    callee = None
    pending = False
    own = collections.Counter()
    edges = collections.Counter()
    calls = collections.Counter()
    for line in path.read_text(errors='replace').splitlines():
        if line.startswith('positions: '):
            positions = len(line.split()) - 1
        elif line.startswith('events: '):
            events = line.split()[1:]
        elif line.startswith('summary: '):
            total = int(line.split()[1].replace(',', ''))
        elif line.startswith('fn='):
            m = re.fullmatch(r'fn=\((\d+)\)(?:\s+(.*))?', line)
            current = m.group(1) if m else line[3:]
            if m and m.group(2):
                symbols[current] = m.group(2)
            callee = None
            pending = False
        elif line.startswith('cfn='):
            m = re.fullmatch(r'cfn=\((\d+)\)(?:\s+(.*))?', line)
            callee = m.group(1) if m else line[4:]
            if m and m.group(2):
                symbols[callee] = m.group(2)
        elif line.startswith('calls='):
            if current is None or callee is None:
                raise ValueError(f'{path}: call without caller/callee')
            calls[(current, callee)] += int(line.split('=', 1)[1].split()[0])
            pending = True
        elif line.startswith(('jump=', 'jcnd=')):
            pending = True
        elif current is not None and positions is not None and events == ['Ir']:
            fields = line.split()
            if len(fields) == positions + 1 and all(POS.fullmatch(x) for x in fields[:positions]):
                cost = int(fields[-1].replace(',', ''))
                if pending:
                    if callee is not None:
                        edges[(current, callee)] += cost
                    pending = False
                else:
                    own[current] += cost
    if total is None and events is None:
        return None
    if total is None or events != ['Ir']:
        raise ValueError(f'{path}: unsupported totals')
    if sum(own.values()) != total:
        raise ValueError(f'{path}: exclusive sum {sum(own.values())} != {total}')
    return total, own, edges, calls

def analyze(root):
    result = {}
    for corpus in ('std', 'cedar', 'mathlib'):
        paths = [Path(p) for p in sorted(glob.glob(str(root / 'out' / (corpus + '.callgrind*')))) if Path(p).is_file()]
        if not paths:
            raise ValueError(f'{corpus}: no profiles')
        symbols = {}
        for path in paths:
            for line in path.read_text(errors='replace').splitlines():
                m = SYM.fullmatch(line)
                if m:
                    key, name = m.groups()
                    if key in symbols and symbols[key] != name:
                        raise ValueError(f'{corpus}: conflicting symbol {key}')
                    symbols[key] = name
        total = threads = 0
        own = collections.Counter()
        edges = collections.Counter()
        calls = collections.Counter()
        for path in paths:
            parsed = parse(path, symbols)
            if parsed is None:
                continue
            n, o, e, c = parsed
            total += n
            threads += 1
            own.update(o)
            edges.update(e)
            calls.update(c)
        if total <= 0 or sum(own.values()) != total:
            raise ValueError(f'{corpus}: incomplete accounting')
        def name(k):
            if k not in symbols:
                raise ValueError(f'{corpus}: unresolved symbol {k}')
            return symbols[k]
        own_named = collections.Counter()
        for k, v in own.items():
            own_named[name(k)] += v
        target_ids = {k for k, v in symbols.items() if re.search(r'(^|::)(?:__)?memset(?:_|$)|^memset$', v)}
        targets = []
        for target in sorted(target_ids):
            incoming = []
            for (caller, callee), cost in edges.items():
                if callee == target:
                    incoming.append({'caller': name(caller), 'edge_ir': cost, 'calls': calls[(caller, callee)]})
            incoming.sort(key=lambda r: -r['edge_ir'])
            targets.append({'function': name(target), 'exclusive_ir': own.get(target, 0), 'incoming_ir': sum(r['edge_ir'] for r in incoming), 'incoming_calls': sum(r['calls'] for r in incoming), 'callers': incoming})
        result[corpus] = {'total_ir': total, 'threads': threads, 'exclusive_accounting': 'EXACT', 'targets': targets, 'top_exclusive': [{'function': k, 'ir': v} for k, v in own_named.most_common(20)]}
    return result

if __name__ == '__main__':
    root = Path(sys.argv[1])
    out = analyze(root)
    (root / 'memory-callers.json').write_text(json.dumps(out, indent=2))
    for corpus, data in out.items():
        print(f'V84_{corpus.upper()}_TOTAL_IR={data["total_ir"]}')
        print(f'V84_{corpus.upper()}_THREADS={data["threads"]}')
        print(f'V84_{corpus.upper()}_EXCLUSIVE_ACCOUNTING=EXACT')
        for target in data['targets']:
            print(f'V84_{corpus.upper()}_TARGET={target["function"]} SELF={target["exclusive_ir"]} INCOMING={target["incoming_ir"]} CALLS={target["incoming_calls"]}')
            for row in target['callers'][:20]:
                print(f'V84_{corpus.upper()}_CALLER {row}')
    print('DECISION=CALLER_ATTRIBUTION_ONLY__NO_REPAIR_PROMOTED')
    print('RULE=EDGE_IR_IS_NOT_EXCLUSIVE_COST_OR_NATIVE_CPU_TIME')
