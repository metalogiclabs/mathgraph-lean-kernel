from pathlib import Path
import subprocess
import sys

cand = Path(sys.argv[1])
base = Path('/tmp/base-src')
repo = Path(__file__).resolve().parent.parent

# Build the admitted V2 baseline in both arms: soundness repair + beta fusion
# + eval-side projection fusion. The active separator workflow supplies exact V1
# worktrees at /tmp/base-src and /tmp/linear-src.
for root in (base, cand):
    subprocess.run([sys.executable, str(repo / 'scripts/apply_extra_rec_soundness.py'), str(root)], check=True)
    subprocess.run([sys.executable, str(repo / 'scripts/apply_infer_beta_fusion.py'), str(root)], check=True)

    p = root / 'src/eval.rs'
    s = p.read_text()
    old_lam = '''            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>
                {
                let ce = self.key_env(env, e);
                value::mk_lam(self.arena, binder_name, binder_style, binder_type, Closure::mk_eval(ce, body))
            }'''
    new_lam = '''            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>
                value::mk_lam(self.arena, binder_name, binder_style, binder_type, Closure::mk_eval(env, body)),'''
    old_pi = '''                {
                    let ce = self.key_env(env, e);
                    value::mk_pi(self.arena, binder_name, binder_style, dom, Closure::mk_eval(ce, body))
                }'''
    new_pi = '''                value::mk_pi(self.arena, binder_name, binder_style, dom, Closure::mk_eval(env, body))'''
    assert old_lam in s, 'eval lambda producer shape changed'
    assert old_pi in s, 'eval pi producer shape changed'
    p.write_text(s.replace(old_lam, new_lam, 1).replace(old_pi, new_pi, 1))

# Candidate only: preserve an already-minimal framed environment across a binder
# extension instead of rebuilding a Cons node that key_env/prune_env must project
# again downstream. This directly targets the measured cold pattern: ~0.96 Cons
# steps per cold prune followed by a tiny frame (~2.76 selected values).
p = cand / 'src/value.rs'
s = p.read_text()
old = '''pub fn env_extend<'a>(arena: &'a Bump, parent: E<'a>, v: V<'a>) -> E<'a> {
    let v_hash = v as *const Value<'a> as usize as u64;
    let parent_hash = parent.get_hash();
    let hash = parent_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(v_hash);
    arena.alloc(Env::Cons {
        v,
        parent,
        lsub: parent.lsub(),
        hash,
        len: parent.len() + 1,
        prune: Cell::new((0, None)),
    })
}'''
new = '''pub fn env_extend<'a>(arena: &'a Bump, parent: E<'a>, v: V<'a>) -> E<'a> {
    // Preserve compact captures directly when extending a small framed env.
    // Index 0 is the new value; all parent coordinates shift by one.
    if let Env::Framed { mask, slots, lsub, len, .. } = parent {
        if *len < 63 && slots.len() < 8 {
            let new_mask = (*mask << 1) | 1;
            let mut buf = smallvec::SmallVec::<[V<'a>; 8]>::new();
            buf.push(v);
            buf.extend_from_slice(*slots);
            let mut slots_hash = (*lsub).map_or(0, |l| l as *const LevelSub<'a> as usize as u64);
            for sv in &buf {
                slots_hash = slots_hash
                    .wrapping_mul(0x9E3779B97F4A7C15)
                    .wrapping_add(*sv as *const Value<'a> as usize as u64);
            }
            let hash = new_mask.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(slots_hash);
            return arena.alloc(Env::Framed {
                mask: new_mask,
                slots: arena.alloc_slice_copy(&buf),
                lsub: *lsub,
                hash,
                len: *len + 1,
                prune: Cell::new((0, None)),
            });
        }
    }
    let v_hash = v as *const Value<'a> as usize as u64;
    let parent_hash = parent.get_hash();
    let hash = parent_hash.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(v_hash);
    arena.alloc(Env::Cons {
        v,
        parent,
        lsub: parent.lsub(),
        hash,
        len: parent.len() + 1,
        prune: Cell::new((0, None)),
    })
}'''
assert old in s, 'env_extend shape changed'
p.write_text(s.replace(old, new, 1))
print('applied V2 baseline to both arms + direct minimal framed capture to candidate')
