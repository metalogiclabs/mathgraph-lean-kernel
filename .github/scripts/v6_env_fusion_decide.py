import csv
from pathlib import Path

rows = list(csv.DictReader(Path('/tmp/v6-callgrind.csv').open()))
by = {(r['test'], r['arm']): int(r['instructions']) for r in rows}
print('V6_CAUSAL_QUESTION=does eliminating the repeated projection/materialization boundary produce a material jump?')
material = False
for t in ['app-lam','beta-ladder','let-ladder','grind-ring-5','std']:
    b, a, f = by[(t,'base')], by[(t,'ablate')], by[(t,'fusion')]
    fb = 100*(f/b-1)
    fa = 100*(f/a-1)
    print(f'{t} base={b} ablate={a} fusion={f} fusion_vs_base={fb:+.3f}% fusion_vs_ablate={fa:+.3f}%')
    if fb <= -2.0 or fa <= -2.0:
        material = True
print('DECISION=' + ('KEEP__PRODUCER_CONSUMER_FUSION_MATERIAL' if material else 'KILL__PRODUCER_CONSUMER_FUSION_NOT_MATERIAL'))
