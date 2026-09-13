#!/usr/bin/env python3
import re, sys
from collections import defaultdict
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit('usage: apply_full_state_selector_v119.py <v117-artifact-dir>')
ART=Path(sys.argv[1])
PAT=re.compile(
    r'V117_CELL k=(\S+) root=(\S+) mask=(\S+) var_mass=(\S+) depth=(\S+) app_spine=(\S+) '
    r'calls=(\d+) hits=(\d+) success=(\d+) fail=(\d+) selected_sum=(\d+) saved_sum=(\d+) same_env=(\d+)'
)
K={'65_96':0,'97_128':1,'129_192':2,'193_256':3,'257_384':4,'385_512':5,'513_plus':6}
ROOT={'Var':0,'Sort':1,'Const':2,'App':3,'Pi':4,'Lambda':5,'Let':6,'StringLit':7,'NatLit':8,'Proj':9}
MASK={'0':0,'1_4':1,'5_8':2,'9_16':3,'17_32':4,'33_48':5,'49_64':6}
DEPTH={'1_3':0,'4_7':1,'8_11':2,'12_15':3}
SPINE={'0':0,'1':1,'2_3':2,'4_7':3,'8_15':4}

def replace_once(text,old,new,label):
    n=text.count(old)
    if n!=1: raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return text.replace(old,new,1)

agg=defaultdict(lambda:[0,0])
for fn in [ART/'ATLAS__mathlib.stderr',ART/'ATLAS__con-leche.stderr']:
    if not fn.exists(): raise SystemExit(f'missing frozen V117 evidence: {fn}')
    for line in fn.read_text(errors='replace').splitlines():
        m=PAT.search(line)
        if not m: continue
        k,root,mask,_vm,depth,spine,*nums=m.groups()
        selected=int(nums[4]); saved=int(nums[5])
        key=(K[k],ROOT[root],MASK[mask],DEPTH[depth],SPINE[spine])
        agg[key][0]+=selected; agg[key][1]+=saved

arms=[]
for key,(selected,saved) in sorted(agg.items()):
    score=0 if selected==0 else min(65535, round(1000*saved/selected))
    arms.append(f'        {key} => {score},')
print(f'V119_TABLE_CELLS={len(arms)}')
print('V119_TABLE_SOURCE_RUN=34781716973')
print('V119_TABLE_SOURCE_ARTIFACT=10325841133')
print('V119_TABLE_SOURCE_SHA256=ed23da7d49b89b74715f10eb19d950b37784c865f7f30b6172d67e270b487e59')

p=Path('src/expr.rs'); c=p.read_text()
for label,old,new in [
('proj field',"""        structure: ExprPtr<'a>,
        fv_mask: u64,
    },""", """        structure: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u8,
    },"""),
('app field',"""        fun: ExprPtr<'a>,
        arg: ExprPtr<'a>,
        fv_mask: u64,
    },""", """        fun: ExprPtr<'a>,
        arg: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u8,
    },"""),
('pi field',"""        binder_type: ExprPtr<'a>,
        body: ExprPtr<'a>,
        fv_mask: u64,
    },
    Lambda {""", """        binder_type: ExprPtr<'a>,
        body: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u8,
    },
    Lambda {"""),
('lambda field',"""        binder_type: ExprPtr<'a>,
        body: ExprPtr<'a>,
        fv_mask: u64,
    },
    Let {""", """        binder_type: ExprPtr<'a>,
        body: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u8,
    },
    Let {"""),
('let field',"""        data: &'a LetData<'a>,
        fv_mask: u64,
    },""", """        data: &'a LetData<'a>,
        fv_mask: u64,
        boundary: u8,
    },"""),]: c=replace_once(c,old,new,label)
