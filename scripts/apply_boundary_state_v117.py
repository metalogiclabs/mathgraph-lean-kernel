#!/usr/bin/env python3
from pathlib import Path

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 anchor, found {n}")
    return text.replace(old, new, 1)

# expr.rs: add one packed construction-time boundary word to composite expressions.
p = Path("src/expr.rs")
c = p.read_text()

for label, old, new in [
("proj field",
"""        structure: ExprPtr<'a>,
        fv_mask: u64,
    },""",
"""        structure: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u32,
    },"""),
("app field",
"""        fun: ExprPtr<'a>,
        arg: ExprPtr<'a>,
        fv_mask: u64,
    },""",
"""        fun: ExprPtr<'a>,
        arg: ExprPtr<'a>,
        fv_mask: u64,
        boundary: u32,
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
        boundary: u32,
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
        boundary: u32,
    },
    Let {"""),
("let field",
"""        data: &'a LetData<'a>,
        fv_mask: u64,
    },""",
"""        data: &'a LetData<'a>,
        fv_mask: u64,
        boundary: u32,
    },"""),
]:
    c = replace_once(c, old, new, label)

anchor = """#[inline]
pub(crate) fn ignores_binder(body: ExprPtr<'_>) -> bool {
"""
helpers = """#[inline]
pub(crate) fn pack_boundary(loose: u16, var_mass: u8, depth: u8, app_spine: u8) -> u32 {
    u32::from(loose)
        | (u32::from(var_mass) << 16)
        | (u32::from(depth.min(15)) << 24)
        | (u32::from(app_spine.min(15)) << 28)
}

""" + anchor
c = replace_once(c, anchor, helpers, "boundary helper")

old = """        match self {
            Sort { .. } | Const { .. } | StringLit { .. } | NatLit { .. } => 0,
            Var { dbj_idx, .. } => dbj_idx + 1,
            App { fun, arg, .. } => fun.num_loose_bvars().max(arg.num_loose_bvars()),
            Pi { binder_type, body, .. } | Lambda { binder_type, body, .. } =>
                binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1)),
            Let { data, .. } => data
                .binder_type
                .num_loose_bvars()
                .max(data.val.num_loose_bvars().max(data.body.num_loose_bvars().saturating_sub(1))),
            Proj { structure, .. } => structure.num_loose_bvars(),
        }"""
new = """        match self {
            Sort { .. } | Const { .. } | StringLit { .. } | NatLit { .. } => 0,
            Var { dbj_idx, .. } => dbj_idx + 1,
            App { boundary, .. }
            | Pi { boundary, .. }
            | Lambda { boundary, .. }
            | Let { boundary, .. }
            | Proj { boundary, .. } => (*boundary & 0xffff) as u16,
        }"""
c = replace_once(c, old, new, "cached loose accessor")

anchor = """    #[inline]
    pub(crate) fn fv_mask(&self) -> u64 {
"""
methods = """    #[inline]
    pub(crate) fn boundary_var_mass(&self) -> u8 {
        match self {
            Var { .. } => 1,
            Sort { .. } | Const { .. } | StringLit { .. } | NatLit { .. } => 0,
            App { boundary, .. }
            | Pi { boundary, .. }
            | Lambda { boundary, .. }
            | Let { boundary, .. }
            | Proj { boundary, .. } => ((*boundary >> 16) & 0xff) as u8,
        }
    }

    #[inline]
    pub(crate) fn boundary_depth(&self) -> u8 {
        match self {
            Var { .. } | Sort { .. } | Const { .. } | StringLit { .. } | NatLit { .. } => 1,
            App { boundary, .. }
            | Pi { boundary, .. }
            | Lambda { boundary, .. }
            | Let { boundary, .. }
            | Proj { boundary, .. } => ((*boundary >> 24) & 0x0f) as u8,
        }
    }

    #[inline]
    pub(crate) fn boundary_app_spine(&self) -> u8 {
        match self {
            App { boundary, .. }
            | Pi { boundary, .. }
            | Lambda { boundary, .. }
            | Let { boundary, .. }
            | Proj { boundary, .. } => ((*boundary >> 28) & 0x0f) as u8,
            _ => 0,
        }
    }

""" + anchor
c = replace_once(c, anchor, methods, "boundary accessors")
p.write_text(c)

