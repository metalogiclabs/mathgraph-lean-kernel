#!/usr/bin/env bash
set -euo pipefail
BASE=08ddb26718c86213262943ca19ae8cf1b03fa922
ARENA=91f376e4baacf2df0c478e7173bccb2a6adac5c5
ROOT=/tmp/v84
rm -rf "$ROOT"
mkdir -p "$ROOT/out"
git clone -q https://github.com/metalogiclabs/mathgraph-lean-kernel "$ROOT/base"
git -C "$ROOT/base" checkout -q "$BASE"
for arm in candidate control; do cp -a "$ROOT/base" "$ROOT/$arm"; done
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
old="""        match self.tc_cache.spine_hc.entry(key) {
            Entry::Occupied(o) => *o.get(),
            Entry::Vacant(slot) => {
                let s = value::spine_snoc(arena, prev, elim);
                let canon = prev.is_canonical()
                    && match elim.view() {
                        ElimView::App(a) => a.is_canonical(),
                        ElimView::Proj { .. } => true,
                    };
                if canon {
                    s.mark_canonical();
                }
                *slot.insert(s)
            }
        }
"""
for arm in ('candidate','control'):
    p=root/arm/'src/eval.rs'
    s=p.read_text()
    assert s.count(old)==1, 'frozen spine_snoc_hc anchor changed'
    # Both arms perform the same preliminary lookup. Only the candidate
    # returns on a hit; the control continues through the original entry.
    probe="""        if let Some(existing) = self.tc_cache.spine_hc.get(&key) {
            #[cfg(v84_count)]
            V84_HITS.with(|n| n.set(n.get() + 1));
"""
    probe += "            return *existing;\n" if arm=='candidate' else "            let _ = existing;\n"
    probe += "        }\n"
    s=s.replace(old,probe+old,1)
    counter="""#[cfg(v84_count)]
thread_local! {
    static V84_HITS: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
    static V84_REPORT: V84Report = const { V84Report };
}
#[cfg(v84_count)]
struct V84Report;
#[cfg(v84_count)]
impl Drop for V84Report {
    fn drop(&mut self) {
        V84_HITS.with(|n| eprintln!("V84_ATTACHMENT_HITS={}", n.get()));
    }
}
"""
    s=s.replace(probe,probe.replace('        if let Some(existing)', '        #[cfg(v84_count)]\n        V84_REPORT.with(|_| {});\n        if let Some(existing)'),1)
    p.write_text(counter+s)
PY
cat > "$ROOT/config.json" <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF
git clone -q https://github.com/leanprover/lean-kernel-arena "$ROOT/arena"
git -C "$ROOT/arena" checkout -q "$ARENA"
echo "V84_BASE=$BASE"
echo "V84_ARENA_HEAD=$(git -C "$ROOT/arena" rev-parse HEAD)"
cd "$ROOT/arena"
for corpus in std cedar mathlib; do nix develop -c ./lka.py build-test "$corpus" >/dev/null; done
build() {
    local arm=$1 suffix=$2 flags=$3
    cd "$ROOT/$arm"
    RUSTFLAGS="-C target-cpu=native $flags" CARGO_TARGET_DIR="$ROOT/target-$arm-$suffix" cargo build --release --locked -q
    cp "$ROOT/target-$arm-$suffix/release/sokonanoda" "$ROOT/$arm-$suffix.bin"
}
for arm in base candidate control; do build "$arm" clean ''; done
for arm in candidate control; do build "$arm" counted '--cfg v84_count'; done
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
xs=[int(x) for x in re.findall(r'V84_ATTACHMENT_HITS=(\d+)',pathlib.Path(sys.argv[1]).read_text())]
assert xs, 'missing attachment counters'
print(sum(xs))
PY
)
        printf '%s,%s,%s\n' "$corpus" "$arm" "$hits" | tee -a "$ROOT/attachment.csv"
        "$ROOT/$arm-clean.bin" "$ROOT/config.json" < "$input" > "$ROOT/out/$arm-$corpus.out"
        cmp "$ROOT/out/base-$corpus.out" "$ROOT/out/$arm-$corpus.out"
    done
    echo "V84_${corpus^^}_ALL_ARMS_REPLAY=EXACT"
done
python3 - "$ROOT" <<'PY'
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1]+'/attachment.csv')))
assert all(int(r['hits'])>0 for r in rows), 'NO_ATTACHMENT'
print('V84_ATTACHMENT=POSITIVE')
PY
# Short screen: full Std and Cedar, then promote only if both are promising.
# The full tournament is always required before a gain can be retained.
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
    geo[arm]=(math.prod(med[c,arm]/med[c,'base'] for c in ['std','cedar','mathlib'])**(1/3)-1)*100
    print(f'{arm} GEOMEAN {geo[arm]:+.3f}%')
if geo['candidate']<=-1 and geo['control']-geo['candidate']>=1:
    print('DECISION=CANDIDATE_GAIN__CONTROL_SEPARATED__REPEAT_BEFORE_RETENTION')
elif geo['candidate']<=-1 and geo['control']<=-1:
    print('DECISION=SHARED_GAIN__CAUSALITY_NOT_ISOLATED')
else:
    print('DECISION=NO_ISOLATED_MATERIAL_GAIN__DO_NOT_RETAIN')
print('SCOPE=FROZEN_THREE_CORPORA__EXPLORATORY_THRESHOLDS_NOT_CONFIDENCE_INTERVALS')
PY
