#!/usr/bin/env bash
set -euxo pipefail

SOKO=7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0
ROOT=/tmp/v64
rm -rf "$ROOT"
mkdir -p "$ROOT"

git clone https://github.com/intgrah/sokonanoda "$ROOT/incumbent"
git -C "$ROOT/incumbent" checkout "$SOKO"

# Reconstruct promoted incumbent: Pi force fast path + relevance propagation-off.
python3 - "$ROOT/incumbent" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])

p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)

p=root/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))
PY

# Add route counters without changing semantic control flow.
python3 - "$ROOT/incumbent" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/eval.rs'
s=p.read_text()

anchor='use std::collections::hash_map::Entry;\n'
insert='''use std::collections::hash_map::Entry;\nuse std::sync::atomic::{AtomicU64, Ordering::Relaxed};\n\nstatic V64_EVAL_TOTAL: AtomicU64 = AtomicU64::new(0);\nstatic V64_CLOSED_HIT: AtomicU64 = AtomicU64::new(0);\nstatic V64_CLOSED_MISS: AtomicU64 = AtomicU64::new(0);\nstatic V64_OPEN_HIT: AtomicU64 = AtomicU64::new(0);\nstatic V64_OPEN_MISS: AtomicU64 = AtomicU64::new(0);\nstatic V64_APP_NESTED: AtomicU64 = AtomicU64::new(0);\nstatic V64_APP_NESTED_ALL_SAME: AtomicU64 = AtomicU64::new(0);\nstatic V64_APP_NESTED_GENERIC: AtomicU64 = AtomicU64::new(0);\nstatic V64_APP_SIMPLE: AtomicU64 = AtomicU64::new(0);\nstatic V64_APP_SIMPLE_LAM: AtomicU64 = AtomicU64::new(0);\nstatic V64_APP_SIMPLE_NONLAM: AtomicU64 = AtomicU64::new(0);\nstatic V64_VAR: AtomicU64 = AtomicU64::new(0);\nstatic V64_SORT: AtomicU64 = AtomicU64::new(0);\nstatic V64_CONST: AtomicU64 = AtomicU64::new(0);\nstatic V64_LAMBDA: AtomicU64 = AtomicU64::new(0);\nstatic V64_PI: AtomicU64 = AtomicU64::new(0);\nstatic V64_LET: AtomicU64 = AtomicU64::new(0);\nstatic V64_PROJ: AtomicU64 = AtomicU64::new(0);\nstatic V64_NATLIT: AtomicU64 = AtomicU64::new(0);\nstatic V64_STRLIT: AtomicU64 = AtomicU64::new(0);\n\npub fn dump_eval_census() {\n    let total = V64_EVAL_TOTAL.load(Relaxed).max(1);\n    macro_rules! out { ($n:literal, $c:ident) => {{ let v=$c.load(Relaxed); eprintln!(\"V64_{}={} SHARE_PCT={:.6}\", $n, v, 100.0*(v as f64)/(total as f64)); }} }\n    eprintln!(\"V64_EVAL_TOTAL={}\", total);\n    out!(\"CLOSED_HIT\", V64_CLOSED_HIT); out!(\"CLOSED_MISS\", V64_CLOSED_MISS);\n    out!(\"OPEN_HIT\", V64_OPEN_HIT); out!(\"OPEN_MISS\", V64_OPEN_MISS);\n    out!(\"APP_NESTED\", V64_APP_NESTED); out!(\"APP_NESTED_ALL_SAME\", V64_APP_NESTED_ALL_SAME); out!(\"APP_NESTED_GENERIC\", V64_APP_NESTED_GENERIC);\n    out!(\"APP_SIMPLE\", V64_APP_SIMPLE); out!(\"APP_SIMPLE_LAM\", V64_APP_SIMPLE_LAM); out!(\"APP_SIMPLE_NONLAM\", V64_APP_SIMPLE_NONLAM);\n    out!(\"VAR\", V64_VAR); out!(\"SORT\", V64_SORT); out!(\"CONST\", V64_CONST); out!(\"LAMBDA\", V64_LAMBDA); out!(\"PI\", V64_PI); out!(\"LET\", V64_LET); out!(\"PROJ\", V64_PROJ); out!(\"NATLIT\", V64_NATLIT); out!(\"STRLIT\", V64_STRLIT);\n}\n'''
assert s.count(anchor)==1
s=s.replace(anchor,insert,1)

