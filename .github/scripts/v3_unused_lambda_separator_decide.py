from pathlib import Path


def ir(path: str) -> int:
    for line in Path(path).read_text(errors='ignore').splitlines():
        if line.startswith('summary:'):
            return int(line.split()[1])
    raise RuntimeError(path)


ratios = {}
for t in ['app-lam', 'beta-ladder', 'let-ladder', 'grind-ring-5']:
    b = ir(f'/tmp/base-{t}.cg')
    c = ir(f'/tmp/cand-{t}.cg')
    d = (c - b) / b
    ratios[t] = d
    print(f'{t} base={b} cand={c} delta={d:.6%}')

target = min(ratios['app-lam'], ratios['beta-ladder'])
guard = max(ratios['let-ladder'], ratios['grind-ring-5'])
if target <= -0.03 and guard <= 0.005:
    decision = 'PROMOTE__UNUSED_LAMBDA_APPLICATION_ELISION'
elif target <= -0.005 and guard <= 0.005:
    decision = 'REAL_GAIN__ESCALATE_FULL_ARENA'
else:
    decision = 'KILL__UNUSED_LAMBDA_ELISION_NOT_MATERIAL'
print('DECISION=' + decision)