# util.rs: compute the boundary word once, compositionally, at expression construction.
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
        let loose = fun.num_loose_bvars().max(arg.num_loose_bvars());
        let var_mass = fun.as_ref().boundary_var_mass().saturating_add(arg.as_ref().boundary_var_mass());
        let depth = 1u8.saturating_add(fun.as_ref().boundary_depth().max(arg.as_ref().boundary_depth())).min(15);
        let app_spine = 1u8.saturating_add(fun.as_ref().boundary_app_spine()).min(15);
        let boundary = crate::expr::pack_boundary(loose, var_mass, depth, app_spine);
        self.alloc_expr(Expr::App { fun, arg, fv_mask, boundary, hash })
    }"""
c = replace_once(c, old, new, "mk_app")

old = """        let hash = hash64!(LAMBDA_HASH, binder_name, binder_style, binder_type, body);
        let fv_mask = crate::expr::child_mask(binder_type) | crate::expr::body_mask(body);
        self.alloc_expr(Expr::Lambda {
            binder_name,
            binder_style,
            binder_type,
            body,
            fv_mask,
            hash,
        })"""
new = """        let hash = hash64!(LAMBDA_HASH, binder_name, binder_style, binder_type, body);
        let fv_mask = crate::expr::child_mask(binder_type) | crate::expr::body_mask(body);
        let loose = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        let var_mass = binder_type.as_ref().boundary_var_mass().saturating_add(body.as_ref().boundary_var_mass());
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth().max(body.as_ref().boundary_depth())).min(15);
        let boundary = crate::expr::pack_boundary(loose, var_mass, depth, 0);
        self.alloc_expr(Expr::Lambda {
            binder_name,
            binder_style,
            binder_type,
            body,
            fv_mask,
            boundary,
            hash,
        })"""
c = replace_once(c, old, new, "mk_lambda")

old = """        let hash = hash64!(PI_HASH, binder_name, binder_style, binder_type, body);
        let fv_mask = crate::expr::child_mask(binder_type) | crate::expr::body_mask(body);
        self.alloc_expr(Expr::Pi {
            binder_name,
            binder_style,
            binder_type,
            body,
            fv_mask,
            hash,
        })"""
new = """        let hash = hash64!(PI_HASH, binder_name, binder_style, binder_type, body);
        let fv_mask = crate::expr::child_mask(binder_type) | crate::expr::body_mask(body);
        let loose = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        let var_mass = binder_type.as_ref().boundary_var_mass().saturating_add(body.as_ref().boundary_var_mass());
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth().max(body.as_ref().boundary_depth())).min(15);
        let boundary = crate::expr::pack_boundary(loose, var_mass, depth, 0);
        self.alloc_expr(Expr::Pi {
            binder_name,
            binder_style,
            binder_type,
            body,
            fv_mask,
            boundary,
            hash,
        })"""
c = replace_once(c, old, new, "mk_pi")

old = """        let fv_mask =
            crate::expr::child_mask(binder_type) | crate::expr::child_mask(val) | crate::expr::body_mask(body);
        let data = self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep });
        self.alloc_expr(Expr::Let { data, fv_mask, hash })"""
new = """        let fv_mask =
            crate::expr::child_mask(binder_type) | crate::expr::child_mask(val) | crate::expr::body_mask(body);
        let loose = binder_type
            .num_loose_bvars()
            .max(val.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1)));
        let var_mass = binder_type
            .as_ref()
            .boundary_var_mass()
            .saturating_add(val.as_ref().boundary_var_mass())
            .saturating_add(body.as_ref().boundary_var_mass());
        let depth = 1u8
            .saturating_add(
                binder_type
                    .as_ref()
                    .boundary_depth()
                    .max(val.as_ref().boundary_depth().max(body.as_ref().boundary_depth())),
            )
            .min(15);
        let boundary = crate::expr::pack_boundary(loose, var_mass, depth, 0);
        let data = self.arena.alloc(crate::expr::LetData { binder_name, binder_type, val, body, nondep });
        self.alloc_expr(Expr::Let { data, fv_mask, boundary, hash })"""
c = replace_once(c, old, new, "mk_let")

old = """        let hash = hash64!(PROJ_HASH, ty_name, idx, structure);
        let fv_mask = crate::expr::child_mask(structure);
        self.alloc_expr(Expr::Proj { ty_name, idx, structure, fv_mask, hash })"""
new = """        let hash = hash64!(PROJ_HASH, ty_name, idx, structure);
        let fv_mask = crate::expr::child_mask(structure);
        let loose = structure.num_loose_bvars();
        let var_mass = structure.as_ref().boundary_var_mass();
        let depth = 1u8.saturating_add(structure.as_ref().boundary_depth()).min(15);
        let boundary = crate::expr::pack_boundary(loose, var_mass, depth, 0);
        self.alloc_expr(Expr::Proj { ty_name, idx, structure, fv_mask, boundary, hash })"""
c = replace_once(c, old, new, "mk_proj")

p.write_text(c)

# parser.rs: the export parser constructs expressions directly rather than
# through TcCtx::mk_*; compose the same boundary state there.
p = Path("src/parser.rs")
c = p.read_text()

old = """        let fv_mask = fun_mask | arg_mask;
        let nlb = fun.num_loose_bvars().max(arg.num_loose_bvars());
        self.push_expr(idx, Expr::App { fun, arg, fv_mask, hash }, nlb, fv_mask);"""
new = """        let fv_mask = fun_mask | arg_mask;
        let nlb = fun.num_loose_bvars().max(arg.num_loose_bvars());
        let var_mass = fun.as_ref().boundary_var_mass().saturating_add(arg.as_ref().boundary_var_mass());
        let depth = 1u8.saturating_add(fun.as_ref().boundary_depth().max(arg.as_ref().boundary_depth())).min(15);
        let app_spine = 1u8.saturating_add(fun.as_ref().boundary_app_spine()).min(15);
        let boundary = crate::expr::pack_boundary(nlb, var_mass, depth, app_spine);
        self.push_expr(idx, Expr::App { fun, arg, fv_mask, boundary, hash }, nlb, fv_mask);"""
c = replace_once(c, old, new, "parser app")

old = """        let fv_mask = binder_type_mask | body_mask;
        let nlb = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        self.push_expr(
            idx,
            Expr::Lambda { binder_name, binder_style: binder_info, binder_type, body, fv_mask, hash },"""
new = """        let fv_mask = binder_type_mask | body_mask;
        let nlb = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        let var_mass = binder_type.as_ref().boundary_var_mass().saturating_add(body.as_ref().boundary_var_mass());
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth().max(body.as_ref().boundary_depth())).min(15);
        let boundary = crate::expr::pack_boundary(nlb, var_mass, depth, 0);
        self.push_expr(
            idx,
            Expr::Lambda { binder_name, binder_style: binder_info, binder_type, body, fv_mask, boundary, hash },"""
c = replace_once(c, old, new, "parser lambda")

old = """        let fv_mask = binder_type_mask | body_mask;
        let nlb = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        self.push_expr(
            idx,
            Expr::Pi { binder_name, binder_style: binder_info, binder_type, body, fv_mask, hash },"""
new = """        let fv_mask = binder_type_mask | body_mask;
        let nlb = binder_type.num_loose_bvars().max(body.num_loose_bvars().saturating_sub(1));
        let var_mass = binder_type.as_ref().boundary_var_mass().saturating_add(body.as_ref().boundary_var_mass());
        let depth = 1u8.saturating_add(binder_type.as_ref().boundary_depth().max(body.as_ref().boundary_depth())).min(15);
        let boundary = crate::expr::pack_boundary(nlb, var_mass, depth, 0);
        self.push_expr(
            idx,
            Expr::Pi { binder_name, binder_style: binder_info, binder_type, body, fv_mask, boundary, hash },"""
c = replace_once(c, old, new, "parser pi")

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
        let var_mass = binder_type
            .as_ref()
            .boundary_var_mass()
            .saturating_add(val.as_ref().boundary_var_mass())
            .saturating_add(body.as_ref().boundary_var_mass());
        let depth = 1u8
            .saturating_add(
                binder_type
                    .as_ref()
                    .boundary_depth()
                    .max(val.as_ref().boundary_depth().max(body.as_ref().boundary_depth())),
            )
            .min(15);
        let boundary = crate::expr::pack_boundary(nlb, var_mass, depth, 0);
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
            Expr::Proj { ty_name, idx: proj_idx, structure, fv_mask, hash },
            structure.num_loose_bvars(),"""
new = """        let hash = hash64!(crate::expr::PROJ_HASH, ty_name, proj_idx, structure);
        let nlb = structure.num_loose_bvars();
        let var_mass = structure.as_ref().boundary_var_mass();
        let depth = 1u8.saturating_add(structure.as_ref().boundary_depth()).min(15);
        let boundary = crate::expr::pack_boundary(nlb, var_mass, depth, 0);
        self.push_expr(
            idx,
            Expr::Proj { ty_name, idx: proj_idx, structure, fv_mask, boundary, hash },
            nlb,"""
c = replace_once(c, old, new, "parser proj")

p.write_text(c)
print("APPLY_BOUNDARY_STATE_V117=PASS")