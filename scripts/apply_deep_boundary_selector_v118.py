#!/usr/bin/env python3
from pathlib import Path

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old, new, 1)

# V118 adds one byte of construction-time state (depth + app-spine).
# V117 proved a u32 field still leaves size_of::<Expr>() == 48; u8 therefore
# occupies existing layout slack as well. No semantic hashes include this field.

p = Path("src/expr.rs")
c = p.read_text()

for label, old, new in [
("proj field",
"""        structure: ExprPtr<'a>,
        fv_mask: u64,
    },""",
"""        structure: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u8,
    },"""),
("app field",
"""        fun: ExprPtr<'a>,
        arg: ExprPtr<'a>,
        fv_mask: u64,
    },""",
"""        fun: ExprPtr<'a>,
        arg: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u8,
    },"""),
("pi field",
"""        binder_type: ExprPtr<'a>,
        body: ExprPtr<'a>,
        fv_mask: u64,
    },
    Lambda {""",
"""        binder_type: ExprPtr<'a>,
        body: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u8,
    },
    Lambda {"""),
("lambda field",
"""        binder_type: ExprPtr<'a>,
        body: ExprPtr<'a>,
        fv_mask: u64,
    },
    Let {""",
"""        binder_type: ExprPtr<'a>,
        body: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u8,
    },
    Let {"""),
("let field",
"""        data: &'a LetData<'a>,
        fv_mask: u64,
    },""",
"""        data: &'a LetData<'a>,
        fv_mask: u64,
        boundary: u8,
    },"""),
]:
    c = replace_once(c, old, new, label)

anchor = """pub(crate) fn ignores_binder(body: ExprPtr<'_>) -> bool {
"""
helpers = """#[inline]
pub(crate) fn pack_boundary_v118(depth: u8, app_spine: u8) -> u8 {
    depth.min(15) | (app_spine.min(15) << 4)
}

""" + anchor
c = replace_once(c, anchor, helpers, "boundary helper")

anchor = """    #[inline]
    pub(crate) fn fv_mask(&self) -> u64 {
"""
methods = """    #[inline]
    pub(crate) fn boundary_depth_v118(&self) -> u8 {
        match self {
            Var { .. } | Sort { .. } | Const { .. } | StringLit { .. } | NatLit { .. } => 1,
            App { boundary, .. }
            | Pi { boundary, .. }
            | Lambda { boundary, .. }
            | Let { boundary, .. }
            | Proj { boundary, .. } => *boundary & 0x0f,
        }
    }

    #[inline]
    pub(crate) fn boundary_app_spine_v118(&self) -> u8 {
        match self {
            App { boundary, .. }
            | Pi { boundary, .. }
            | Lambda { boundary, .. }
            | Let { boundary, .. }
            | Proj { boundary, .. } => *boundary >> 4,
            _ => 0,
        }
    }

""" + anchor
c = replace_once(c, anchor, methods, "boundary accessors")
p.write_text(c)

p = Path("src/util.rs")
c = p.read_text()

old = """    pub fn mk_app(&mut self, fun: ExprPtr<'t>, arg: ExprPtr<'t>) -> ExprPtr<'t> {
        let hash = hash64!(APP_HASH, fun, arg);
        let fv_mask = crate::expr::child_mask(fun) | crate::expr::child_mask(arg);
        self.alloc_expr(Expr::App { fun, arg, fv_mask, hash })
    }"""
new = """    pub fn mk_app(&mut self, fun: ExprPtr<'t>, arg: ExprPtr<'t>) -> ExprPtr<'t> {
        let hash = hash64!(APP_HASH, fun, arg);
        let fv_mask = crate::expr::child_mask(fun) | crate::expr::child_mask(arg);
        let depth = 1u8.saturating_add(fun.as_ref().boundary_depth_v118().max(arg.as_ref().boundary_depth_v118())).min(15);
        let app_spine = 1u8.saturating_add(fun.as_ref().boundary_app_spine_v118()).min(15);
        let boundary = crate::expr::pack_boundary_v118(depth, app_spine);
        self.alloc_expr(Expr::App { fun, arg, fv_mask, boundary, hash })
    }"""
c = replace_once(c, old, new, "mk_app")

