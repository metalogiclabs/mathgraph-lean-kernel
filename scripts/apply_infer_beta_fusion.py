#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / 'src' / 'infer.rs'
s = p.read_text()
needle = '''    fn infer_app_v(\n        &mut self,\n        flag: InferFlag,\n        depth: u32,\n        env: E<'t>,\n        ctx: C<'t>,\n        e: ExprPtr<'t>,\n    ) -> V<'t> {\n        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);\n'''
replacement = '''    fn infer_app_v(\n        &mut self,\n        flag: InferFlag,\n        depth: u32,\n        env: E<'t>,\n        ctx: C<'t>,\n        e: ExprPtr<'t>,\n    ) -> V<'t> {\n        // Fuse the typing rule for an immediately-applied lambda. The generic\n        // path first infers the lambda as a Pi and then consumes that Pi, which\n        // re-infers nested beta-ladder suffixes. Check the binder and argument\n        // once, then infer the body under the actual argument substitution.\n        if let App { fun, arg, .. } = self.ctx.read_expr(e) {\n            if let Lambda { binder_type, body, .. } = self.ctx.read_expr(fun) {\n                let dom = self.arg_value(depth, env, binder_type);\n                if flag == Check {\n                    self.infer_sort_of_v(flag, depth, env, ctx, binder_type);\n                    let arg_ty = self.infer_value(flag, depth, env, ctx, arg);\n                    assert!(self.conv_types_at(depth, dom, arg_ty), "app arg def_eq failed");\n                }\n                let av = self.arg_value(depth, env, arg);\n                let env2 = value::env_extend(self.arena, env, av);\n                let ctx2 = value::ctx_extend(self.arena, ctx, dom);\n                return self.infer_value(flag, depth + 1, env2, ctx2, body);\n            }\n        }\n\n        let (fun, mut args) = self.ctx.unfold_apps_stack(self.arena, e);\n'''
assert needle in s, 'infer_app_v anchor not found'
p.write_text(s.replace(needle, replacement, 1))
print('applied direct infer beta-fusion fast path')