old="""    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {\n        if e.num_loose_bvars() == 0 && env.lsub().is_none() {\n            if let Some(v) = self.tc_cache.closed_eval_cache.get(&e) {\n                return v;\n            }\n            let v = self.eval_no_cache(depth, env, e);"""
new="""    pub(crate) fn eval(&mut self, depth: u32, env: E<'t>, e: ExprPtr<'t>) -> V<'t> {\n        V64_EVAL_TOTAL.fetch_add(1, Relaxed);\n        if e.num_loose_bvars() == 0 && env.lsub().is_none() {\n            if let Some(v) = self.tc_cache.closed_eval_cache.get(&e) {\n                V64_CLOSED_HIT.fetch_add(1, Relaxed);\n                return v;\n            }\n            V64_CLOSED_MISS.fetch_add(1, Relaxed);\n            let v = self.eval_no_cache(depth, env, e);"""
assert s.count(old)==1
s=s.replace(old,new,1)

old="""            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                return v;\n            }\n            let v = self.eval_no_cache(depth, te, e);"""
new="""            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                V64_OPEN_HIT.fetch_add(1, Relaxed);\n                return v;\n            }\n            V64_OPEN_MISS.fetch_add(1, Relaxed);\n            let v = self.eval_no_cache(depth, te, e);"""
assert s.count(old)==1
s=s.replace(old,new,1)

old="""        if let Expr::App { fun, arg, .. } = first {\n            if let &Expr::App { fun: f2, arg: a2, .. } = self.ctx.read_expr_ref(arg) {"""
new="""        if let Expr::App { fun, arg, .. } = first {\n            if let &Expr::App { fun: f2, arg: a2, .. } = self.ctx.read_expr_ref(arg) {\n                V64_APP_NESTED.fetch_add(1, Relaxed);"""
assert s.count(old)==1
s=s.replace(old,new,1)

old="""                if all_same {\n                    let f_val = match self.ctx.read_expr_ref(first_fun) {"""
new="""                if all_same {\n                    V64_APP_NESTED_ALL_SAME.fetch_add(1, Relaxed);\n                    let f_val = match self.ctx.read_expr_ref(first_fun) {"""
assert s.count(old)==1
s=s.replace(old,new,1)

old="""                let mut funs: Vec<ExprPtr<'t>> = Vec::with_capacity(count as usize);"""
new="""                V64_APP_NESTED_GENERIC.fetch_add(1, Relaxed);\n                let mut funs: Vec<ExprPtr<'t>> = Vec::with_capacity(count as usize);"""
assert s.count(old)==1
s=s.replace(old,new,1)

old="""            let f = self.eval(depth, env, fun);\n            let a = self.eval(depth, env, arg);\n            if let Value::Lam { body: clo, .. } = f {"""
new="""            V64_APP_SIMPLE.fetch_add(1, Relaxed);\n            let f = self.eval(depth, env, fun);\n            let a = self.eval(depth, env, arg);\n            if let Value::Lam { body: clo, .. } = f {\n                V64_APP_SIMPLE_LAM.fetch_add(1, Relaxed);"""
assert s.count(old)==1
s=s.replace(old,new,1)

old="""            return self.apply(depth, f, a);"""
new="""            V64_APP_SIMPLE_NONLAM.fetch_add(1, Relaxed);\n            return self.apply(depth, f, a);"""
# first occurrence is the simple-app tail in this source region
assert s.count(old)>=1
s=s.replace(old,new,1)

