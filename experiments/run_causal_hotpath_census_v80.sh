#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v80
rm -rf "$ROOT" && mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cp -a "$ROOT/base" "$ROOT/probe"
python3 - "$ROOT/probe" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])/'src/eval.rs'
s=p.read_text()
labels=['FORCE_TOTAL','FORCE_PI','FORCE_THUNK','FORCE_UNFOLD','FORCE_IOTA','FORCE_TERMINAL','FORCE_SAME','FORCE_UNCHANGED_AFTER_WORK','STORE_TOTAL','STORE_HIT','STORE_SAME','THUNK_TOTAL','THUNK_HIT','THUNK_MISS','IOTA_REDUCED','IOTA_DESCEND','IOTA_DONE','PRUNE_COLD','KEY_ENV_ZERO','KEY_ENV_LARGE','KEY_ENV_OTHER','FRAME_HIT','FRAME_MISS','EVAL_TOTAL','CLOSED_HIT','CLOSED_MISS','OPEN_HIT','OPEN_MISS','APP_SIMPLE','APP_LAM','APP_NONLAM']
header='''use std::sync::atomic::{AtomicU64, Ordering::Relaxed};
static V80: [AtomicU64; N] = [const { AtomicU64::new(0) }; N];
#[inline] fn v80(n:usize) { V80[n].fetch_add(1,Relaxed); }
pub fn dump_v80() { for (i,name) in LABELS.iter().enumerate() { eprintln!("V80_{}={}",name,V80[i].load(Relaxed)); } }
'''.replace('N]',str(len(labels))+']').replace('; N]',f'; {len(labels)}]').replace('LABELS',str(labels).replace("'",'"'))
# Rust constants are generated from the single ordered counter schema.
header='const V80_LABELS: &[&str] = &['+','.join('"'+x+'"' for x in labels)+'];\n'+header.replace(str(labels).replace("'",'"'),'V80_LABELS')
anchor='use std::collections::hash_map::Entry;\n'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+header,1)
def replace_once(old,new):
    global s
    assert s.count(old)==1,(old,s.count(old))
    s=s.replace(old,new,1)
def wrapper(signature,inner,body):
    global s
    assert s.count(signature)==1,(signature,s.count(signature))
    s=s.replace(signature,signature.replace('fn '+inner+'(', 'fn '+inner+'_inner('),1)
    pos=s.index(signature.replace('fn '+inner+'(', 'fn '+inner+'_inner('))
    s=s[:pos]+signature+'\n'+body+'\n    }\n\n'+s[pos:]
# A wrapper counts the actual result; the original implementation remains intact.
wrapper("    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {",'force_all', '''        v80(0);
        match v { Value::Pi{..}=>v80(1), Value::Thunk{..}=>v80(2), Value::Unfold{..}=>v80(3), Value::Rigid{head:RigidHead::Recursor(..)|RigidHead::QuotConst(..),..}=>v80(4), _=>v80(5) }
        let r=self.force_all_inner(depth,v);
        if std::ptr::eq(r,v) { v80(6); if !matches!(v,Value::Pi{..}) {v80(7);} }
        r''')
wrapper("    #[inline]\n    fn store_lookup(&mut self, depth: u32, v: V<'t>) -> Option<V<'t>> {",'store_lookup', '''        v80(8);
        let r=self.store_lookup_inner(depth,v);
        if let Some(x)=r { v80(9); if std::ptr::eq(x,v) {v80(10);} }
        r''')
wrapper("    #[inline]\n    pub(crate) fn force_thunk(&mut self, depth: u32, v: V<'t>) -> V<'t> {",'force_thunk', '''        if let Value::Thunk{forced,..}=v {v80(11); if forced.get().is_some(){v80(12);}else{v80(13);} }
        self.force_thunk_inner(depth,v)''')
