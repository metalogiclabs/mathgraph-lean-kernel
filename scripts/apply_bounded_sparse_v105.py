#!/usr/bin/env python3
from pathlib import Path

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, found {n}")
    return text.replace(old, new, 1)

# util.rs
p = Path("src/util.rs")
c = p.read_text()
c = replace_once(c,
"""    pub(crate) wide_uses_cache: FxHashMap<ExprPtr<'t>, Box<[u64]>>,
    pub(crate) wide_prune_cache: FxHashMap<(usize, ExprPtr<'t>), E<'a>>,""",
"""    pub(crate) wide_uses_cache: FxHashMap<ExprPtr<'t>, Box<[u64]>>,
    pub(crate) bounded_sparse_uses_cache: FxHashMap<ExprPtr<'t>, Option<Box<[u16]>>>,
    pub(crate) wide_prune_cache: FxHashMap<(usize, ExprPtr<'t>), E<'a>>,""",
"util field")
c = replace_once(c,
"""            wide_uses_cache: session_small_fx_hash_map(),
            wide_prune_cache: session_fx_hash_map(),""",
"""            wide_uses_cache: session_small_fx_hash_map(),
            bounded_sparse_uses_cache: session_small_fx_hash_map(),
            wide_prune_cache: session_fx_hash_map(),""",
"util init")
c = replace_once(c,
"""        self.wide_uses_cache.clear();
        self.wide_prune_cache.clear();""",
"""        self.wide_uses_cache.clear();
        self.bounded_sparse_uses_cache.clear();
        self.wide_prune_cache.clear();""",
"util clear")
c = replace_once(c,
"""        shrink_map(&mut self.wide_uses_cache);
        shrink_map(&mut self.wide_prune_cache);""",
"""        shrink_map(&mut self.wide_uses_cache);
        shrink_map(&mut self.bounded_sparse_uses_cache);
        shrink_map(&mut self.wide_prune_cache);""",
"util clear_session")
p.write_text(c)

# value.rs
p = Path("src/value.rs")
c = p.read_text()
wide = """    WideFramed {
        words: &'a [u64],
        slots: &'a [V<'a>],
        lsub: Option<&'a LevelSub<'a>>,
        hash: u64,
        len: u32,
        prune: Cell<(u64, Option<E<'a>>)>,
    },"""
c = replace_once(c, wide, wide + """
    SparseFramed {
        indices: &'a [u16],
        slots: &'a [V<'a>],
        lsub: Option<&'a LevelSub<'a>>,
        hash: u64,
        len: u32,
        prune: Cell<(u64, Option<E<'a>>)>,
    },""", "value enum")
c = replace_once(c,
"""Env::Nil { hash, .. } | Env::Cons { hash, .. } | Env::Framed { hash, .. } | Env::WideFramed { hash, .. } => *hash,""",
"""Env::Nil { hash, .. } | Env::Cons { hash, .. } | Env::Framed { hash, .. } | Env::WideFramed { hash, .. } | Env::SparseFramed { hash, .. } => *hash,""",
"value hash")
c = replace_once(c,
"""Env::Cons { len, .. } | Env::Framed { len, .. } | Env::WideFramed { len, .. } => *len,""",
"""Env::Cons { len, .. } | Env::Framed { len, .. } | Env::WideFramed { len, .. } | Env::SparseFramed { len, .. } => *len,""",
"value len")
c = replace_once(c,
"""Env::Nil { lsub, .. } | Env::Cons { lsub, .. } | Env::Framed { lsub, .. } | Env::WideFramed { lsub, .. } => *lsub,""",
"""Env::Nil { lsub, .. } | Env::Cons { lsub, .. } | Env::Framed { lsub, .. } | Env::WideFramed { lsub, .. } | Env::SparseFramed { lsub, .. } => *lsub,""",
"value lsub")
lookup = """                Env::WideFramed { words, slots, .. } => {
                    let wi = usize::from(idx) / 64;
                    let bi = u32::from(idx % 64);
                    let Some(&word) = words.get(wi) else { return None };
                    if (word >> bi) & 1 == 0 {
                        return None;
                    }
                    let before_words: usize = words[..wi].iter().map(|w| w.count_ones() as usize).sum();
                    let below = if bi == 0 { 0 } else { word & ((1u64 << bi) - 1) };
                    return Some(slots[before_words + below.count_ones() as usize]);
                }"""
c = replace_once(c, lookup, lookup + """
                Env::SparseFramed { indices, slots, .. } => {
                    return indices.binary_search(&idx).ok().map(|i| slots[i]);
                }""", "value lookup")
