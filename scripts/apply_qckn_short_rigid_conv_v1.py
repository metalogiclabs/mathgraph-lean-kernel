#!/usr/bin/env python3
from pathlib import Path

# util.rs
p=Path("src/util.rs")
c=p.read_text()

old="""pub(crate) const PRUNE_DM_LEN: usize = 1 << 10;
pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;
"""
new=old+"""
pub(crate) const SHORT_RIGID_CONV_DM_LEN: usize = 1 << 16;
pub(crate) const SHORT_RIGID_CONV_DM_SHIFT: u32 = 64 - 16;
"""
if c.count(old)!=1: raise SystemExit(f"const anchor mismatch {c.count(old)}")
c=c.replace(old,new,1)

old="""    pub(crate) conv_cache_neg_probe: FxHashSet<(usize, usize)>,
"""
new=old+"""    pub(crate) short_rigid_conv_dm: Box<[(usize, usize); SHORT_RIGID_CONV_DM_LEN]>,
"""
if c.count(old)!=1: raise SystemExit(f"field anchor mismatch {c.count(old)}")
c=c.replace(old,new,1)

old="""            conv_cache_neg_probe: small_fx_hash_set(),
"""
new=old+"""            short_rigid_conv_dm: Box::new([(0usize, 0usize); SHORT_RIGID_CONV_DM_LEN]),
"""
if c.count(old)!=1: raise SystemExit(f"init anchor mismatch {c.count(old)}")
c=c.replace(old,new,1)

old="""        self.conv_cache_neg_probe.clear();
"""
new=old+"""        self.short_rigid_conv_dm.fill((0, 0));
"""
if c.count(old)!=1: raise SystemExit(f"clear anchor mismatch {c.count(old)}")
c=c.replace(old,new,1)

old="""        shrink_set(&mut self.conv_cache_neg_probe);
"""
new=old+"""        self.short_rigid_conv_dm.fill((0, 0));
"""
if c.count(old)!=1: raise SystemExit(f"clear_session anchor mismatch {c.count(old)}")
c=c.replace(old,new,1)
p.write_text(c)

# conv.rs
p=Path("src/conv.rs")
c=p.read_text()

anchor="""    fn unify_spine<const RIGID: bool>(&mut self, depth: u32, sx: S<'t>, sy: S<'t>, sig: Sig, limit: u32) -> bool {
"""
helper="""    #[inline]
    fn unify_short_rigid_spine_cached<const RIGID: bool>(
        &mut self,
        depth: u32,
        x: V<'t>,
        y: V<'t>,
        sx: S<'t>,
        sy: S<'t>,
        sig: Sig,
        limit: u32,
    ) -> bool {
        if sx.len().max(sy.len()) > 4 {
            return self.unify_spine::<RIGID>(depth, sx, sy, sig, limit);
        }
        let xa = x as *const Value<'t> as usize;
        let ya = y as *const Value<'t> as usize;
        let key = if xa < ya { (xa, ya) } else { (ya, xa) };
        let slot = ((((key.0 as u64).wrapping_mul(0x9E3779B97F4A7C15))
            ^ (key.1 as u64).wrapping_mul(0xD6E8FEB86659FD93))
            >> crate::util::SHORT_RIGID_CONV_DM_SHIFT) as usize;
        if self.tc_cache.short_rigid_conv_dm[slot] == key {
            return true;
        }
        let result = self.unify_spine::<RIGID>(depth, sx, sy, sig, limit);
        if result {
            self.tc_cache.short_rigid_conv_dm[slot] = key;
        }
        result
    }

"""
if c.count(anchor)!=1: raise SystemExit(f"spine anchor mismatch {c.count(anchor)}")
c=c.replace(anchor,helper+anchor,1)

repls=[
("""            (Value::Rigid { head: hx, spine: sx, .. }, Value::Rigid { head: hy, spine: sy, .. }) if rigid_head_eq(*hx, *hy) =>
                self.unify_spine::<RIGID>(depth, sx, sy, Sig::ALL_RELEVANT, 0),
""",
"""            (Value::Rigid { head: hx, spine: sx, .. }, Value::Rigid { head: hy, spine: sy, .. }) if rigid_head_eq(*hx, *hy) =>
                self.unify_short_rigid_spine_cached::<RIGID>(depth, t, t2, sx, sy, Sig::ALL_RELEVANT, 0),
"""),
("""                self.unify_spine::<RIGID>(depth, sx, sy, sig, limit)
            }
            (
                Value::Rigid { head: RigidHead::Inductive(nx, lx), spine: sx, .. },
""",
"""                self.unify_short_rigid_spine_cached::<RIGID>(depth, t, t2, sx, sy, sig, limit)
            }
            (
                Value::Rigid { head: RigidHead::Inductive(nx, lx), spine: sx, .. },
"""),
("""                self.unify_spine::<RIGID>(depth, sx, sy, sig, limit)
            }
            (
                Value::Rigid { head: RigidHead::Axiom(nx, lx), spine: sx, .. },
""",
"""                self.unify_short_rigid_spine_cached::<RIGID>(depth, t, t2, sx, sy, sig, limit)
            }
            (
                Value::Rigid { head: RigidHead::Axiom(nx, lx), spine: sx, .. },
"""),
("""                self.unify_spine::<RIGID>(depth, sx, sy, sig, limit)
            }

            (
                Value::Rigid { head: RigidHead::Recursor(nx, lx), spine: sx, .. },
""",
"""                self.unify_short_rigid_spine_cached::<RIGID>(depth, t, t2, sx, sy, sig, limit)
            }

            (
                Value::Rigid { head: RigidHead::Recursor(nx, lx), spine: sx, .. },
"""),
("""                return self.unify_spine::<true>(depth, sx, sy, sig, limit);
""",
"""                return self.unify_short_rigid_spine_cached::<true>(depth, t, t2, sx, sy, sig, limit);
"""),
("""        } else if heads_match {
            self.unify_spine::<false>(depth, sx, sy, sig, limit)
        } else {
            false
        }
    }

    fn iota_or_self""",
"""        } else if heads_match {
            self.unify_short_rigid_spine_cached::<false>(depth, t, t2, sx, sy, sig, limit)
        } else {
            false
        }
    }

    fn iota_or_self"""),
]
for old,new in repls:
    if c.count(old)!=1:
        raise SystemExit(f"conv replacement anchor mismatch {old[:60]!r}: {c.count(old)}")
    c=c.replace(old,new,1)

p.write_text(c)
print("QCKN_SHORT_RIGID_CONV_V1_PATCH=PASS")
