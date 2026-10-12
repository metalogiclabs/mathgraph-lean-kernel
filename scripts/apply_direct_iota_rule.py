#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src/eval.rs"
s = p.read_text()

old = '''        let (ctor_name, ctor_args) = self.unwrap_ctor_app(depth, major)?;
        let rec_rule = rec.rec_rules.iter().find(|r| r.ctor_name == ctor_name).copied()?;
        let num_extra = ctor_args.len().checked_sub(usize::from(rec_rule.ctor_telescope_size_wo_params))?;'''
new = '''        let (ctor_name, ctor_args) = self.unwrap_ctor_app(depth, major)?;
        // Fast separator: constructor metadata already carries its 0-based constructor index.
        // Use it only when the indexed recursor rule confirms the same constructor name;
        // otherwise preserve the exact historical linear-search behavior. This is semantics-safe
        // even for mutual/nested cases whose rec_rules ordering does not match ctor_idx.
        let rec_rule = if let Some(ctor) = self.env.get_constructor(&ctor_name) {
            rec.rec_rules
                .get(usize::from(ctor.ctor_idx))
                .filter(|r| r.ctor_name == ctor_name)
                .copied()
                .or_else(|| rec.rec_rules.iter().find(|r| r.ctor_name == ctor_name).copied())?
        } else {
            rec.rec_rules.iter().find(|r| r.ctor_name == ctor_name).copied()?
        };
        let num_extra = ctor_args.len().checked_sub(usize::from(rec_rule.ctor_telescope_size_wo_params))?;'''

assert old in s, "fire_recursor rule lookup shape changed"
p.write_text(s.replace(old, new, 1))
print("direct iota rule separator applied")
