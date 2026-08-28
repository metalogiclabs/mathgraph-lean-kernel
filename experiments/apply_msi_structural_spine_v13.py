from pathlib import Path
p=Path('src/conv.rs')
s=p.read_text()
s=s.replace('use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};', '''use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};
use std::sync::atomic::{AtomicU64, Ordering};
macro_rules! ctr { ($n:ident) => { static $n: AtomicU64 = AtomicU64::new(0); }; }
ctr!(V13_UNIFY); ctr!(V13_SORT); ctr!(V13_LIT); ctr!(V13_RIGID); ctr!(V13_CTOR); ctr!(V13_IND); ctr!(V13_AXIOM); ctr!(V13_REC); ctr!(V13_PI); ctr!(V13_LAM); ctr!(V13_UNFOLD);
ctr!(V13_SIG); ctr!(V13_SIG_MASKED); ctr!(V13_SPINE); ctr!(V13_SPINE_PTR); ctr!(V13_SPINE_EMPTY); ctr!(V13_SPINE_SNOC); ctr!(V13_APP); ctr!(V13_APP_PTR); ctr!(V13_PROOF_SKIP); ctr!(V13_APP_RECURSE); ctr!(V13_PROJ); ctr!(V13_SPINE_MISMATCH);
fn v13_print(n:u64) { eprintln!("MSI_STRUCT_SPINE unify={} sort={} lit={} rigid={} ctor={} ind={} axiom={} rec={} pi={} lam={} unfold={} sig={} sig_masked={} spine={} spine_ptr={} spine_empty={} spine_snoc={} app={} app_ptr={} proof_skip={} app_recurse={} proj={} spine_mismatch={}", n,V13_SORT.load(Ordering::Relaxed),V13_LIT.load(Ordering::Relaxed),V13_RIGID.load(Ordering::Relaxed),V13_CTOR.load(Ordering::Relaxed),V13_IND.load(Ordering::Relaxed),V13_AXIOM.load(Ordering::Relaxed),V13_REC.load(Ordering::Relaxed),V13_PI.load(Ordering::Relaxed),V13_LAM.load(Ordering::Relaxed),V13_UNFOLD.load(Ordering::Relaxed),V13_SIG.load(Ordering::Relaxed),V13_SIG_MASKED.load(Ordering::Relaxed),V13_SPINE.load(Ordering::Relaxed),V13_SPINE_PTR.load(Ordering::Relaxed),V13_SPINE_EMPTY.load(Ordering::Relaxed),V13_SPINE_SNOC.load(Ordering::Relaxed),V13_APP.load(Ordering::Relaxed),V13_APP_PTR.load(Ordering::Relaxed),V13_PROOF_SKIP.load(Ordering::Relaxed),V13_APP_RECURSE.load(Ordering::Relaxed),V13_PROJ.load(Ordering::Relaxed),V13_SPINE_MISMATCH.load(Ordering::Relaxed)); }
''')
s=s.replace('fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<\'t>, y: V<\'t>) -> bool {', '''fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        let n=V13_UNIFY.fetch_add(1,Ordering::Relaxed)+1; if n%1_000_000==0 { v13_print(n); }''')
repls={
'(Value::Sort { level: lx , .. }, Value::Sort { level: ly , .. }) =>':'(Value::Sort { level: lx , .. }, Value::Sort { level: ly , .. }) => { V13_SORT.fetch_add(1,Ordering::Relaxed); return',
'(Value::NatLit { ptr: px , .. }, Value::NatLit { ptr: py , .. }) =>':'(Value::NatLit { ptr: px , .. }, Value::NatLit { ptr: py , .. }) => { V13_LIT.fetch_add(1,Ordering::Relaxed); return',
'(Value::StrLit { ptr: px , .. }, Value::StrLit { ptr: py , .. }) =>':'(Value::StrLit { ptr: px , .. }, Value::StrLit { ptr: py , .. }) => { V13_LIT.fetch_add(1,Ordering::Relaxed); return',
'} if rigid_head_eq(*hx, *hy) =>\n                self.unify_spine::<RIGID>(depth, sx, sy, Sig::ALL_RELEVANT, 0),':'} if rigid_head_eq(*hx, *hy) => { V13_RIGID.fetch_add(1,Ordering::Relaxed); self.unify_spine::<RIGID>(depth, sx, sy, Sig::ALL_RELEVANT, 0) },',
'} if nx == ny && self.ctx.eq_antisymm_many(*lx, *ly) => {\n                let (sig, limit) = self.head_spine_sig(*nx, *lx, sx, sy);':'} if nx == ny && self.ctx.eq_antisymm_many(*lx, *ly) => {\n                V13_CTOR.fetch_add(1,Ordering::Relaxed);\n                let (sig, limit) = self.head_spine_sig(*nx, *lx, sx, sy);'
}
for a,b in repls.items(): s=s.replace(a,b,1)
# repair scalar branch braces introduced above
s=s.replace('return self.ctx.eq_antisymm(*lx, *ly),','return self.ctx.eq_antisymm(*lx, *ly); },')
s=s.replace('return px == py,','return px == py; },')
# second literal
s=s.replace('return px == py,','return px == py; },',1)
# mark Pi/Lam/Unfold branch entries
s=s.replace('(Value::Pi { domain: dx, body: bx, .. }, Value::Pi { domain: dy, body: by, .. }) => {','(Value::Pi { domain: dx, body: bx, .. }, Value::Pi { domain: dy, body: by, .. }) => { V13_PI.fetch_add(1,Ordering::Relaxed);')
s=s.replace('(Value::Lam { body: bx, .. }, Value::Lam { body: by, .. }) => {','(Value::Lam { body: bx, .. }, Value::Lam { body: by, .. }) => { V13_LAM.fetch_add(1,Ordering::Relaxed);')
s=s.replace(') => {\n                let heads_match = nx == ny && self.ctx.eq_antisymm_many(*lx, *ly);\n                let (nx, ny, lx) = (*nx, *ny, *lx);\n                let sx = *sx;\n                let sy = *sy;',' ) => {\n                V13_UNFOLD.fetch_add(1,Ordering::Relaxed);\n                let heads_match = nx == ny && self.ctx.eq_antisymm_many(*lx, *ly);\n                let (nx, ny, lx) = (*nx, *ny, *lx);\n                let sx = *sx;\n                let sy = *sy;',1)
# sig census
s=s.replace('fn head_spine_sig(&mut self, name: NamePtr<\'t>, levels: LevelsPtr<\'t>, sx: S<\'t>, sy: S<\'t>) -> (Sig, u32) {\n        let sig = self.sig_of(name, levels);',"fn head_spine_sig(&mut self, name: NamePtr<'t>, levels: LevelsPtr<'t>, sx: S<'t>, sy: S<'t>) -> (Sig, u32) {\n        V13_SIG.fetch_add(1,Ordering::Relaxed); let sig = self.sig_of(name, levels);")
s=s.replace('if !sig.masks_any_arg() {','if !sig.masks_any_arg() {',1).replace('(sig, app_prefix_len(sx).min(app_prefix_len(sy)))','{ V13_SIG_MASKED.fetch_add(1,Ordering::Relaxed); (sig, app_prefix_len(sx).min(app_prefix_len(sy))) }',1)
# spine census
s=s.replace("fn unify_spine<const RIGID: bool>(&mut self, depth: u32, sx: S<'t>, sy: S<'t>, sig: Sig, limit: u32) -> bool {\n        if std::ptr::eq(sx, sy) {\n            return true;\n        }", "fn unify_spine<const RIGID: bool>(&mut self, depth: u32, sx: S<'t>, sy: S<'t>, sig: Sig, limit: u32) -> bool {\n        V13_SPINE.fetch_add(1,Ordering::Relaxed);\n        if std::ptr::eq(sx, sy) { V13_SPINE_PTR.fetch_add(1,Ordering::Relaxed); return true; }")
s=s.replace('(Spine::Empty, Spine::Empty) => true,','(Spine::Empty, Spine::Empty) => { V13_SPINE_EMPTY.fetch_add(1,Ordering::Relaxed); true },')
s=s.replace('(Spine::Snoc { prev: pa, elim: ea, .. }, Spine::Snoc { prev: pb, elim: eb, .. }) => {\n                if !self.unify_spine', '(Spine::Snoc { prev: pa, elim: ea, .. }, Spine::Snoc { prev: pb, elim: eb, .. }) => {\n                V13_SPINE_SNOC.fetch_add(1,Ordering::Relaxed);\n                if !self.unify_spine',1)
s=s.replace('(ElimView::App(va), ElimView::App(vb)) => {\n                        let idx = pa.len();','(ElimView::App(va), ElimView::App(vb)) => {\n                        V13_APP.fetch_add(1,Ordering::Relaxed); if std::ptr::eq(va,vb) { V13_APP_PTR.fetch_add(1,Ordering::Relaxed); }\n                        let idx = pa.len();',1)
s=s.replace('if idx < limit && sig.arg_is_proof(idx) {\n                            return true;\n                        }\n                        self.unify::<RIGID>(depth, va, vb)','if idx < limit && sig.arg_is_proof(idx) { V13_PROOF_SKIP.fetch_add(1,Ordering::Relaxed); return true; }\n                        V13_APP_RECURSE.fetch_add(1,Ordering::Relaxed); self.unify::<RIGID>(depth, va, vb)',1)
s=s.replace('(ElimView::Proj { ty_name: tx, idx: ix }, ElimView::Proj { ty_name: ty, idx: iy }) => tx == ty && ix == iy,','(ElimView::Proj { ty_name: tx, idx: ix }, ElimView::Proj { ty_name: ty, idx: iy }) => { V13_PROJ.fetch_add(1,Ordering::Relaxed); tx == ty && ix == iy },',1)
s=s.replace('_ => false,\n                }\n            }\n            _ => false,\n        }\n    }\n\n    fn statically_not_proof','_ => { V13_SPINE_MISMATCH.fetch_add(1,Ordering::Relaxed); false },\n                }\n            }\n            _ => { V13_SPINE_MISMATCH.fetch_add(1,Ordering::Relaxed); false },\n        }\n    }\n\n    fn statically_not_proof',1)
p.write_text(s)
print('applied MSI structural spine v13')
