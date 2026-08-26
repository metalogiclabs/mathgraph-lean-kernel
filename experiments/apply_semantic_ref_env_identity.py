from pathlib import Path
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')

# First tranche of the Indexed Closure Kernel hypothesis.
#
# Current semantic keys reconstruct the captured environment by repeatedly
# looking up and digesting every live slot.  This prototype instead treats the
# persistent environment itself as the identity-bearing semantic object:
#
#     SemanticRef ~= (ExprPtr identity, Env identity)
#
# Env::hash is maintained incrementally when frames are extended, so reading it
# is O(1).  We deliberately make the closedness result conservative whenever a
# body actually captures variables; this can only disable optimisations.  It
# therefore makes the performance test harder to win and avoids pretending the
# environment hash proves semantic closedness.

vp = root / 'src/value.rs'
vs = vp.read_text()

old_closure = '''fn closure_key(clo: &Closure<'_>) -> (u64, bool) {
    let (e, c) = env_slots_key(clo.env, clo.body.num_loose_bvars().saturating_sub(1));
    let d = kmix(clo.body.as_ref() as *const crate::expr::Expr<'_> as usize as u64, e);
    (d, c && clo.ctx.is_none())
}'''
new_closure = '''fn closure_key(clo: &Closure<'_>) -> (u64, bool) {
    let captured = clo.body.num_loose_bvars().saturating_sub(1);
    let e = kmix(
        kmix(clo.env.get_hash(), lsub_key(clo.env.lsub())),
        u64::from(captured),
    );
    let d = kmix(clo.body.as_ref() as *const crate::expr::Expr<'_> as usize as u64, e);
    (d, captured == 0 && clo.ctx.is_none())
}'''
assert old_closure in vs, 'closure_key anchor changed'
vs = vs.replace(old_closure, new_closure, 1)

old_thunk = '''            Value::Thunk { env, expr, .. } => {
                let (e, c) = env_slots_key(env, expr.num_loose_bvars());
                seal(kmix(kmix(13, expr.as_ref() as *const crate::expr::Expr<'a> as usize as u64), e), c)
            }'''
new_thunk = '''            Value::Thunk { env, expr, .. } => {
                let captured = expr.num_loose_bvars();
                let e = kmix(
                    kmix(env.get_hash(), lsub_key(env.lsub())),
                    u64::from(captured),
                );
                seal(
                    kmix(kmix(13, expr.as_ref() as *const crate::expr::Expr<'a> as usize as u64), e),
                    captured == 0,
                )
            }'''
assert old_thunk in vs, 'Thunk key anchor changed'
vs = vs.replace(old_thunk, new_thunk, 1)
vp.write_text(vs)

# The global semantic key in eval.rs has the same representation tax.  Replace
# traversal of the captured slots with the persistent environment identity.
# This is deliberately a cache-key change only; evaluation and conversion
# semantics remain untouched.
ep = root / 'src/eval.rs'
es = ep.read_text()
old_env_key = '''    fn env_key(&mut self, acc: u128, closed: bool, env: E<'t>, depth: u32, count: u16) -> Result<(u128, bool), u8> {
        let mut acc = acc;
        let mut closed = closed;
        if let Some(ls) = env.lsub() {
            acc = mix(mix(acc, u128::from(ls.ks.get_hash())), u128::from(ls.vs.get_hash()));
        }
        for i in 0..count {
            if let Some(slot) = env.lookup(i) {
                let (k, c) = self.global_key(slot, depth)?;
                acc = mix(mix(acc, u128::from(i)), k);
                closed &= c;
            }
        }
        Ok((acc, closed))
    }'''
new_env_key = '''    fn env_key(&mut self, acc: u128, closed: bool, env: E<'t>, _depth: u32, count: u16) -> Result<(u128, bool), u8> {
        let mut acc = acc;
        if let Some(ls) = env.lsub() {
            acc = mix(mix(acc, u128::from(ls.ks.get_hash())), u128::from(ls.vs.get_hash()));
        }
        acc = mix(acc, u128::from(env.get_hash()));
        acc = mix(acc, u128::from(count));
        Ok((acc, closed && count == 0))
    }'''
assert old_env_key in es, 'eval.rs env_key anchor changed'
es = es.replace(old_env_key, new_env_key, 1)
ep.write_text(es)

print('applied semantic-ref v1: O(1) persistent environment identity keys')
