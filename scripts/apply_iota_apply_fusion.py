#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / 'src' / 'eval.rs'
s = p.read_text()
old = '''        let nprefix = usize::from(rec.num_params + rec.num_motives + rec.num_minors);
        result = self.apply_many(depth, result, &args[..nprefix]);
        result = self.apply_many(depth, result, &ctor_args[num_extra..]);
        result = self.apply_many(depth, result, &args[rec.major_idx() + 1..]);
        Some(result)
'''
new = '''        let nprefix = usize::from(rec.num_params + rec.num_motives + rec.num_minors);
        // Frozen separator: preserve one application stream across the three
        // recursor-application phases so apply_many can fuse adjacent lambdas
        // rather than materializing/evaluating an intermediate value at each boundary.
        let mut fused_args: SpineArgs<'t> = SpineArgs::with_capacity(
            nprefix + (ctor_args.len() - num_extra) + (args.len() - (rec.major_idx() + 1))
        );
        fused_args.extend_from_slice(&args[..nprefix]);
        fused_args.extend_from_slice(&ctor_args[num_extra..]);
        fused_args.extend_from_slice(&args[rec.major_idx() + 1..]);
        result = self.apply_many(depth, result, &fused_args);
        Some(result)
'''
if old not in s:
    raise SystemExit('target fire_recursor block not found')
p.write_text(s.replace(old, new, 1))
print('iota apply fusion separator applied')