p.write_text(c)

# eval.rs
p = Path("src/eval.rs")
c = p.read_text()
wide_bit = """#[inline]
fn wide_bit(words: &[u64], idx: usize) -> bool {
    words.get(idx / 64).is_some_and(|w| ((w >> (idx % 64)) & 1) != 0)
}
"""
helpers = wide_bit + """
const SPARSE_PROBE_CAP: usize = 64;

fn merge_sparse_bounded(mut a: Vec<u16>, b: Vec<u16>) -> Option<Vec<u16>> {
    a.extend(b);
    a.sort_unstable();
    a.dedup();
    if a.len() > SPARSE_PROBE_CAP { None } else { Some(a) }
}

fn under_binder_sparse(indices: Vec<u16>) -> Vec<u16> {
    indices.into_iter().filter_map(|i| i.checked_sub(1)).collect()
}
"""
c = replace_once(c, wide_bit, helpers, "eval sparse helpers")

anchor = """    fn exact_wide_uses(&mut self, e: ExprPtr<'t>) -> Option<Vec<u64>> {"""
sparse = """    fn intern_sparse_frame(
        &mut self,
        indices: &[u16],
        slots: &[V<'t>],
        lsub: Option<&'t value::LevelSub<'t>>,
    ) -> E<'t> {
        debug_assert!(!indices.is_empty());
        debug_assert_eq!(indices.len(), slots.len());
        let lsub_addr = lsub.map_or(0, |l| l as *const value::LevelSub<'t> as usize);
        let mut hash = (lsub_addr as u64) ^ 0x6A09_E667_F3BC_C909;
        for &i in indices {
            hash = hash.wrapping_mul(0x9E37_79B9_7F4A_7C15).wrapping_add(u64::from(i));
        }
        for &v in slots {
            hash = hash
                .wrapping_mul(0xD6E8_FEB8_6659_FD93)
                .wrapping_add(v as *const Value<'t> as usize as u64);
        }
        if let Some(e) = self.tc_cache.frames.find(hash, |e: &E<'t>| match e {
            value::Env::SparseFramed { indices: ei, slots: es, lsub: el, .. } =>
                el.map_or(0, |l| l as *const value::LevelSub<'t> as usize) == lsub_addr
                    && *ei == indices
                    && es.len() == slots.len()
                    && es.iter().zip(slots).all(|(a, b)| std::ptr::eq(*a, *b)),
            _ => false,
        }) {
            return e;
        }
        let len = u32::from(*indices.last().unwrap()) + 1;
        let e: E<'t> = self.arena.alloc(value::Env::SparseFramed {
            indices: self.arena.alloc_slice_copy(indices),
            slots: self.arena.alloc_slice_copy(slots),
            lsub,
            hash,
            len,
            prune: std::cell::Cell::new((0, None)),
        });
        self.tc_cache.frames.insert_unique(hash, e, |e| e.get_hash());
        e
    }

    fn exact_sparse_uses_bounded(&mut self, e: ExprPtr<'t>) -> Option<Vec<u16>> {
        if let Some(cached) = self.tc_cache.bounded_sparse_uses_cache.get(&e) {
            return cached.as_ref().map(|x| x.to_vec());
        }
        let node = *self.ctx.read_expr_ref(e);
        let result = match node {
            Expr::Var { dbj_idx, .. } => Some(vec![dbj_idx]),
            Expr::App { fun, arg, .. } => {
                let a = self.exact_sparse_uses_bounded(fun)?;
                let b = self.exact_sparse_uses_bounded(arg)?;
                merge_sparse_bounded(a, b)
            }
            Expr::Pi { binder_type, body, .. } | Expr::Lambda { binder_type, body, .. } => {
                let d = self.exact_sparse_uses_bounded(binder_type)?;
                let b = under_binder_sparse(self.exact_sparse_uses_bounded(body)?);
                merge_sparse_bounded(d, b)
            }
            Expr::Let { data, .. } => {
                let d = *data;
                let t = self.exact_sparse_uses_bounded(d.binder_type)?;
                let v = self.exact_sparse_uses_bounded(d.val)?;
                let b = under_binder_sparse(self.exact_sparse_uses_bounded(d.body)?);
                merge_sparse_bounded(merge_sparse_bounded(t, v)?, b)
            }
            Expr::Proj { structure, .. } => self.exact_sparse_uses_bounded(structure),
            Expr::Sort { .. } | Expr::Const { .. } | Expr::StringLit { .. } | Expr::NatLit { .. } => Some(Vec::new()),
        };
        self.tc_cache.bounded_sparse_uses_cache.insert(
            e,
            result.as_ref().map(|x| x.clone().into_boxed_slice()),
        );
        result
    }

    fn prune_env_sparse(&mut self, env: E<'t>, indices: &[u16]) -> E<'t> {
        if indices.is_empty() {
            return self.lsub_base(env.lsub());
        }
        let mut slots = Vec::with_capacity(indices.len());
        for &idx in indices {
            let Some(v) = env.lookup(idx) else { return env };
            slots.push(v);
        }
        self.intern_sparse_frame(indices, &slots, env.lsub())
    }

"""
c = replace_once(c, anchor, sparse + anchor, "eval exact wide anchor")

