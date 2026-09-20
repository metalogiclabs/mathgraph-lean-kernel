#!/usr/bin/env python3
from pathlib import Path

# util.rs
p=Path("src/util.rs")
c=p.read_text()

anchor="""pub(crate) const PRUNE_DM_LEN: usize = 1 << 10;
pub(crate) const PRUNE_DM_SHIFT: u32 = 64 - 10;
"""
insert=anchor+"""
pub(crate) const APP_CONV_DM_LEN: usize = 1 << 13;
pub(crate) const APP_CONV_DM_SHIFT: u32 = 64 - 13;
"""
if c.count(anchor) != 1:
    raise SystemExit("dm const anchor mismatch")
c=c.replace(anchor,insert,1)

field="""    pub(crate) type_cache: FxHashMap<(usize, ExprPtr<'t>), crate::infer::CachedType<'a>>,
"""
field_new=field+"""    pub(crate) app_conv_dm: Box<[(usize, usize); APP_CONV_DM_LEN]>,
"""
if c.count(field) != 1:
    raise SystemExit("field anchor mismatch")
c=c.replace(field,field_new,1)

init="""            type_cache: session_fx_hash_map(),
"""
init_new=init+"""            app_conv_dm: Box::new([(0usize, 0usize); APP_CONV_DM_LEN]),
"""
if c.count(init) != 1:
    raise SystemExit("init anchor mismatch")
c=c.replace(init,init_new,1)

clear="""        self.type_cache.clear();
"""
clear_new=clear+"""        self.app_conv_dm.fill((0, 0));
"""
if c.count(clear) != 1:
    raise SystemExit("clear anchor mismatch")
c=c.replace(clear,clear_new,1)

clear_session="""        shrink_map(&mut self.type_cache);
"""
clear_session_new=clear_session+"""        self.app_conv_dm.fill((0, 0));
"""
if c.count(clear_session) != 1:
    raise SystemExit("clear_session anchor mismatch")
c=c.replace(clear_session,clear_session_new,1)
p.write_text(c)

# infer.rs
p=Path("src/infer.rs")
c=p.read_text()
old="""            if flag == Check {
                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");
            }
"""
new="""            if flag == Check {
                let arg_ty = self.infer_value(flag, depth, env, ctx, arg);
                let da = domain as *const Value<'t> as usize;
                let aa = arg_ty as *const Value<'t> as usize;
                let pair = if da < aa { (da, aa) } else { (aa, da) };
                let slot = ((((pair.0 as u64).wrapping_mul(0x9E3779B97F4A7C15))
                    ^ (pair.1 as u64).wrapping_mul(0xD6E8FEB86659FD93))
                    >> crate::util::APP_CONV_DM_SHIFT) as usize;
                if self.tc_cache.app_conv_dm[slot] != pair {
                    assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");
                    self.tc_cache.app_conv_dm[slot] = pair;
                }
            }
"""
if c.count(old) != 1:
    raise SystemExit(f"infer app anchor mismatch: {c.count(old)}")
c=c.replace(old,new,1)
p.write_text(c)
print("QCKN_APP_CONV_DIRECTMAP_V1_PATCH=PASS")
