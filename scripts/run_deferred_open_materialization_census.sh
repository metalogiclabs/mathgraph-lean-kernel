#!/usr/bin/env bash
set -euxo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/deferred-mat /tmp/arena-deferred /tmp/v2-deferred
mkdir -p /tmp/deferred-mat

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-deferred
cd /tmp/arena-deferred
for t in init std mathlib; do nix develop -c ./lka.py build-test "$t"; done

cd "$GITHUB_WORKSPACE"
git worktree add /tmp/v2-deferred "$V2"
cd /tmp/v2-deferred
python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs')
s=p.read_text()
anchor="pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;"
insert=r'''pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;

// Experiment-only, single-thread census state. The workflow forces num_threads=1.
static mut MAT_CALLS: [u64; 5] = [0; 5];
static mut MAT_HITS: [u64; 5] = [0; 5];
static mut MAT_COLD_HITS: [u64; 5] = [0; 5];
static mut MAT_COLD_MISSES: [u64; 5] = [0; 5];
static mut MAT_COLD_HITS_LE2: [u64; 5] = [0; 5];
static mut MAT_COLD_MISSES_LE2: [u64; 5] = [0; 5];
static mut MAT_LAST_COLD: bool = false;
static mut MAT_LAST_N: usize = 0;

pub(crate) fn dump_open_materialization_census() {
    unsafe {
        let names = ["app", "proj", "let", "pi", "lambda"];
        for i in 0..5 {
            eprintln!("OPEN_MAT class={} calls={} hits={} cold_hits={} cold_misses={} cold_hits_le2={} cold_misses_le2={}",
                names[i], MAT_CALLS[i], MAT_HITS[i], MAT_COLD_HITS[i], MAT_COLD_MISSES[i], MAT_COLD_HITS_LE2[i], MAT_COLD_MISSES_LE2[i]);
        }
    }
}'''
assert anchor in s
s=s.replace(anchor,insert,1)
needle='''        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };'''
repl='''        unsafe { MAT_LAST_COLD = true; MAT_LAST_N = n; }
        let slots: &[V<'t>] = unsafe { std::slice::from_raw_parts(buf.as_ptr().cast::<V<'t>>(), n) };'''
assert needle in s
s=s.replace(needle,repl,1)
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
new='''        if matches!(
            self.ctx.read_expr_ref(e),
            Expr::App { .. } | Expr::Proj { .. } | Expr::Let { .. } | Expr::Pi { .. } | Expr::Lambda { .. }
        ) {
            let ci = match self.ctx.read_expr_ref(e) {
                Expr::App { .. } => 0usize,
                Expr::Proj { .. } => 1,
                Expr::Let { .. } => 2,
                Expr::Pi { .. } => 3,
                Expr::Lambda { .. } => 4,
                _ => unreachable!(),
            };
            unsafe { MAT_CALLS[ci] += 1; MAT_LAST_COLD = false; MAT_LAST_N = 0; }
            let te = self.key_env(env, e);
            let key = (te as *const value::Env<'t> as usize, e);
            if let Some(v) = self.tc_cache.open_eval_cache.get(&key) {
                unsafe {
                    MAT_HITS[ci] += 1;
                    if MAT_LAST_COLD {
                        MAT_COLD_HITS[ci] += 1;
                        if MAT_LAST_N <= 2 { MAT_COLD_HITS_LE2[ci] += 1; }
                    }
                }
                return v;
            }
            unsafe {
                if MAT_LAST_COLD {
                    MAT_COLD_MISSES[ci] += 1;
                    if MAT_LAST_N <= 2 { MAT_COLD_MISSES_LE2[ci] += 1; }
                }
            }
            let v = self.eval_no_cache(depth, te, e);
            self.tc_cache.open_eval_cache.insert(key, v);
            return v;
        }'''
assert old in s
p.write_text(s.replace(old,new,1))

p=Path('src/tc.rs')
s=p.read_text()
old='''        std::thread::scope(|sco| {
            std::thread::Builder::new()
                .stack_size(crate::STACK_SIZE)
                .spawn_scoped(sco, || self.run_session((0, total), || None))
                .unwrap()
                .join()
                .expect("serial checker thread panicked");
        });'''
new='''        std::thread::scope(|sco| {
            std::thread::Builder::new()
                .stack_size(crate::STACK_SIZE)
                .spawn_scoped(sco, || self.run_session((0, total), || None))
                .unwrap()
                .join()
                .expect("serial checker thread panicked");
        });
        crate::eval::dump_open_materialization_census();'''
assert old in s
p.write_text(s.replace(old,new,1))
PY

cargo test --release --locked
cargo build --release --locked
cat >/tmp/deferred-mat/checker.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}
EOF
for t in init std mathlib; do
  target/release/sokonanoda /tmp/deferred-mat/checker.json < /tmp/arena-deferred/_build/tests/$t.ndjson >/tmp/deferred-mat/$t.out 2>/tmp/deferred-mat/$t.err
  grep 'OPEN_MAT' /tmp/deferred-mat/$t.err > /tmp/deferred-mat/$t.census
  cat /tmp/deferred-mat/$t.census
done
python3 - <<'PY' | tee /tmp/deferred-mat/summary.txt
import re
for w in ['init','std','mathlib']:
    rows=[]
    for ln in open(f'/tmp/deferred-mat/{w}.census'):
        d=dict(re.findall(r'(\w+)=([^ ]+)',ln))
        for k in list(d):
            if k!='class': d[k]=int(d[k])
        rows.append(d)
    calls=sum(r['calls'] for r in rows); hits=sum(r['hits'] for r in rows)
    ch=sum(r['cold_hits'] for r in rows); cm=sum(r['cold_misses'] for r in rows)
    chl2=sum(r['cold_hits_le2'] for r in rows)
    print('WORKLOAD',w,'calls',calls,'hits',hits,'cold_hits',ch,'cold_misses',cm)
    print(' hit_rate',hits/calls if calls else 0,'cold_hit_share_of_hits',ch/hits if hits else 0,'cold_hits_le2_share',chl2/ch if ch else 0)
    for r in rows:
        print(' ',r['class'],'hit_rate',r['hits']/r['calls'] if r['calls'] else 0,'cold_hits',r['cold_hits'],'cold_misses',r['cold_misses'])
    if w=='mathlib':
        # A deferred structural-key design can only avoid materialization on cache hits that currently take the cold path.
        avoid=ch
        cold=ch+cm
        print('MATHLIB_DECISION_INPUTS')
        print('avoidable_cold_materializations_if_deferred',avoid)
        print('avoidable_share_of_open_cold',avoid/cold if cold else 0)
        if cold and avoid/cold >= .25:
            print('DECISION=BUILD_DEFERRED_STRUCTURAL_OPEN_CACHE_KEY_AB')
        else:
            print('DECISION=DEFERRED_KEY_CEILING_TOO_SMALL')
PY