wide_branch = """                value::Env::WideFramed { words: frame_words, slots: frame_slots, .. } => {
                    for j in 0..=highest - offset {
                        if !wide_bit(words, offset + j) {
                            continue;
                        }
                        if !wide_bit(frame_words, j) {
                            return e;
                        }
                        let wi = j / 64;
                        let bi = j % 64;
                        let before: usize = frame_words[..wi].iter().map(|w| w.count_ones() as usize).sum();
                        let below = if bi == 0 { 0 } else { frame_words[wi] & ((1u64 << bi) - 1) };
                        slots.push(frame_slots[before + below.count_ones() as usize]);
                    }
                    offset = highest + 1;
                }"""
c = replace_once(c, wide_branch, wide_branch + """
                value::Env::SparseFramed { indices, slots: frame_slots, .. } => {
                    for j in 0..=highest - offset {
                        if !wide_bit(words, offset + j) {
                            continue;
                        }
                        let Ok(pos) = indices.binary_search(&(j as u16)) else { return e };
                        slots.push(frame_slots[pos]);
                    }
                    offset = highest + 1;
                }""", "prune_env_wide sparse")

c = c.replace(
"""            value::Env::Cons { prune, .. } | value::Env::WideFramed { prune, .. } => {""",
"""            value::Env::Cons { prune, .. } | value::Env::WideFramed { prune, .. } | value::Env::SparseFramed { prune, .. } => {""")
c = c.replace(
"""                    | value::Env::WideFramed { prune, .. } => prune.set((mask, Some(hit))),""",
"""                    | value::Env::WideFramed { prune, .. }
                    | value::Env::SparseFramed { prune, .. } => prune.set((mask, Some(hit))),""")
c = c.replace(
"""            | value::Env::WideFramed { prune, .. } => prune.set((mask, Some(r))),""",
"""            | value::Env::WideFramed { prune, .. }
            | value::Env::SparseFramed { prune, .. } => prune.set((mask, Some(r))),""")

cold = """                value::Env::WideFramed { words, slots, .. } => {
                    let fmask = words.first().copied().unwrap_or(0);
                    let limit = 64 - consumed;
                    let bound = if limit >= 64 { u64::MAX } else { (1u64 << limit) - 1 };
                    let m2 = rem & fmask & bound;
                    out_mask |= m2 << consumed;
                    let mut sel = select_ranks(m2, fmask);
                    while sel != 0 {
                        let i = sel.trailing_zeros() as usize;
                        sel &= sel - 1;
                        let sv = slots[i];
                        buf[n].write(sv);
                        slots_hash = slots_hash
                            .wrapping_mul(0x9E3779B97F4A7C15)
                            .wrapping_add(sv as *const Value<'t> as usize as u64);
                        n += 1;
                    }
                    break;
                }"""
c = replace_once(c, cold, cold + """
                value::Env::SparseFramed { indices, slots, .. } => {
                    for (&idx, &sv) in indices.iter().zip(*slots) {
                        let j = u32::from(idx);
                        if j >= 64 - consumed { break; }
                        if (rem >> j) & 1 != 0 {
                            buf[n].write(sv);
                            slots_hash = slots_hash
                                .wrapping_mul(0x9E3779B97F4A7C15)
                                .wrapping_add(sv as *const Value<'t> as usize as u64);
                            out_mask |= 1u64 << (j + consumed);
                            n += 1;
                        }
                    }
                    break;
                }""", "prune_env_cold sparse")

key = """        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
key2 = """        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let r = if let Some(words) = self.exact_wide_uses(e) {
                self.prune_env_wide(env, &words)
            } else if let Some(indices) = self.exact_sparse_uses_bounded(e) {
                self.prune_env_sparse(env, &indices)
            } else {
                env
            };
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
c = replace_once(c, key, key2, "key_env bounded sparse")
p.write_text(c)

print("APPLY_BOUNDED_SPARSE_V105=PASS")
