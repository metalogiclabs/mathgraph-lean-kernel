#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v31-* /tmp/v31-arena

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v31-arena
(cd /tmp/v31-arena && for t in std cedar; do nix develop -c ./lka.py build-test "$t"; done)

for arm in base pi app piapp; do
  git worktree add "/tmp/v31-$arm" "$BASE"
done

# Pi-only is the verified v29 wall-time seed. Apply it to every arm.
for arm in base pi app piapp; do
python3 - "$arm" <<'PY'
from pathlib import Path
import sys
arm=sys.argv[1]
p=Path(f'/tmp/v31-{arm}/src/eval.rs')
s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY
done

# Candidate arms add a collision-safe <=2-dependency pre-hit cache. It is only a
# front-door proof of an existing open_eval_cache hit: misses fall through to the
# unchanged key_env -> materialized Frame -> open_eval_cache path.
for arm in pi app piapp; do
python3 - "$arm" <<'PY'
from pathlib import Path
import sys
arm=sys.argv[1]
want_pi=arm in ('pi','piapp')
want_app=arm in ('app','piapp')

u=Path(f'/tmp/v31-{arm}/src/util.rs')
s=u.read_text()
old="""    pub(crate) open_eval_cache: FxHashMap<(usize, ExprPtr<'t>), V<'a>>,\n    pub(crate) open_eval_seen: FxHashSet<ExprPtr<'t>>,"""
new="""    pub(crate) open_eval_cache: FxHashMap<(usize, ExprPtr<'t>), V<'a>>,\n    pub(crate) open_prehit2: FxHashMap<(ExprPtr<'t>, usize, u64, usize, usize), V<'a>>,\n    pub(crate) open_eval_seen: FxHashSet<ExprPtr<'t>>,"""
assert old in s; s=s.replace(old,new,1)
old="""            open_eval_cache: session_fx_hash_map(),\n            open_eval_seen: small_fx_hash_set(),"""
new="""            open_eval_cache: session_fx_hash_map(),\n            open_prehit2: session_fx_hash_map(),\n            open_eval_seen: small_fx_hash_set(),"""
assert old in s; s=s.replace(old,new,1)
s=s.replace("        self.open_eval_cache.clear();\n        self.open_eval_seen.clear();",
            "        self.open_eval_cache.clear();\n        self.open_prehit2.clear();\n        self.open_eval_seen.clear();")
s=s.replace("        shrink_map(&mut self.open_eval_cache);\n", "        shrink_map(&mut self.open_eval_cache);\n        shrink_map(&mut self.open_prehit2);\n")
u.write_text(s)

p=Path(f'/tmp/v31-{arm}/src/eval.rs')
s=p.read_text()
old='''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                return v;
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }'''
mode = ("matches!(self.ctx.read_expr_ref(e), Expr::Pi { .. })" if want_pi and not want_app else
        "matches!(self.ctx.read_expr_ref(e), Expr::App { .. })" if want_app and not want_pi else
        "matches!(self.ctx.read_expr_ref(e), Expr::Pi { .. } | Expr::App { .. })")
new=f'''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App {{ .. }} | Expr::Proj {{ .. }} | Expr::Let {{ .. }} | Expr::Pi {{ .. }} | Expr::Lambda {{ .. }}
        ) {{
            let prehit_enabled = {mode};
            let mask = e.as_ref().fv_mask();
            let prekey = if prehit_enabled && e.num_loose_bvars() <= 64 && mask.count_ones() <= 2 {{
                let mut bits = mask;
                let mut a = 0usize;
                let mut b = 0usize;
                if bits != 0 {{
                    let i = bits.trailing_zeros() as u16; bits &= bits - 1;
                    a = env.lookup(i).expect("v31 prehit dependency") as *const Value<'t> as usize;
                }}
                if bits != 0 {{
                    let i = bits.trailing_zeros() as u16;
                    b = env.lookup(i).expect("v31 prehit dependency") as *const Value<'t> as usize;
                }}
                let ls = env.lsub().map_or(0usize, |x| x as *const value::LevelSub<'t> as usize);
                Some((e, ls, mask, a, b))
            }} else {{ None }};
            if let Some(pk) = prekey {{
                if let Some(v) = self.tc_cache.open_prehit2.get(&pk) {{ return v; }}
            }}
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {{
                if let Some(pk) = prekey {{ self.tc_cache.open_prehit2.insert(pk, v); }}
                return v;
            }}
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            if let Some(pk) = prekey {{ self.tc_cache.open_prehit2.insert(pk, v); }}
            return v;
        }}'''