anchor="""pub(crate) fn ignores_binder(body: ExprPtr<'_>) -> bool {
"""
helper="""pub(crate) fn pack_boundary_v119(depth: u8, app_spine: u8) -> u8 {
    depth.min(15) | (app_spine.min(15) << 4)
}

"""+anchor
c=replace_once(c,anchor,helper,'boundary helper')
anchor="""    #[inline]
    pub(crate) fn fv_mask(&self) -> u64 {
"""
methods="""    #[inline]
    pub(crate) fn boundary_depth_v119(&self) -> u8 {
        match self {
            Var { .. } | Sort { .. } | Const { .. } | StringLit { .. } | NatLit { .. } => 1,
            App { boundary, .. } | Pi { boundary, .. } | Lambda { boundary, .. }
            | Let { boundary, .. } | Proj { boundary, .. } => *boundary & 0x0f,
        }
    }

    #[inline]
    pub(crate) fn boundary_app_spine_v119(&self) -> u8 {
        match self {
            App { boundary, .. } | Pi { boundary, .. } | Lambda { boundary, .. }
            | Let { boundary, .. } | Proj { boundary, .. } => *boundary >> 4,
            _ => 0,
        }
    }

"""+anchor
c=replace_once(c,anchor,methods,'boundary methods'); p.write_text(c)

p=Path('src/util.rs'); c=p.read_text()
old="""    pub fn mk_app(&mut self, fun: ExprPtr<'t>, arg: ExprPtr<'t>) -> ExprPtr<'t> {
        let hash = hash64!(APP_HASH, fun, arg);
        let fv_mask = crate::expr::child_mask(fun) | crate::expr::child_mask(arg);
        self.alloc_expr(Expr::App { fun, arg, fv_mask, hash })
    }"""
new="""    pub fn mk_app(&mut self, fun: ExprPtr<'t>, arg: ExprPtr<'t>) -> ExprPtr<'t> {
        let hash = hash64!(APP_HASH, fun, arg);
        let fv_mask = crate::expr::child_mask(fun) | crate::expr::child_mask(arg);
        let depth = 1u8.saturating_add(fun.as_ref().boundary_depth_v119().max(arg.as_ref().boundary_depth_v119())).min(15);
        let app_spine = 1u8.saturating_add(fun.as_ref().boundary_app_spine_v119()).min(15);
        let boundary = crate::expr::pack_boundary_v119(depth, app_spine);
        self.alloc_expr(Expr::App { fun, arg, fv_mask, boundary, hash })
    }"""
c=replace_once(c,old,new,'mk_app')
for label,kind,hashname in [('mk_lambda','Lambda','LAMBDA_HASH'),('mk_pi','Pi','PI_HASH')]:
    old=f"""        let hash = hash64!({hashname}, binder_name, binder_style, binder_type, body);
        let fv_mask = crate::expr::child_mask(binder_type) | crate::expr::body_mask(body);
        self.alloc_expr(Expr::{kind} {{
            binder_name,
            binder_style,
            binder_type,
            body,
            fv_mask,
            hash,
        }})"""
    new=f"""        let hash = hash64!({hashname}, binder_name, binder_style, binder_type, body);
        let fv_mask = crate::expr::child_mask(binder_type) | crate::expr::body_mask(body);
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth_v119().max(body.as_ref().boundary_depth_v119())).min(15);
        let boundary = crate::expr::pack_boundary_v119(depth, 0);
        self.alloc_expr(Expr::{kind} {{
            binder_name,
            binder_style,
            binder_type,
            body,
            fv_mask,
            boundary,
            hash,
        }})"""
    c=replace_once(c,old,new,label)
old="""        let fv_mask =
            crate::expr::child_mask(binder_type) | crate::expr::child_mask(val) | crate::expr::body_mask(body);
        let data = self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep });
        self.alloc_expr(Expr::Let { data, fv_mask, hash })"""
