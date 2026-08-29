#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

log=Path(sys.argv[1]).read_text()
out=Path(sys.argv[2])
required=[
    'STAGE2_PROMOTED_CONSTRUCTOR_CONSUMED=PASS',
    'STAGE2_DEPENDS_ON_PROMOTED_GUARD=PASS',
    'SECOND_STRUCTURALLY_DISTINCT_INTERFACE=PASS',
    'BLIND_RECURSIVE_LOWERING_STAGE=2:PASS',
]
for r in required:
    if r not in log:
        raise SystemExit(f'missing stage2 proof gate: {r}')
m=re.search(r'STAGE2_GENERATED_VARIANT=([^\s]+)',log)
if not m:
    raise SystemExit('missing generated stage2 representation')
cert={
    'constructor':'anonymous_exposed_body_interface',
    'parent':'anonymous_guard_before_force',
    'source_context':'q1',
    'generated_shape':m.group(1),
    'exports':['opaque_slot_0','opaque_slot_1'],
}
out.write_text(json.dumps(cert,sort_keys=True)+'\n')
print('STAGE2_PROMOTION_CERTIFICATE=PASS')
