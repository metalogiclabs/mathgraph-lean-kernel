#!/usr/bin/env python3
from pathlib import Path
import csv

rows = list(csv.DictReader(open('/tmp/v5-callgrind.csv')))

def I(test, arm):
    return int(next(r['instructions'] for r in rows if r['test'] == test and r['arm'] == arm))

tests = sorted({r['test'] for r in rows})
print('V5_CAUSAL_QUESTION=does reuse of an already-computed future-relative key_env representative amortize its memo bookkeeping cost?')
print('ARM_base=exact_V2')
print('ARM_ablate=compute_and_store_memo_but_never_read_it')
print('ARM_reuse=same_bookkeeping_plus_memo_hits')

profitable = False
reuse_material = False
for t in tests:
    b, a, r = I(t, 'base'), I(t, 'ablate'), I(t, 'reuse')
    rb = (r / b - 1.0) * 100.0
    ab = (a / b - 1.0) * 100.0
    ra = (r / a - 1.0) * 100.0
    print(f'{t} base={b} ablate={a} reuse={r} reuse_vs_base={rb:+.3f}% ablate_vs_base={ab:+.3f}% reuse_vs_ablate={ra:+.3f}%')
    profitable |= rb <= -0.5 and ra < 0
    reuse_material |= ra <= -1.0

# The causal signal is reuse<ablate. Promotion additionally requires reuse<base;
# otherwise we have proven reuse but not a useful implementation.
if profitable and reuse_material:
    decision = 'PROMOTE__REPEATED_CONSUMPTION_REUSE_IS_CAUSAL_AND_PROFITABLE'
elif reuse_material:
    decision = 'KEEP_RESIDUAL__REUSE_IS_REAL_BUT_MEMO_OVERHEAD_DOMINATES'
else:
    decision = 'KILL__KEY_ENV_REUSE_NOT_MATERIAL_AT_THIS_BOUNDARY'
print('DECISION=' + decision)