wrapper("    fn iota_step(&mut self, depth: u32, v: V<'t>) -> ForceStep<'t> {",'iota_step', '''        let r=self.iota_step_inner(depth,v);
        match &r {ForceStep::Reduced(_)=>v80(14),ForceStep::Descend(_)=>v80(15),ForceStep::Done=>v80(16)}
        r''')
replace_once("    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {","    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {\n        v80(17);")
replace_once("        if k == 0 {\n            return self.lsub_base(env.lsub());","        if k == 0 {\n            v80(18);\n            return self.lsub_base(env.lsub());")
replace_once("        if k > 64 {\n            return env;","        if k > 64 {\n            v80(19);\n            return env;")
replace_once("        self.prune_env(env, e.as_ref().fv_mask())","        v80(20);\n        self.prune_env(env, e.as_ref().fv_mask())")
# Count actual frame interning outcomes, not merely calls to the helper.
needle='''        }) {
            return e;
        }
        let len = 64 - mask.leading_zeros();'''
replace_once(needle,'''        }) {
            v80(21);
            return e;
        }
        v80(22);
        let len = 64 - mask.leading_zeros();''')
start=s.index("    pub(crate) fn eval(&mut self, depth:")
end=s.index("    fn eval_no_cache",start)
seg=s[start:end]
seg=seg.replace("        if e.num_loose_bvars() == 0", "        v80(23);\n        if e.num_loose_bvars() == 0",1)
seg=seg.replace("if let Some(v) = self.tc_cache.closed_eval_cache.get(&e) {\n                return v;", "if let Some(v) = self.tc_cache.closed_eval_cache.get(&e) {\n                v80(24);\n                return v;",1)
seg=seg.replace("            let v = self.eval_no_cache(depth, env, e);", "            v80(25);\n            let v = self.eval_no_cache(depth, env, e);",1)
seg=seg.replace("if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                return v;", "if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {\n                v80(26);\n                return v;",1)
seg=seg.replace("            let v = self.eval_no_cache(depth, te, e);", "            v80(27);\n            let v = self.eval_no_cache(depth, te, e);",1)
s=s[:start]+seg+s[end:]
start=s.index('    fn eval_no_cache')
end=s.index('    fn const_kind',start)
seg=s[start:end]
old='''            let f = self.eval(depth, env, fun);
            let a = self.eval(depth, env, arg);
            if let Value::Lam { body: clo, .. } = f {'''
assert seg.count(old)==1
seg=seg.replace(old,'''            v80(28);
            let f = self.eval(depth, env, fun);
            let a = self.eval(depth, env, arg);
            if let Value::Lam { body: clo, .. } = f {
                v80(29);''',1)
old='''            return self.apply(depth, f, a);'''
assert seg.count(old)==1
seg=seg.replace(old,'''            v80(30);
            return self.apply(depth, f, a);''',1)
s=s[:start]+seg+s[end:]
p.write_text(s)
p=Path(sys.argv[1])/'src/main.rs';s=p.read_text()
old='''    // Check the environment
    export_file.check_all_declars();'''
assert s.count(old)==1
p.write_text(s.replace(old,old+'\n    sokonanoda::eval::dump_v80();',1))
print('V80_INSTRUMENTATION_ANCHORS=PASS')
PY
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V80_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
for arm in base probe; do (cd "$ROOT/$arm" && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q && cp target/release/sokonanoda "$ROOT/$arm.bin"); done
for corpus in std cedar mathlib; do
  input="$ROOT/arena/_build/tests/$corpus.ndjson"
  "$ROOT/base.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/base-$corpus.out" 2> "$ROOT/out/base-$corpus.err"
  "$ROOT/probe.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/probe-$corpus.out" 2> "$ROOT/out/$corpus.census"
  cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/probe-$corpus.out"
  echo "V80_${corpus^^}_REPLAY=EXACT"
