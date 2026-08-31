from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / 'src/eval.rs'
s = p.read_text()
old = """        match e {
            value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => prune.set((mask, Some(r))),
            value::Env::Nil { .. } => {}
        }
        r
    }"""
new = """        match e {
            value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => {
                let (old_mask, old_r) = prune.get();
                if old_r.is_none() || old_mask == mask {
                    prune.set((mask, Some(r)));
                }
            }
            value::Env::Nil { .. } => {}
        }
        r
    }"""
assert old in s, 'sticky-prune target not found'
p.write_text(s.replace(old, new, 1))