new="""        let fv_mask =
            crate::expr::child_mask(binder_type) | crate::expr::child_mask(val) | crate::expr::body_mask(body);
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth_v119().max(val.as_ref().boundary_depth_v119().max(body.as_ref().boundary_depth_v119()))).min(15);
        let boundary = crate::expr::pack_boundary_v119(depth, 0);
        let data = self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep });
        self.alloc_expr(Expr::Let { data, fv_mask, boundary, hash })"""
c=replace_once(c,old,new,'mk_let')
old="""        let hash = hash64!(PROJ_HASH, ty_name, idx, structure);
        let fv_mask = crate::expr::child_mask(structure);
        self.alloc_expr(Expr::Proj { ty_name, idx, structure, fv_mask, hash })"""
new="""        let hash = hash64!(PROJ_HASH, ty_name, idx, structure);
        let fv_mask = crate::expr::child_mask(structure);
        let depth = 1u8.saturating_add(structure.as_ref().boundary_depth_v119()).min(15);
        let boundary = crate::expr::pack_boundary_v119(depth, 0);
        self.alloc_expr(Expr::Proj { ty_name, idx, structure, fv_mask, boundary, hash })"""
c=replace_once(c,old,new,'mk_proj'); p.write_text(c)

p=Path('src/parser.rs'); c=p.read_text()
old="""        let fv_mask = fun_mask | arg_mask;
        let nlb = fun.num_loose_bvars().max(arg.num_loose_bvars());
        self.push_expr(idx, Expr::App { fun, arg, fv_mask, hash }, nlb, fv_mask);"""
new="""        let fv_mask = fun_mask | arg_mask;
        let nlb = fun.num_loose_bvars().max(arg.num_loose_bvars());
        let depth = 1u8.saturating_add(fun.as_ref().boundary_depth_v119().max(arg.as_ref().boundary_depth_v119())).min(15);
        let app_spine = 1u8.saturating_add(fun.as_ref().boundary_app_spine_v119()).min(15);
        let boundary = crate::expr::pack_boundary_v119(depth, app_spine);
        self.push_expr(idx, Expr::App { fun, arg, fv_mask, boundary, hash }, nlb, fv_mask);"""
c=replace_once(c,old,new,'parser app')
for label,kind,hashname in [('parser lambda','Lambda','LAMBDA_HASH'),('parser pi','Pi','PI_HASH')]:
    old=f"""        let hash = hash64!(crate::expr::{hashname}, binder_name, binder_info, binder_type, body);
        let fv_mask = binder_type_mask | body_mask;
        let nlb = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        self.push_expr(
            idx,
            Expr::{kind} {{ binder_name, binder_style: binder_info, binder_type, body, fv_mask, hash }},"""
    new=f"""        let hash = hash64!(crate::expr::{hashname}, binder_name, binder_info, binder_type, body);
        let fv_mask = binder_type_mask | body_mask;
        let nlb = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth_v119().max(body.as_ref().boundary_depth_v119())).min(15);
        let boundary = crate::expr::pack_boundary_v119(depth, 0);
        self.push_expr(
            idx,
            Expr::{kind} {{ binder_name, binder_style: binder_info, binder_type, body, fv_mask, boundary, hash }},"""
    c=replace_once(c,old,new,label)
old="""        let nlb =
            binder_type.num_loose_bvars().max(val.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1)));
        self.push_expr(
            idx,
            Expr::Let {
                data: self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep }),
                fv_mask,
                hash,"""
new="""        let nlb =
            binder_type.num_loose_bvars().max(val.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1)));
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth_v119().max(val.as_ref().boundary_depth_v119().max(body.as_ref().boundary_depth_v119()))).min(15);
        let boundary = crate::expr::pack_boundary_v119(depth, 0);
        self.push_expr(
            idx,
            Expr::Let {
                data: self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep }),
                fv_mask,
                boundary,
                hash,"""
c=replace_once(c,old,new,'parser let')
old="""        let hash = hash64!(crate::expr::PROJ_HASH, ty_name, proj_idx, structure);
        self.push_expr(
            idx,
            Expr::Proj { ty_name, idx: proj_idx, structure, fv_mask, hash },"""