done
python3 - "$ROOT" <<'PY'
import sys,re,json
from pathlib import Path
r=Path(sys.argv[1]); data={}
for c in ['std','cedar','mathlib']:
    text=(r/'out'/f'{c}.census').read_text()
    data[c]={k:int(v) for k,v in re.findall(r'^V80_([A-Z_]+)=(\d+)$',text,re.M)}
    assert data[c]['FORCE_TOTAL']==sum(data[c]['FORCE_'+x] for x in ['PI','THUNK','UNFOLD','IOTA','TERMINAL'])
    assert data[c]['EVAL_TOTAL']>=data[c]['CLOSED_HIT']+data[c]['CLOSED_MISS']+data[c]['OPEN_HIT']+data[c]['OPEN_MISS']
    assert data[c]['APP_SIMPLE']==data[c]['APP_LAM']+data[c]['APP_NONLAM']
    assert data[c]['STORE_HIT']<=data[c]['STORE_TOTAL']
    assert data[c]['FORCE_SAME']<=data[c]['FORCE_TOTAL']
    assert data[c]['THUNK_HIT']+data[c]['THUNK_MISS']==data[c]['THUNK_TOTAL']
    print('V80_'+c.upper()+'_COUNTER_INVARIANTS=PASS')
(r/'census.json').write_text(json.dumps(data,indent=2))
for c,d in data.items():
    for k in ['FORCE_TOTAL','FORCE_PI','FORCE_THUNK','FORCE_UNFOLD','FORCE_IOTA','FORCE_TERMINAL','FORCE_SAME','FORCE_UNCHANGED_AFTER_WORK','STORE_TOTAL','STORE_HIT','THUNK_TOTAL','THUNK_HIT','THUNK_MISS','IOTA_REDUCED','IOTA_DESCEND','PRUNE_COLD','FRAME_HIT','FRAME_MISS','EVAL_TOTAL','OPEN_HIT','OPEN_MISS','APP_SIMPLE']:
        print(f'V80_{c.upper()}_{k}={d[k]}')
print('V80_DECISION=REACHABILITY_CENSUS_COMPLETE__COST_SAMPLING_REQUIRED_BEFORE_REPAIR')
PY
# Sample the unmodified release, not the instrumented binary. Performance
# counters may be unavailable on hosted runners; record that explicitly.
if command -v perf >/dev/null 2>&1; then
  for corpus in std cedar mathlib; do
    perf record -q -F 99 -g --call-graph dwarf,16384 -o "$ROOT/out/$corpus.perf.data" -- "$ROOT/base.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > "$ROOT/out/perf-$corpus.out" 2> "$ROOT/out/perf-$corpus.err" || true
    if [ -s "$ROOT/out/$corpus.perf.data" ]; then
      perf report --stdio --no-children -i "$ROOT/out/$corpus.perf.data" > "$ROOT/out/$corpus.perf.txt" 2> "$ROOT/out/perf-report-$corpus.err" || true
    fi
  done
fi
python3 - "$ROOT" <<'PY' | tee "$ROOT/summary.txt"
import sys,re,json
from pathlib import Path
r=Path(sys.argv[1]); d=json.loads((r/'census.json').read_text())
for c in d:
    p=r/'out'/f'{c}.perf.txt'
    if p.exists() and p.stat().st_size:
        print('V80_'+c.upper()+'_COST_PROFILE=AVAILABLE')
        for line in p.read_text(errors='replace').splitlines():
            if re.search(r'\b(force_all|eval_no_cache|key_env|prune_env|global_key|store_lookup|conv_types|infer_value)\b',line): print('V80_PROFILE_'+c.upper()+' '+line.strip())
    else: print('V80_'+c.upper()+'_COST_PROFILE=UNAVAILABLE')
print('DECISION=RETAIN_REACHABILITY_COUNTS__NO_SPEEDUP_CLAIM__SELECT_REPAIR_ONLY_AFTER_COST_AND_CAUSAL_GATE')
PY
