#!/usr/bin/env bash
set -euo pipefail

BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v91
rm -rf "$ROOT"
mkdir -p "$ROOT/out"

git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
cp -a "$ROOT/base" "$ROOT/probe"

python3 - "$ROOT/probe" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
p=root/'src/eval.rs'
s=p.read_text()
labels=[
 'COLD_TOTAL','START_CONS','START_FRAMED','START_NIL',
 'MASK_1','MASK_2_4','MASK_5_8','MASK_9_16','MASK_17_32','MASK_33_64',
 'END_FRAMED','END_NIL','END_EXHAUSTED',
 'CONS_0','CONS_1','CONS_2_4','CONS_5_8','CONS_9_16','CONS_17_32','CONS_33_PLUS',
 'SLOTS_0','SLOTS_1','SLOTS_2_4','SLOTS_5_8','SLOTS_9_16','SLOTS_17_32','SLOTS_33_PLUS',
 'SAME_RESULT'
]
header='const V91_LABELS: &[&str] = &['+','.join(repr(x) for x in labels).replace("'",'"')+'];\n'
header+=f'''use std::sync::atomic::{{AtomicU64, Ordering::Relaxed}};
static V91: [AtomicU64; {len(labels)}] = [const {{ AtomicU64::new(0) }}; {len(labels)}];
#[inline] fn v91(n: usize) {{ V91[n].fetch_add(1, Relaxed); }}
pub fn dump_v91() {{ for (i,name) in V91_LABELS.iter().enumerate() {{ eprintln!("V91_{{}}={{}}", name, V91[i].load(Relaxed)); }} }}
'''
anchor='use std::collections::hash_map::Entry;\n'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+header,1)

sig="    fn prune_env_cold(&mut self, e: E<'t>, mask: u64, slot: usize) -> E<'t> {"
assert s.count(sig)==1
replacement=sig+'''
        v91(0);
        match e {
            value::Env::Cons { .. } => v91(1),
            value::Env::Framed { .. } => v91(2),
            value::Env::Nil { .. } => v91(3),
        }
        match mask.count_ones() {
            1 => v91(4),
            2..=4 => v91(5),
            5..=8 => v91(6),
            9..=16 => v91(7),
            17..=32 => v91(8),
            _ => v91(9),
        }
        let mut v91_cons_steps = 0u32;
        let mut v91_end_recorded = false;'''
s=s.replace(sig,replacement,1)

old='''                value::Env::Nil { .. } => break,
                value::Env::Framed { mask: fmask, slots, .. } => {'''
new='''                value::Env::Nil { .. } => {
                    v91(11);
                    v91_end_recorded = true;
                    break
                },
                value::Env::Framed { mask: fmask, slots, .. } => {
                    v91(10);
                    v91_end_recorded = true;'''
assert s.count(old)==1
s=s.replace(old,new,1)

old='''                value::Env::Cons { v, parent, .. } => {
                    if rem & 1 != 0 {'''
new='''                value::Env::Cons { v, parent, .. } => {
                    v91_cons_steps += 1;
                    if rem & 1 != 0 {'''
assert s.count(old)==1
s=s.replace(old,new,1)

old='''                    if rem == 0 {
                        break;
                    }
                    consumed += 1;'''
new='''                    if rem == 0 {
                        v91(12);
                        v91_end_recorded = true;
                        break;
                    }
                    consumed += 1;'''
assert s.count(old)==1
s=s.replace(old,new,1)

old='''        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };
        let lsub = e.lsub();'''
new='''        debug_assert!(v91_end_recorded);
        match v91_cons_steps {
            0 => v91(13),
            1 => v91(14),
            2..=4 => v91(15),
            5..=8 => v91(16),
            9..=16 => v91(17),
            17..=32 => v91(18),
            _ => v91(19),
        }
        match n {
            0 => v91(20),
            1 => v91(21),
            2..=4 => v91(22),
            5..=8 => v91(23),
            9..=16 => v91(24),
            17..=32 => v91(25),
            _ => v91(26),
        }
        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };
        let lsub = e.lsub();'''
assert s.count(old)==1
s=s.replace(old,new,1)

old='''        let r = self.intern_frame(hash, out_mask, slots, lsub);
        self.tc_cache.prune_dm[slot] = (e as *const value::Env<'t> as usize, mask, Some(r));'''
new='''        let r = self.intern_frame(hash, out_mask, slots, lsub);
        if std::ptr::eq(r, e) { v91(27); }
        self.tc_cache.prune_dm[slot] = (e as *const value::Env<'t> as usize, mask, Some(r));'''
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)

p=root/'src/main.rs'
s=p.read_text()
old='''    // Check the environment
    export_file.check_all_declars();'''