for label, kind, hashname in [
    ("mk_lambda", "Lambda", "LAMBDA_HASH"),
    ("mk_pi", "Pi", "PI_HASH"),
]:
    old = f"""        let hash = hash64!({hashname}, binder_name, binder_style, binder_type, body);
        let fv_mask = crate::expr::child_mask(binder_type) | crate::expr::body_mask(body);
        self.alloc_expr(Expr::{kind} {{
            binder_name,
            binder_style,
            binder_type,
            body,
            fv_mask,
            hash,
        }})"""
    new = f"""        let hash = hash64!({hashname}, binder_name, binder_style, binder_type, body);
        let fv_mask = crate::expr::child_mask(binder_type) | crate::expr::body_mask(body);
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth_v118().max(body.as_ref().boundary_depth_v118())).min(15);
        let boundary = crate::expr::pack_boundary_v118(depth, 0);
        self.alloc_expr(Expr::{kind} {{
            binder_name,
            binder_style,
            binder_type,
            body,
            fv_mask,
            boundary,
            hash,
        }})"""
    c = replace_once(c, old, new, label)

old = """        let fv_mask =
            crate::expr::child_mask(binder_type) | crate::expr::child_mask(val) | crate::expr::body_mask(body);
        let data = self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep });
        self.alloc_expr(Expr::Let { data, fv_mask, hash })"""
new = """        let fv_mask =
            crate::expr::child_mask(binder_type) | crate::expr::child_mask(val) | crate::expr::body_mask(body);
        let depth = 1u8
            .saturating_add(
                binder_type
                    .as_ref()
                    .boundary_depth_v118()
                    .max(val.as_ref().boundary_depth_v118().max(body.as_ref().boundary_depth_v118())),
            )
            .min(15);
        let boundary = crate::expr::pack_boundary_v118(depth, 0);
        let data = self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep });
        self.alloc_expr(Expr::Let { data, fv_mask, boundary, hash })"""
c = replace_once(c, old, new, "mk_let")

old = """        let hash = hash64!(PROJ_HASH, ty_name, idx, structure);
        let fv_mask = crate::expr::child_mask(structure);
        self.alloc_expr(Expr::Proj { ty_name, idx, structure, fv_mask, hash })"""
new = """        let hash = hash64!(PROJ_HASH, ty_name, idx, structure);
        let fv_mask = crate::expr::child_mask(structure);
        let depth = 1u8.saturating_add(structure.as_ref().boundary_depth_v118()).min(15);
        let boundary = crate::expr::pack_boundary_v118(depth, 0);
        self.alloc_expr(Expr::Proj { ty_name, idx, structure, fv_mask, boundary, hash })"""
c = replace_once(c, old, new, "mk_proj")
p.write_text(c)

# The parser constructs Expr directly, so compose the identical state there.
p = Path("src/parser.rs")
c = p.read_text()

old = """        let fv_mask = fun_mask | arg_mask;
        let nlb = fun.num_loose_bvars().max(arg.num_loose_bvars());
        self.push_expr(idx, Expr::App { fun, arg, fv_mask, hash }, nlb, fv_mask);"""
new = """        let fv_mask = fun_mask | arg_mask;
        let nlb = fun.num_loose_bvars().max(arg.num_loose_bvars());
        let depth = 1u8.saturating_add(fun.as_ref().boundary_depth_v118().max(arg.as_ref().boundary_depth_v118())).min(15);
        let app_spine = 1u8.saturating_add(fun.as_ref().boundary_app_spine_v118()).min(15);
        let boundary = crate::expr::pack_boundary_v118(depth, app_spine);
        self.push_expr(idx, Expr::App { fun, arg, fv_mask, boundary, hash }, nlb, fv_mask);"""
c = replace_once(c, old, new, "parser app")

for label, kind, hashname in [
    ("parser lambda", "Lambda", "LAMBDA_HASH"),
    ("parser pi", "Pi", "PI_HASH"),
]:
    old = f"""        let hash = hash64!(crate::expr::{hashname}, binder_name, binder_info, binder_type, body);
        let fv_mask = binder_type_mask | body_mask;
        let nlb = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        self.push_expr(
            idx,
            Expr::{kind} {{ binder_name, binder_style: binder_info, binder_type, body, fv_mask, hash }},"""
    new = f"""        let hash = hash64!(crate::expr::{hashname}, binder_name, binder_info, binder_type, body);
        let fv_mask = binder_type_mask | body_mask;
        let nlb = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth_v118().max(body.as_ref().boundary_depth_v118())).min(15);
        let boundary = crate::expr::pack_boundary_v118(depth, 0);
        self.push_expr(
            idx,
            Expr::{kind} {{ binder_name, binder_style: binder_info, binder_type, body, fv_mask, boundary, hash }},"""
    c = replace_once(c, old, new, label)

old = """        let nlb =
            binder_type.num_loose_bvars().max(val.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1)));
        self.push_expr(
            idx,
            Expr::Let {
                data: self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep }),
                fv_mask,
                hash,"""
