from pathlib import Path
import sys

root = Path(sys.argv[1])
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
s = s.replace(cold_old, """        r
    }""", 1)
s = s.replace(dm_old, """                return hit;""", 1)
p.write_text(s)
print('V4_STEP22_NO_LOCAL_PRUNE_WRITES=YES')