repls={
"            Expr::Var { dbj_idx, .. } => {":"            Expr::Var { dbj_idx, .. } => { V64_VAR.fetch_add(1, Relaxed);",
"            Expr::Sort { level, .. } => {":"            Expr::Sort { level, .. } => { V64_SORT.fetch_add(1, Relaxed);",
"            Expr::Const { name, levels, .. } => {":"            Expr::Const { name, levels, .. } => { V64_CONST.fetch_add(1, Relaxed);",
"            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>\n                {":"            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>\n                { V64_LAMBDA.fetch_add(1, Relaxed);",
"            Expr::Pi { binder_name, binder_style, binder_type, body, .. } => {":"            Expr::Pi { binder_name, binder_style, binder_type, body, .. } => { V64_PI.fetch_add(1, Relaxed);",
"            Expr::Let { .. } => {":"            Expr::Let { .. } => { V64_LET.fetch_add(1, Relaxed);",
"            Expr::Proj { ty_name, idx, structure, .. } => {":"            Expr::Proj { ty_name, idx, structure, .. } => { V64_PROJ.fetch_add(1, Relaxed);",
"            Expr::NatLit { ptr, .. } => value::mk_natlit(self.arena, ptr),":"            Expr::NatLit { ptr, .. } => { V64_NATLIT.fetch_add(1, Relaxed); value::mk_natlit(self.arena, ptr) },",
"            Expr::StringLit { ptr, .. } => value::mk_strlit(self.arena, ptr),":"            Expr::StringLit { ptr, .. } => { V64_STRLIT.fetch_add(1, Relaxed); value::mk_strlit(self.arena, ptr) },",
}
for a,b in repls.items():
    assert s.count(a)>=1, a
    s=s.replace(a,b,1)
p.write_text(s)

p=root/'src/main.rs'; s=p.read_text()
old='''    // Check the environment\n    export_file.check_all_declars();\n    // Pretty print as necessary'''
new='''    // Check the environment\n    export_file.check_all_declars();\n    sokonanoda::eval::dump_eval_census();\n    // Pretty print as necessary'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY

cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
ARENA=$(git -C "$ROOT/arena" rev-parse HEAD)
echo "V64_ARENA_HEAD=$ARENA"
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t"; done

cd "$ROOT/incumbent"
RUSTFLAGS='-C target-cpu=native' cargo build --release --locked

mkdir -p "$ROOT/out"
for t in std cedar mathlib; do
  ./target/release/sokonanoda "$ROOT/config.json" < "$ROOT/arena/_build/tests/$t.ndjson" > "$ROOT/out/$t.out" 2> "$ROOT/out/$t.census"
  echo "V64_${t^^}_CHECK=PASS"
  grep '^V64_' "$ROOT/out/$t.census" | sed "s/^/V64_${t^^}_/" | tee "$ROOT/out/$t.summary"
done

python3 - <<'PY' | tee "$ROOT/decision.txt"
from pathlib import Path
import re
root=Path('/tmp/v64/out')
for test in ('std','cedar','mathlib'):
    txt=(root/f'{test}.census').read_text()
    vals={}
    shares={}
    for line in txt.splitlines():
        m=re.match(r'V64_([A-Z0-9_]+)=(\d+)(?: SHARE_PCT=([0-9.]+))?$', line)
        if m:
            vals[m.group(1)]=int(m.group(2))
            if m.group(3) is not None: shares[m.group(1)]=float(m.group(3))
    ranked=sorted(shares.items(), key=lambda kv: kv[1], reverse=True)
    print(f'V64_{test.upper()}_TOP_ROUTES={ranked[:8]}')
# Choose next target only from actual measured route shares.
math=(root/'mathlib.census').read_text()
shares={m.group(1):float(m.group(3)) for m in re.finditer(r'^V64_([A-Z0-9_]+)=(\d+) SHARE_PCT=([0-9.]+)$', math, re.M)}
route_candidates=['OPEN_MISS','CLOSED_MISS','APP_NESTED','APP_SIMPLE','LAMBDA','PI','LET','PROJ']
best=max(route_candidates, key=lambda k: shares.get(k,0.0))
print(f'V64_MATHLIB_LARGEST_MEASURED_ROUTE={best}')
print(f'V64_MATHLIB_LARGEST_MEASURED_ROUTE_SHARE_PCT={shares.get(best,0.0):.6f}')
print('DECISION=V64_ROUTE_CENSUS_COMPLETE__TARGET_LARGEST_MEASURED_AVOIDABLE_ROUTE')
print('RULE=MEASURE_PATH_VOLUME_BEFORE_NEXT_SEMANTIC_BYPASS')
PY