new = """        let nlb =
            binder_type.num_loose_bvars().max(val.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1)));
        let depth = 1u8
            .saturating_add(
                binder_type
                    .as_ref()
                    .boundary_depth_v118()
                    .max(val.as_ref().boundary_depth_v118().max(body.as_ref().boundary_depth_v118())),
            )
            .min(15);
        let boundary = crate::expr::pack_boundary_v118(depth, 0);
        self.push_expr(
            idx,
            Expr::Let {
                data: self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep }),
                fv_mask,
                boundary,
                hash,"""
c = replace_once(c, old, new, "parser let")

old = """        let hash = hash64!(crate::expr::PROJ_HASH, ty_name, proj_idx, structure);
        self.push_expr(
            idx,
            Expr::Proj { ty_name, idx: proj_idx, structure, fv_mask, hash },"""
new = """        let hash = hash64!(crate::expr::PROJ_HASH, ty_name, proj_idx, structure);
        let depth = 1u8.saturating_add(structure.as_ref().boundary_depth_v118()).min(15);
        let boundary = crate::expr::pack_boundary_v118(depth, 0);
        self.push_expr(
            idx,
            Expr::Proj { ty_name, idx: proj_idx, structure, fv_mask, boundary, hash },"""
c = replace_once(c, old, new, "parser proj")
p.write_text(c)

# Causal selector. Scores are frozen from V117 artifact 10325841133
# (sha256:ed23da7d49b89b74715f10eb19d950b37784c865f7f30b6172d67e270b487e59),
# pooling workloads WITHOUT exposing workload identity to the selector.
# Score = 1000 * (saved environment positions / selected dependency positions).
p = Path("src/eval.rs")
c = p.read_text()
anchor = "use std::collections::hash_map::Entry;\n"
insert = anchor + """use std::sync::atomic::{AtomicU16, Ordering};

static V118_THRESHOLD_MILLI: AtomicU16 = AtomicU16::new(0);

pub fn configure_v118_policy_from_env() {
    let threshold = std::env::var("MATHGRAPH_V118_THRESHOLD_MILLI")
        .ok()
        .and_then(|s| s.parse::<u16>().ok())
        .unwrap_or(0);
    V118_THRESHOLD_MILLI.store(threshold, Ordering::Relaxed);
    eprintln!("V118_POLICY threshold_milli={}", threshold);
}

#[inline]
fn v118_depth_bucket(depth: u8) -> usize {
    match depth { 0..=3 => 0, 4..=7 => 1, 8..=11 => 2, _ => 3 }
}

#[inline]
fn v118_spine_bucket(spine: u8) -> usize {
    match spine { 0 => 0, 1 => 1, 2..=3 => 2, 4..=7 => 3, _ => 4 }
}

#[inline]
fn v118_yield_milli(e: ExprPtr<'_>) -> u16 {
    const SCORE: [[u16; 5]; 4] = [
        [343, 12815, 45024, 0, 0],
        [564, 1867, 5426, 720, 0],
        [432, 791, 810, 473, 38],
        [13, 263, 175, 42, 6],
    ];
    SCORE[v118_depth_bucket(e.as_ref().boundary_depth_v118())]
         [v118_spine_bucket(e.as_ref().boundary_app_spine_v118())]
}

"""
c = replace_once(c, anchor, insert, "eval imports")

old = """        if k > 64 {
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
new = """        if k > 64 {
            let threshold = V118_THRESHOLD_MILLI.load(Ordering::Relaxed);
            if threshold != 0 && v118_yield_milli(e) < threshold {
                return env;
            }
            let ck = (env as *const value::Env<'t> as usize, e);
            if let Some(r) = self.tc_cache.wide_prune_cache.get(&ck) {
                return *r;
            }
            let Some(words) = self.exact_wide_uses(e) else { return env };
            let r = self.prune_env_wide(env, &words);
            self.tc_cache.wide_prune_cache.insert(ck, r);
            return r;
        }"""
c = replace_once(c, old, new, "key_env selector")
p.write_text(c)

p = Path("src/main.rs")
c = p.read_text()
old = """fn use_config(config_path: &Path) -> Result<Option<String>, Box<dyn Error>> {
    let cfg = Config::try_from(config_path)?;"""
new = """fn use_config(config_path: &Path) -> Result<Option<String>, Box<dyn Error>> {
    sokonanoda::eval::configure_v118_policy_from_env();
    let cfg = Config::try_from(config_path)?;"""
c = replace_once(c, old, new, "main configure")
p.write_text(c)

print("APPLY_DEEP_BOUNDARY_SELECTOR_V118=PASS")
