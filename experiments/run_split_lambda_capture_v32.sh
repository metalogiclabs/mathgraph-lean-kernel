#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v32-* /tmp/v32-arena

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v32-arena
(cd /tmp/v32-arena && for t in std cedar; do nix develop -c ./lka.py build-test "$t"; done)

for arm in base split; do git worktree add "/tmp/v32-$arm" "$BASE"; done

# Verified v29 wall-time seed: immediate Pi force collapse.
for arm in base split; do
python3 - "$arm" <<'PY'
from pathlib import Path
import sys
p=Path(f'/tmp/v32-{sys.argv[1]}/src/eval.rs'); s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if matches!(v, Value::Pi { .. }) { return v; }
        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY
done

# Consequence-first representation change: a Lambda no longer captures the union
# environment for both binder type and body. The binder type is stored as a lazy
# thunk with its own minimal environment; the body closure gets body_mask(body).
python3 - <<'PY'
from pathlib import Path
root=Path('/tmp/v32-split')

# Value::Lam keeps the same pointer-width slot: ExprPtr -> V (a lazy binder-domain thunk).
p=root/'src/value.rs'; s=p.read_text()
s=s.replace("        binder_type: ExprPtr<'a>,\n        body: Closure<'a>,", "        binder_type: V<'a>,\n        body: Closure<'a>,", 1)
s=s.replace("            Value::Lam { binder_name, binder_style, binder_type, body, .. } => {\n                let (b, c) = closure_key(body);\n                let h = kmix(\n                    kmix(kmix(11, binder_name.get_hash()), *binder_style as u64),\n                    binder_type.as_ref() as *const crate::expr::Expr<'a> as usize as u64,\n                );\n                seal(kmix(h, b), c)\n            }",
"            Value::Lam { binder_name, binder_style, binder_type, body, .. } => {\n                let (b, c) = closure_key(body);\n                let h = kmix(kmix(kmix(11, binder_name.get_hash()), *binder_style as u64), binder_type.digest());\n                seal(kmix(h, b), c && binder_type.is_closed())\n            }",1)
s=s.replace("    binder_type: ExprPtr<'a>,\n    body: Closure<'a>,\n) -> V<'a> {\n    arena.alloc(Value::Lam", "    binder_type: V<'a>,\n    body: Closure<'a>,\n) -> V<'a> {\n    arena.alloc(Value::Lam",1)
p.write_text(s)

# Lam hash-cons key now keys the semantic binder-domain value by pointer.
p=root/'src/util.rs'; s=p.read_text()
s=s.replace("pub(crate) lam_hc: FxHashMap<(ExprPtr<'t>, usize, ExprPtr<'t>), V<'a>>",
            "pub(crate) lam_hc: FxHashMap<(usize, usize, ExprPtr<'t>), V<'a>>",1)
p.write_text(s)

p=root/'src/eval.rs'; s=p.read_text()
s=s.replace("        binder_type: ExprPtr<'t>,\n        body: Closure<'t>,", "        binder_type: V<'t>,\n        body: Closure<'t>,",1)
s=s.replace("        let key = (binder_type, body.env as *const value::Env<'t> as usize, body.body);",
            "        let key = (binder_type as *const Value<'t> as usize, body.env as *const value::Env<'t> as usize, body.body);",1)

old="""            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } =>
                {
                let ce = self.key_env(env, e);
                value::mk_lam(self.arena, binder_name, binder_style, binder_type, Closure::mk_eval(ce, body))
            }"""
new="""            Expr::Lambda { binder_name, binder_style, binder_type, body, .. } => {
                let bt_env = self.key_env(env, binder_type);
                let bt = value::mk_thunk(self.arena, bt_env, binder_type);
                let bm = crate::expr::body_mask(body);
                let body_env = if body.num_loose_bvars() <= 1 {
                    self.lsub_base(env.lsub())
                } else if body.num_loose_bvars() > 65 {
                    env
                } else {
                    self.prune_env(env, bm)
                };
                value::mk_lam(self.arena, binder_name, binder_style, bt, Closure::mk_eval(body_env, body))
            }"""
assert old in s
s=s.replace(old,new,1)

old="""            Value::Lam { binder_type, body, .. } => {
                let addr = v as *const Value<'t> as usize;
                if let Some(d) = self.tc_cache.lam_domain_cache.get(&addr) {
                    return d;
                }
                let e = body.env;
                let bt = *binder_type;
                let d = self.eval(depth, e, bt);
                self.tc_cache.lam_domain_cache.insert(addr, d);
                d
            }"""
