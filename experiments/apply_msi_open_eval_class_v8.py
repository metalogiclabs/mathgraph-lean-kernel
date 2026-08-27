#!/usr/bin/env python3
import pathlib, sys
mode=sys.argv[1]
p=pathlib.Path('src/eval.rs')
s=p.read_text()
old='''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {'''
conds={
'app':'matches!(self.ctx.read_expr_ref(e), Expr::App { .. })',
'app-proj':'matches!(self.ctx.read_expr_ref(e), Expr::App { .. } | Expr::Proj { .. })',
'app-let':'matches!(self.ctx.read_expr_ref(e), Expr::App { .. } | Expr::Let { .. })',
}
if mode not in conds: raise SystemExit(mode)
new=f'''        if {conds[mode]} {{'''
if old not in s: raise SystemExit('anchor not found')
p.write_text(s.replace(old,new,1))
print('applied MSI open-eval class',mode)