new="""        let hash = hash64!(crate::expr::PROJ_HASH, ty_name, proj_idx, structure);
        let depth = 1u8.saturating_add(structure.as_ref().boundary_depth_v119()).min(15);
        let boundary = crate::expr::pack_boundary_v119(depth, 0);
        self.push_expr(
            idx,
            Expr::Proj { ty_name, idx: proj_idx, structure, fv_mask, boundary, hash },"""
c=replace_once(c,old,new,'parser proj'); p.write_text(c)

p=Path('src/eval.rs'); c=p.read_text(); anchor='use std::collections::hash_map::Entry;\n'
match_body='\n'.join(arms)
insert=anchor+f"""use std::sync::atomic::{{AtomicU16, Ordering}};

static V119_THRESHOLD_MILLI: AtomicU16 = AtomicU16::new(0);

pub fn configure_v119_policy_from_env() {{
    let threshold = std::env::var("MATHGRAPH_V119_THRESHOLD_MILLI").ok().and_then(|s| s.parse::<u16>().ok()).unwrap_or(0);
    V119_THRESHOLD_MILLI.store(threshold, Ordering::Relaxed);
    eprintln!("V119_POLICY threshold_milli={{}}", threshold);
}}

#[inline] fn v119_k(k:u16)->u8 {{ match k {{ 0..=96=>0,97..=128=>1,129..=192=>2,193..=256=>3,257..=384=>4,385..=512=>5,_=>6 }} }}
#[inline] fn v119_root(e:ExprPtr<'_>)->u8 {{ match e.as_ref() {{ Expr::Var{{..}}=>0,Expr::Sort{{..}}=>1,Expr::Const{{..}}=>2,Expr::App{{..}}=>3,Expr::Pi{{..}}=>4,Expr::Lambda{{..}}=>5,Expr::Let{{..}}=>6,Expr::StringLit{{..}}=>7,Expr::NatLit{{..}}=>8,Expr::Proj{{..}}=>9 }} }}
#[inline] fn v119_mask(n:u32)->u8 {{ match n {{ 0=>0,1..=4=>1,5..=8=>2,9..=16=>3,17..=32=>4,33..=48=>5,_=>6 }} }}
#[inline] fn v119_depth(n:u8)->u8 {{ match n {{ 0..=3=>0,4..=7=>1,8..=11=>2,_=>3 }} }}
#[inline] fn v119_spine(n:u8)->u8 {{ match n {{ 0=>0,1=>1,2..=3=>2,4..=7=>3,_=>4 }} }}
#[inline] fn v119_yield_milli(e:ExprPtr<'_>, k:u16)->u16 {{
    let key=(v119_k(k),v119_root(e),v119_mask(e.as_ref().fv_mask().count_ones()),v119_depth(e.as_ref().boundary_depth_v119()),v119_spine(e.as_ref().boundary_app_spine_v119()));
    match key {{
{match_body}
        _ => 0,
    }}
}}

"""
c=replace_once(c,anchor,insert,'eval imports')
old="""        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
new="""        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let threshold = V119_THRESHOLD_MILLI.load(Ordering::Relaxed);
            if threshold != 0 && v119_yield_milli(e, k) < threshold {
                return env;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
c=replace_once(c,old,new,'key_env'); p.write_text(c)

p=Path('src/main.rs'); c=p.read_text()
old="""fn use_config(config_path: &Path) -> Result<Option<String>, Box<dyn Error>> {
    let cfg = Config::try_from(config_path)?;"""
new="""fn use_config(config_path: &Path) -> Result<Option<String>, Box<dyn Error>> {
    sokonanoda::eval::configure_v119_policy_from_env();
    let cfg = Config::try_from(config_path)?;"""
c=replace_once(c,old,new,'main configure'); p.write_text(c)
print('APPLY_FULL_STATE_SELECTOR_V119=PASS')