assert s.count(old)==1
p.write_text(s.replace(old,old+'\n    sokonanoda::eval::dump_v91();',1))
print('V91_INSTRUMENTATION_ANCHORS=PASS')
PY

cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
ACTUAL_ARENA=$(git -C "$ROOT/arena" rev-parse HEAD)
test "$ACTUAL_ARENA" = "$ARENA"
echo "V91_ARENA_PIN=PASS $ACTUAL_ARENA"

cd "$ROOT/arena"
for corpus in std cedar mathlib; do
  nix develop -c ./lka.py build-test "$corpus" >/dev/null
done

for arm in base probe; do
  (cd "$ROOT/$arm" && RUSTFLAGS='-C target-cpu=native' cargo build --release --locked -q && cp target/release/sokonanoda "$ROOT/$arm.bin")
done

for corpus in std cedar mathlib; do
  input="$ROOT/arena/_build/tests/$corpus.ndjson"
  "$ROOT/base.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/base-$corpus.out" 2> "$ROOT/out/base-$corpus.err"
  "$ROOT/probe.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/probe-$corpus.out" 2> "$ROOT/out/probe-$corpus.err"
  cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/probe-$corpus.out"
  grep -v '^V91_' "$ROOT/out/probe-$corpus.err" > "$ROOT/out/probe-$corpus.stripped.err" || true
  cmp "$ROOT/out/base-$corpus.err" "$ROOT/out/probe-$corpus.stripped.err"
  echo "V91_${corpus^^}_EXACT_REPLAY=PASS"
done

python3 - "$ROOT" <<'PY' | tee "$ROOT/summary.txt"
from pathlib import Path
import json,re,sys
r=Path(sys.argv[1])
classes={
 'start':['START_CONS','START_FRAMED','START_NIL'],
 'mask':['MASK_1','MASK_2_4','MASK_5_8','MASK_9_16','MASK_17_32','MASK_33_64'],
 'end':['END_FRAMED','END_NIL','END_EXHAUSTED'],
 'cons':['CONS_0','CONS_1','CONS_2_4','CONS_5_8','CONS_9_16','CONS_17_32','CONS_33_PLUS'],
 'slots':['SLOTS_0','SLOTS_1','SLOTS_2_4','SLOTS_5_8','SLOTS_9_16','SLOTS_17_32','SLOTS_33_PLUS'],
}
out={}
for corpus in ['std','cedar','mathlib']:
    text=(r/'out'/f'probe-{corpus}.err').read_text(errors='replace')
    d={k:int(v) for k,v in re.findall(r'^V91_([A-Z0-9_]+)=(\d+)$',text,re.M)}
    total=d['COLD_TOTAL']
    assert total>0
    for name,keys in classes.items():
        assert sum(d[k] for k in keys)==total,(corpus,name,total,sum(d[k] for k in keys))
    out[corpus]={'counts':d,'fractions':{}}
    for name,keys in classes.items():
        out[corpus]['fractions'][name]={k:d[k]/total for k in keys}
    out[corpus]['same_result_fraction']=d['SAME_RESULT']/total
    print(f'V91_{corpus.upper()}_COLD_TOTAL={total}')
    for name,keys in classes.items():
        best=max(keys,key=lambda k:d[k])
        print(f'V91_{corpus.upper()}_{name.upper()}_DOMINANT={best} {d[best]/total:.6f}')
    print(f'V91_{corpus.upper()}_SAME_RESULT_FRACTION={d["SAME_RESULT"]/total:.6f}')

# A useful separator must be stable across Cedar and Mathlib and cover a substantial
# fraction of cold entries. We do not choose an optimization here; we only name the
# dominant verified class to constrain the next experiment.
def dominant(corpus,axis):
    fs=out[corpus]['fractions'][axis]
    return max(fs,key=fs.get),max(fs.values())
shared=[]
for axis in classes:
    a,fa=dominant('cedar',axis); b,fb=dominant('mathlib',axis)
    if a==b and min(fa,fb)>=0.50:
        shared.append({'axis':axis,'class':a,'min_fraction':min(fa,fb)})
out['shared_majority_separators']=shared
(r/'separator.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
if shared:
    best=max(shared,key=lambda x:x['min_fraction'])
    print('V91_SHARED_MAJORITY_SEPARATOR='+best['axis']+':'+best['class']+f':{best["min_fraction"]:.6f}')
    print('DECISION=SEPARATOR_FOUND__NEXT_EXPERIMENT_MUST_TARGET_THIS_CLASS_ONLY')
else:
    print('DECISION=NO_MAJORITY_SEPARATOR__REFINE_OBSERVATION_GRAMMAR_BEFORE_OPTIMIZING')
PY
