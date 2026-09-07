#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ROOT=/tmp/v82
rm -rf "$ROOT"
mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
for arm in candidate control; do cp -a "$ROOT/base" "$ROOT/$arm"; done
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
anchor="""    fn spine_type_with_value(&mut self, depth: u32, mut ty: V<'t>, prev_head: V<'t>, spine: S<'t>) -> V<'t> {
        let mut prev = prev_head;
        for elim in spine.to_vec() {
"""
old="""                ElimView::App(a) => {
                    let ty_f = self.force_all(depth, ty);
"""
for arm in ('candidate','control'):
    p=root/arm/'src/eval.rs'
    s=p.read_text()
    assert s.count(anchor)==1 and s.count(old)==1, 'frozen source anchor changed'
    helper="""    // V82: only an already-cached Pi is eligible. No new reduction rule.
    #[inline]
    fn force_spine_cached_pi_v82(&mut self, depth: u32, v: V<'t>) -> V<'t> {
        if let Value::Unfold { forced, .. } = v {
            if let Some(cached) = forced.get() {
                if matches!(cached, Value::Pi { .. }) {
                    #[cfg(v82_count)]
                    V82_HITS.with(|hits| hits.fetch_add(1, std::sync::atomic::Ordering::Relaxed));
"""
    if arm=='candidate':
        helper+='                    return cached;\n'
    else:
        helper+='                    return self.force_all(depth, v);\n'
    helper+="""                }
            }
        }
        self.force_all(depth, v)
    }

"""
    s=s.replace(anchor,helper+anchor,1)
    s=s.replace(old,old.replace('self.force_all(depth, ty)','self.force_spine_cached_pi_v82(depth, ty)'),1)
    counter="""#[cfg(v82_count)]
thread_local! {
    static V82_HITS: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
    static V82_REPORT: V82Report = const { V82Report };
}
#[cfg(v82_count)]
struct V82Report;
#[cfg(v82_count)]
impl Drop for V82Report {
    fn drop(&mut self) {
        V82_HITS.with(|hits| eprintln!("V82_ATTACHMENT_HITS={}", hits.load(std::sync::atomic::Ordering::Relaxed)));
    }
}
"""
    # Initialize the reporting guard on the actual execution thread.
    helper_call='''                    #[cfg(v82_count)]
                    V82_REPORT.with(|_| {});
'''
    s=s.replace('                    #[cfg(v82_count)]\n                    V82_HITS.with',helper_call+'                    #[cfg(v82_count)]\n                    V82_HITS.with',1)
    p.write_text(counter+s)
PY
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q --depth 1 https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
echo V82_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)
cd "$ROOT/arena"
for t in std cedar mathlib; do nix develop -c ./lka.py build-test "$t" >/dev/null; done
build() {
    local arm=$1 suffix=$2 flags=$3
    cd "$ROOT/$arm"
    RUSTFLAGS="-C target-cpu=native $flags" CARGO_TARGET_DIR="$ROOT/target-$arm-$suffix" cargo build --release --locked -q
    cp "$ROOT/target-$arm-$suffix/release/sokonanoda" "$ROOT/$arm-$suffix.bin"
}
for arm in base candidate control; do build "$arm" clean ''; done
for arm in candidate control; do build "$arm" counted '--cfg v82_count'; done
printf 'arm,bytes,sha256\n' > "$ROOT/binaries.csv"
for arm in base candidate control; do
    printf '%s,%s,%s\n' "$arm" "$(stat -c %s "$ROOT/$arm-clean.bin")" "$(sha256sum "$ROOT/$arm-clean.bin" | cut -d' ' -f1)" >> "$ROOT/binaries.csv"
done
printf 'corpus,arm,hits\n' > "$ROOT/attachment.csv"
for corpus in std cedar mathlib; do
    input="$ROOT/arena/_build/tests/$corpus.ndjson"
    "$ROOT/base-clean.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/base-$corpus.out"
    for arm in candidate control; do
        "$ROOT/$arm-counted.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/$arm-counted-$corpus.out" 2> "$ROOT/out/$arm-counted-$corpus.err"
        cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/$arm-counted-$corpus.out"
        hits=$(python3 - "$ROOT/out/$arm-counted-$corpus.err" <<'PY'
import pathlib,re,sys
text=pathlib.Path(sys.argv[1]).read_text()
xs=[int(x) for x in re.findall(r'V82_ATTACHMENT_HITS=(\d+)',text)]
assert xs, 'missing attachment counters'
print(sum(xs))
PY
)
        printf '%s,%s,%s\n' "$corpus" "$arm" "$hits" | tee -a "$ROOT/attachment.csv"
    done
    for arm in candidate control; do
        "$ROOT/$arm-clean.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/$arm-$corpus.out"
        cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/$arm-$corpus.out"
    done
    echo "V82_${corpus^^}_ALL_ARMS_REPLAY=EXACT"
done
python3 - "$ROOT" <<'PY'
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1]+'/attachment.csv')))
assert sum(int(r['hits']) for r in rows if r['arm']=='candidate')>0, 'NO_ATTACHMENT: candidate shortcut never reached'
print('V82_ATTACHMENT=POSITIVE')
PY
printf 'pass,corpus,arm,seconds\n' > "$ROOT/timings.csv"
arms=(base candidate control)
for pass in 1 2 3 4 5; do
    shift=$(( (pass-1) % 3 ))
    order=( ${arms[@]:$shift} ${arms[@]:0:$shift} )
    for corpus in std cedar mathlib; do
        for arm in "${order[@]}"; do
            sec=$({ /usr/bin/time -f '%e' "$ROOT/$arm-clean.bin" "$ROOT/config.json" < "$ROOT/arena/_build/tests/$corpus.ndjson" > /dev/null; } 2>&1 | tail -n1)
            printf '%s,%s,%s,%s\n' "$pass" "$corpus" "$arm" "$sec" | tee -a "$ROOT/timings.csv"
        done
    done
done
python3 - "$ROOT" <<'PY' | tee "$ROOT/summary.txt"
import csv,math,statistics,sys
from pathlib import Path
root=Path(sys.argv[1]); rows=list(csv.DictReader(open(root/'timings.csv')))
med={}
for corpus in ['std','cedar','mathlib']:
    for arm in ['base','candidate','control']:
        xs=[float(r['seconds']) for r in rows if r['corpus']==corpus and r['arm']==arm]
        assert len(xs)==5
        med[corpus,arm]=statistics.median(xs)
    print('MEDIAN',corpus,*(f'{a}={med[corpus,a]:.3f}' for a in ['base','candidate','control']))
geo={}
for arm in ['candidate','control']:
    ratios=[med[c,arm]/med[c,'base'] for c in ['std','cedar','mathlib']]
    geo[arm]=(math.prod(ratios)**(1/3)-1)*100
    print(f'{arm} GEOMEAN {geo[arm]:+.3f}%')
if geo['candidate']<=-1 and geo['control']-geo['candidate']>=1:
    print('DECISION=CANDIDATE_GAIN__CONTROL_SEPARATED__REPEAT_BEFORE_RETENTION')
elif geo['candidate']<=-1 and geo['control']<=-1:
    print('DECISION=SHARED_GAIN__SPECIALIZATION_CAUSALITY_NOT_ISOLATED')
else:
    print('DECISION=NO_ISOLATED_MATERIAL_GAIN__DO_NOT_RETAIN')
print('SCOPE=FROZEN_THREE_CORPORA__EXPLORATORY_THRESHOLDS_NOT_CONFIDENCE_INTERVALS')
PY
