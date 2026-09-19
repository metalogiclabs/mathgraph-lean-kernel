from pathlib import Path
import sys

root = Path(sys.argv[1])
mode = sys.argv[2]
assert mode in {"all", "apppi"}

# Add an experiment-only cache whose key is exactly the semantic content that
# intern_frame uses to identify a projected environment: expression, level-sub
# identity, projected mask, and projected value-pointer sequence.
up = root / "src/util.rs"
us = up.read_text()
old = "    pub(crate) open_eval_cache: FxHashMap<(usize, ExprPtr<'t>), V<'a>>,\n"
new = old + "    pub(crate) structural_open_eval_cache: FxHashMap<(ExprPtr<'t>, usize, u64, smallvec::SmallVec<[usize; 8]>), V<'a>>,\n"
assert old in us
us = us.replace(old, new, 1)
old = "            open_eval_cache: session_fx_hash_map(),\n"
new = old + "            structural_open_eval_cache: session_fx_hash_map(),\n"
assert old in us
us = us.replace(old, new, 1)
old = "        self.open_eval_cache.clear();\n"
new = old + "        self.structural_open_eval_cache.clear();\n"
assert old in us
us = us.replace(old, new, 1)
old = "        shrink_map(&mut self.open_eval_cache);\n"
new = old + "        shrink_map(&mut self.structural_open_eval_cache);\n"
assert old in us
us = us.replace(old, new, 1)
up.write_text(us)

ep = root / "src/eval.rs"
es = ep.read_text()
anchor = "    #[inline]\n    pub(crate) fn key_env(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {\n"
helper = r'''    // Compute the exact semantic identity of prune_env(env, mask) without
    // allocating or interning a Framed environment. This mirrors
    // prune_env_cold's projection order and intern_frame equality key.
    #[inline]
    fn projected_env_key(&self, e: E<'t>, mask: u64) -> (usize, u64, smallvec::SmallVec<[usize; 8]>) {
        let lsub_addr = e.lsub().map_or(0, |l| l as *const value::LevelSub<'t> as usize);
        let mut slots: smallvec::SmallVec<[usize; 8]> = smallvec::SmallVec::new();
        let mut out_mask = 0u64;
        let mut rem = mask;
        let mut consumed = 0u32;
        let mut cur = e;
        while rem != 0 {
            match cur {
                value::Env::Nil { .. } => break,
                value::Env::Framed { mask: fmask, slots: fslots, .. } => {
                    let limit = 64 - consumed;
                    let bound = if limit >= 64 { u64::MAX } else { (1u64 << limit) - 1 };
                    let m2 = rem & *fmask & bound;
                    out_mask |= m2 << consumed;
                    let mut sel = select_ranks(m2, *fmask);
                    while sel != 0 {
                        let i = sel.trailing_zeros() as usize;
                        sel &= sel - 1;
                        slots.push(fslots[i] as *const Value<'t> as usize);
                    }
                    break;
                }
                value::Env::Cons { v, parent, .. } => {
                    if rem & 1 != 0 {
                        slots.push(*v as *const Value<'t> as usize);
                        out_mask |= 1u64 << consumed;
                    }
                    rem >>= 1;
                    if rem == 0 { break; }
                    consumed += 1;
                    cur = parent;
                }
            }
        }
        (lsub_addr, out_mask, slots)
    }

'''
assert anchor in es
es = es.replace(anchor, helper + anchor, 1)

old = '''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                return v;
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }
'''
if mode == "all":
    gate = "true"
else:
    gate = "matches!(self.ctx.read_expr_ref(e), Expr::App { .. } | Expr::Pi { .. })"
new = f'''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App {{ .. }} | Expr::Proj {{ .. }} | Expr::Let {{ .. }} | Expr::Pi {{ .. }} | Expr::Lambda {{ .. }}
        ) {{
            // Probe by the exact projected-environment semantics before key_env
            // materializes/interns the frame. Restrict to the same <=64-bvar
            // regime where key_env performs masked projection.
            let use_struct = {gate};
            let k = e.num_loose_bvars();
            let structural_key = if use_struct && k > 0 && k <= 64 {{
                let (ls, m, slots) = self.projected_env_key(env, e.as_ref().fv_mask());
                let sk = (e, ls, m, slots);
                if let Some(v) = self.tc_cache.structural_open_eval_cache.get(&sk) {{
                    return v;
                }}
                Some(sk)
            }} else {{
                None
            }};

            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {{
                if let Some(sk) = structural_key {{ self.tc_cache.structural_open_eval_cache.insert(sk, v); }}
                return v;
            }}
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            if let Some(sk) = structural_key {{ self.tc_cache.structural_open_eval_cache.insert(sk, v); }}
            return v;
        }}
'''
assert old in es, "open eval cache block changed"
es = es.replace(old, new, 1)
ep.write_text(es)
