from pathlib import Path

TESTS = ['app-lam', 'beta-ladder', 'let-ladder', 'grind-ring-5']
rows = []
for t in TESTS:
    def ir(path):
        for line in Path(path).read_text(errors='ignore').splitlines():
            if line.startswith('events:'):
                pass
        txt = Path(path).read_text(errors='ignore')
        for line in txt.splitlines():
            if line.startswith('summary:'):
                return int(line.split(':', 1)[1].strip())
        raise RuntimeError(f'no callgrind summary in {path}')
    b = ir(f'/tmp/base-{t}.cg')
    c = ir(f'/tmp/cand-{t}.cg')
    d = 100.0 * (c - b) / b
    rows.append((t, b, c, d))
    print(f'{t} base={b} cand={c} delta={d:.6f}%')

D = {t:d for t,_,_,d in rows}
max_reg = max(D.values())
material_gain = min(D.values()) <= -1.0
# V3 paid runtime lowering and regressed grind-ring-5 by +13.069219%.
# This experiment asks whether moving that work to lambda construction removes the displacement,
# and separately whether the quotient becomes performance-material.
if material_gain and max_reg <= 1.0:
    decision = 'PROMOTE__PRODUCER_QUOTIENT_MATERIAL'
elif D['grind-ring-5'] <= 2.0 and max_reg <= 2.0:
    decision = 'KEEP_RESIDUAL__PRECOMPUTE_REMOVES_DISPLACEMENT_NOT_MATERIAL'
else:
    decision = 'KILL__PRODUCER_UNUSED_LAMBDA_QUOTIENT'
print(f'DECISION={decision}')
