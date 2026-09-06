#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v81
rm -rf "$ROOT"
mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cp -a "$ROOT/base" "$ROOT/profile"
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'profile'/'src/eval.rs'
s=p.read_text()
anchor="""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {\n        let mut prev = prev_head;\n        for elim in spine.to_vec() {\n"""
old="""                ElimView::App(a) => {\n                    let ty_f = self.force_all(depth, ty);\n"""
assert s.count(anchor)==1, 'spine function anchor changed'
assert s.count(old)==1, 'spine force callsite changed'
profile=r'''
// V81: temporary measurement-only instrumentation, not a kernel optimization.
// Inclusive time is attributed to the callsite; nested work is not additive.
#[derive(Default)]
struct V81Stats { rows: [[u64; 5]; 18] }
impl Drop for V81Stats {
    fn drop(&mut self) {
        for (i, r) in self.rows.iter().enumerate() {
            if r[0] != 0 {
                eprintln!("V81_PROFILE {},{},{},{},{},{}", i, r[0], r[1], r[2], r[3], r[4]);
            }
        }
    }
}
thread_local! {
    static V81_PROFILE: std::cell::RefCell<V81Stats> = std::cell::RefCell::new(V81Stats::default());
}
fn v81_shape(v: V<'_>) -> usize {
    match v {
        Value::Pi { .. } => 0,
        Value::Thunk { .. } => 1,
        Value::Unfold { .. } => 2,
        Value::Rigid { head: RigidHead::Recursor(..) | RigidHead::QuotConst(..), .. } => 3,
        Value::Rigid { .. } => 4,
        Value::Lam { .. } => 5,
        Value::Sort { .. } => 6,
        Value::NatLit { .. } => 7,
        Value::StrLit { .. } => 8,
    }
}
'''
s=s.replace(anchor, """    #[inline(never)]
    fn force_spine_profile_v81(&mut self, depth: u32, v: V<'t>, app_pos: usize) -> V<'t> {
        let bucket = usize::from(app_pos != 0) * 9 + v81_shape(v);
        let start = std::time::Instant::now();
        let result = self.force_all(depth, v);
        let ns = start.elapsed().as_nanos().min(u64::MAX as u128) as u64;
        let changed = !std::ptr::eq(v, result);
        let is_pi = matches!(result, Value::Pi { .. });
        V81_PROFILE.with(|p| {
            let mut p = p.borrow_mut();
            let r = &mut p.rows[bucket];
            r[0] += 1;
            r[1] = r[1].saturating_add(ns);
            r[2] += u64::from(changed);
            r[3] += u64::from(is_pi);
            r[4] = r[4].max(ns);
        });
        result
    }

"""+anchor.replace('        for elim in spine.to_vec() {','        let mut app_pos = 0usize;\n        for elim in spine.to_vec() {'),1)
s=s.replace(old,"""                ElimView::App(a) => {
                    let ty_f = self.force_spine_profile_v81(depth, ty, app_pos);
                    app_pos += 1;
""",1)
s=profile+s
p.write_text(s)
PY
cat >"$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V81_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
build() {
  local arm=$1
  cd "$ROOT/$arm"
  RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q
  cp target/release/sokonanoda "$ROOT/$arm.bin"
}
build base
build profile
printf 'arm,bytes,sha256\n' > "$ROOT/binaries.csv"
for arm in base profile; do
  printf '%s,%s,%s\n' "$arm" "$(stat -c %s "$ROOT/$arm.bin")" "$(sha256sum "$ROOT/$arm.bin" | cut -d' ' -f1)" >> "$ROOT/binaries.csv"
done
printf 'corpus,arm,seconds\n' > "$ROOT/timings.csv"
for corpus in std cedar mathlib; do
  for arm in base profile; do
    /usr/bin/time -f '%e' -o "$ROOT/out/$arm-$corpus.time" \
      "$ROOT/$arm.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" \
      > "$ROOT/out/$arm-$corpus.out" 2> "$ROOT/out/$arm-$corpus.err"
    printf '%s,%s,%s\n' "$corpus" "$arm" "$(cat "$ROOT/out/$arm-$corpus.time")" >> "$ROOT/timings.csv"
  done
  cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/profile-$corpus.out"
  echo "V81_${corpus^^}_REPLAY=EXACT"
done
python3 - "$ROOT" <<'PY'
from pathlib import Path
import csv, json, sys
root=Path(sys.argv[1])
shapes=['Pi','Thunk','Unfold','RigidRecOrQuot','RigidOther','Lam','Sort','NatLit','StrLit']
rows=[]
for corpus in ['std','cedar','mathlib']:
    agg={i:[0]*5 for i in range(18)}
    for line in (root/'out'/f'profile-{corpus}.err').read_text().splitlines():
        if not line.startswith('V81_PROFILE '): continue
        values=[int(x) for x in line.split(' ',1)[1].split(',')]
        bucket,*metrics=values
        a=agg[bucket]
        for j in range(4): a[j]+=metrics[j]
        a[4]=max(a[4],metrics[4])
    assert sum(r[0] for r in agg.values())>0, f'no profile rows for {corpus}'
    total_ns=sum(r[1] for r in agg.values())
    total_calls=sum(r[0] for r in agg.values())
    for i,r in agg.items():
        if not r[0]: continue
        rows.append({'corpus':corpus,'position':'first' if i<9 else 'later','input_shape':shapes[i%9],
            'calls':r[0],'inclusive_ns':r[1],'changed':r[2],'result_pi':r[3],'max_ns':r[4],
            'mean_ns':r[1]/r[0],'time_share_percent':100*r[1]/total_ns})
    print(f'V81_{corpus.upper()}_CALLS={total_calls} INCLUSIVE_NS={total_ns}',flush=True)
    for r in sorted((r for r in rows if r['corpus']==corpus),key=lambda x:-x['inclusive_ns']):
        print('V81_BUCKET '+json.dumps(r,sort_keys=True),flush=True)
with (root/'profile.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(root/'profile.json').write_text(json.dumps({'frozen_base':'08ddb26718c86213262943ca19ae8cf1b03fa922','rows':rows,'scope':'Inclusive callsite timing and shape distribution; no optimization or exclusive reduction-step attribution.'},indent=2)+'\n')
print('DECISION=PROFILE_RECORDED__SELECT_REACHABLE_COSTLY_CASE_NEXT',flush=True)
PY