new="""            Value::Lam { binder_type, .. } => {
                let addr = v as *const Value<'t> as usize;
                if let Some(d) = self.tc_cache.lam_domain_cache.get(&addr) { return d; }
                let d = self.force_thunk(depth, binder_type);
                self.tc_cache.lam_domain_cache.insert(addr, d);
                d
            }"""
assert old in s
s=s.replace(old,new,1)

# global_key is another consumer of the Lam binder domain. It must key the
# semantic value now, not pass it to binder_key as if it were an ExprPtr.
old="""            Value::Lam { binder_name, binder_style, binder_type, body, .. } => {
                let h = self.binder_key(11, *binder_name, *binder_style, Some(*binder_type));
                self.closure_key(h, body, depth)
            }"""
new="""            Value::Lam { binder_name, binder_style, binder_type, body, .. } => {
                let h = self.binder_key(11, *binder_name, *binder_style, None);
                let (d, dc) = self.global_key(binder_type, depth)?;
                let (k, cc) = self.closure_key(mix(h, d), body, depth)?;
                Ok((k, dc && cc))
            }"""
assert old in s
s=s.replace(old,new,1)
p.write_text(s)
PY

cat >/tmp/v32-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for arm in base split; do
  (cd "/tmp/v32-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v32-$arm/target/release/sokonanoda" "/tmp/v32-$arm-bin"
done

# Exact differential is mandatory before timing.
for t in std cedar; do
  /tmp/v32-base-bin /tmp/v32-config.json < "/tmp/v32-arena/_build/tests/$t.ndjson" >"/tmp/v32-$t-base.out" 2>"/tmp/v32-$t-base.err"
  /tmp/v32-split-bin /tmp/v32-config.json < "/tmp/v32-arena/_build/tests/$t.ndjson" >"/tmp/v32-$t-split.out" 2>"/tmp/v32-$t-split.err"
  cmp "/tmp/v32-$t-base.out" "/tmp/v32-$t-split.out"
  echo "V32_${t^^}_SEMANTIC_REPLAY=EXACT"
done

# Alternating measurements, 3 each.
for t in std cedar; do
  for arm in base split split base base split; do
    n=$(find /tmp -maxdepth 1 -type f -name "v32-${t}-${arm}-*.time" | wc -l); n=$((n+1))
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v32-${t}-${arm}-${n}.time" "/tmp/v32-$arm-bin" /tmp/v32-config.json < "/tmp/v32-arena/_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v32-${t}-${arm}-${n}.err"
  done
done

python3 - <<'PY' | tee /tmp/v32-decision.txt
from pathlib import Path
import statistics
for t in ['std','cedar']:
  vals={}
  for a in ['base','split']:
    xs=[]
    for p in sorted(Path('/tmp').glob(f'v32-{t}-{a}-*.time')):
      e,u,s,r=p.read_text().split(); xs.append((float(e),float(u)+float(s),int(r)))
    vals[a]=(statistics.median(x[0] for x in xs),statistics.median(x[1] for x in xs),statistics.median(x[2] for x in xs))
    print(f'V32_{t.upper()}_{a.upper()}_WALL_MEDIAN={vals[a][0]:.3f} CPU_MEDIAN={vals[a][1]:.3f} RSS_MEDIAN={vals[a][2]:.0f}')
  d=(vals['split'][0]-vals['base'][0])/vals['base'][0]*100
  print(f'V32_{t.upper()}_SPLIT_VS_BASE_PCT={d:+.3f}')
# mean normalized wall
score=[]
for t in ['std','cedar']:
  def med(a):
    return statistics.median(float(p.read_text().split()[0]) for p in Path('/tmp').glob(f'v32-{t}-{a}-*.time'))
  score.append(med('split')/med('base'))
d=(sum(score)/len(score)-1)*100
print(f'V32_MEAN_NORMALIZED_DELTA={d:+.3f}%')
if d <= -2:
  print('DECISION=V32_ADVANCE_SPLIT_CAPTURE_TO_FULL_MATHLIB_PGO')
elif d < 0:
  print('DECISION=V32_WEAK_POSITIVE__RETAIN_AND_MEASURE_MATHLIB_EXPOSURE')
else:
  print('DECISION=V32_KILL_SPLIT_CAPTURE__THUNK_OR_CAPTURE_TAX_EXCEEDS_DELETION')
print('RULE=LAMBDA_BINDER_TYPE_AND_BODY_KEEP_ONLY_THEIR_OWN_DEPENDENCY_ENVIRONMENTS')
PY
