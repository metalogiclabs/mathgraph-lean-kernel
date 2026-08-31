from pathlib import Path
import sys

root = Path(sys.argv[1])
mode = sys.argv[2]
p = root / 'src/eval.rs'
s = p.read_text()

cold_old = """        match e {
            value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => prune.set((mask, Some(r))),
            value::Env::Nil { .. } => {}
        }
        r
    }"""

dm_old = """                match e {
                    value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } =>
                        prune.set((mask, Some(hit))),
                    value::Env::Nil { .. } => {}
                }
                return hit;"""

assert cold_old in s, 'cold write target not found'
assert dm_old in s, 'dm write target not found'

if mode == 'no_cold':
    cold_new = """        r
    }"""
    s = s.replace(cold_old, cold_new, 1)
elif mode == 'first_cold':
    cold_new = """        match e {
            value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => {
                if prune.get().1.is_none() {
                    prune.set((mask, Some(r)));
                }
            }
            value::Env::Nil { .. } => {}
        }
        r
    }"""
    s = s.replace(cold_old, cold_new, 1)
elif mode == 'full_sticky':
    cold_new = """        match e {
            value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => {
                if prune.get().1.is_none() {
                    prune.set((mask, Some(r)));
                }
            }
            value::Env::Nil { .. } => {}
        }
        r
    }"""
    dm_new = """                match e {
                    value::Env::Cons { prune, .. } | value::Env::Framed { prune, .. } => {
                        if prune.get().1.is_none() {
                            prune.set((mask, Some(hit)));
                        }
                    }
                    value::Env::Nil { .. } => {}
                }
                return hit;"""
    s = s.replace(cold_old, cold_new, 1)
    s = s.replace(dm_old, dm_new, 1)
else:
    raise SystemExit(f'unknown mode: {mode}')

p.write_text(s)
print(f'V4_STEP21_APPLIED={mode}')