assert old in s
p.write_text(s.replace(old,new,1))
PY
done

cat >/tmp/v31-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

for arm in base pi app piapp; do
  (cd "/tmp/v31-$arm" && cargo test --release --locked && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked)
  cp "/tmp/v31-$arm/target/release/sokonanoda" "/tmp/v31-$arm-bin"
done

# Correctness differential first. Baseline output is oracle for this experiment.
for t in std cedar; do
  /tmp/v31-base-bin /tmp/v31-config.json < "/tmp/v31-arena/_build/tests/$t.ndjson" >"/tmp/v31-$t-base.out" 2>"/tmp/v31-$t-base.err"
  for arm in pi app piapp; do
    "/tmp/v31-$arm-bin" /tmp/v31-config.json < "/tmp/v31-arena/_build/tests/$t.ndjson" >"/tmp/v31-$t-$arm.out" 2>"/tmp/v31-$t-$arm.err"
    cmp "/tmp/v31-$t-base.out" "/tmp/v31-$t-$arm.out"
    echo "V31_${t^^}_${arm^^}_SEMANTIC_REPLAY=EXACT"
  done
done

# Alternating wall measurements to reduce order bias.
for t in std cedar; do
  for arm in base pi app piapp piapp app pi base; do
    n=$(find /tmp -maxdepth 1 -type f -name "v31-${t}-${arm}-*.time" | wc -l); n=$((n+1))
    /usr/bin/time -f '%e %U %S %M' -o "/tmp/v31-${t}-${arm}-${n}.time" "/tmp/v31-$arm-bin" /tmp/v31-config.json < "/tmp/v31-arena/_build/tests/$t.ndjson" >/dev/null 2>"/tmp/v31-${t}-${arm}-${n}.err"
  done
done

python3 - <<'PY' | tee /tmp/v31-decision.txt
from pathlib import Path
import statistics
arms=['base','pi','app','piapp']; tests=['std','cedar']
def vals(t,a):
  xs=[]
  for p in sorted(Path('/tmp').glob(f'v31-{t}-{a}-*.time')):
    e,u,s,r=p.read_text().split(); xs.append((float(e),float(u)+float(s),int(r)))
  return xs
med={}
for t in tests:
  print('V31_WORKLOAD='+t)
  for a in arms:
    x=vals(t,a); w=statistics.median(z[0] for z in x); c=statistics.median(z[1] for z in x)
    med[t,a]=w
    print(f'V31_{t.upper()}_{a.upper()}_WALL_MEDIAN={w:.3f} CPU_MEDIAN={c:.3f}')
  b=med[t,'base']
  for a in arms[1:]: print(f'V31_{t.upper()}_{a.upper()}_VS_BASE_PCT={(med[t,a]-b)/b*100:+.3f}')
score={a:sum(med[t,a]/med[t,'base'] for t in tests)/len(tests) for a in arms[1:]}
w=min(score,key=score.get)
print('V31_TOURNAMENT_WINNER='+w.upper())
print(f'V31_WINNER_MEAN_NORMALIZED_DELTA={(score[w]-1)*100:+.3f}%')
if score[w] <= .98:
  print('DECISION=V31_ADVANCE_WINNER_TO_FULL_MATHLIB_PGO_GATE')
elif score[w] < 1:
  print('DECISION=V31_WEAK_POSITIVE__RETAIN_BUT_SEEK_LARGER_CONSEQUENCE')
else:
  print('DECISION=V31_KILL_PREHIT_FAMILY__REPRESENTATION_TAX_EXCEEDS_AVOIDED_PROJECTION')
print('RULE=PREHIT_ONLY_PROVES_EXISTING_CACHE_RESULT__MISS_PATH_UNCHANGED')
PY
