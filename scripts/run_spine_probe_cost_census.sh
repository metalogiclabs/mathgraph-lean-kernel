#!/usr/bin/env bash
set -euxo pipefail
V2=3d7585c21242f29fdaa48ae9a16e16c6afe42238
rm -rf /tmp/mg-probe-census /tmp/arena-probe

git worktree add /tmp/mg-probe-census "$V2"
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/mg-probe-census/src/conv.rs')
s=p.read_text()
anchor='use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n'
probe=r'''use std::sync::atomic::{AtomicU64, Ordering};
static MG_PP_CALLS: AtomicU64 = AtomicU64::new(0);
static MG_PP_TRUE: AtomicU64 = AtomicU64::new(0);
static MG_PP_FALSE: AtomicU64 = AtomicU64::new(0);
static MG_PP_EXHAUST_CALLS: AtomicU64 = AtomicU64::new(0);
static MG_PP_PAIRS: AtomicU64 = AtomicU64::new(0);
static MG_PP_WORK: AtomicU64 = AtomicU64::new(0);
static MG_PP_TRUE_WORK: AtomicU64 = AtomicU64::new(0);
static MG_PP_FALSE_WORK: AtomicU64 = AtomicU64::new(0);
static MG_PP_PAIR_LE8: AtomicU64 = AtomicU64::new(0);
static MG_PP_PAIR_9_32: AtomicU64 = AtomicU64::new(0);
static MG_PP_PAIR_33_128: AtomicU64 = AtomicU64::new(0);
static MG_PP_PAIR_129_512: AtomicU64 = AtomicU64::new(0);
static MG_PP_PAIR_513_2048: AtomicU64 = AtomicU64::new(0);
static MG_PP_PAIR_EXHAUST: AtomicU64 = AtomicU64::new(0);

#[inline]
fn mg_probe_pair_work(used: u64, exhausted: bool) {
    MG_PP_PAIRS.fetch_add(1, Ordering::Relaxed);
    MG_PP_WORK.fetch_add(used, Ordering::Relaxed);
    if exhausted {
        MG_PP_PAIR_EXHAUST.fetch_add(1, Ordering::Relaxed);
    } else if used <= 8 {
        MG_PP_PAIR_LE8.fetch_add(1, Ordering::Relaxed);
    } else if used <= 32 {
        MG_PP_PAIR_9_32.fetch_add(1, Ordering::Relaxed);
    } else if used <= 128 {
        MG_PP_PAIR_33_128.fetch_add(1, Ordering::Relaxed);
    } else if used <= 512 {
        MG_PP_PAIR_129_512.fetch_add(1, Ordering::Relaxed);
    } else {
        MG_PP_PAIR_513_2048.fetch_add(1, Ordering::Relaxed);
    }
}

pub fn report_spine_probe_cost_census() {
    if std::env::var_os("MATHGRAPH_PROBE_CENSUS").is_none() { return; }
    eprintln!("MG_PROBE calls={} true={} false={} exhaust_calls={} pairs={} work={} true_work={} false_work={} pair_le8={} pair_9_32={} pair_33_128={} pair_129_512={} pair_513_2048={} pair_exhaust={}",
        MG_PP_CALLS.load(Ordering::Relaxed), MG_PP_TRUE.load(Ordering::Relaxed), MG_PP_FALSE.load(Ordering::Relaxed),
        MG_PP_EXHAUST_CALLS.load(Ordering::Relaxed), MG_PP_PAIRS.load(Ordering::Relaxed), MG_PP_WORK.load(Ordering::Relaxed),
        MG_PP_TRUE_WORK.load(Ordering::Relaxed), MG_PP_FALSE_WORK.load(Ordering::Relaxed),
        MG_PP_PAIR_LE8.load(Ordering::Relaxed), MG_PP_PAIR_9_32.load(Ordering::Relaxed), MG_PP_PAIR_33_128.load(Ordering::Relaxed),
        MG_PP_PAIR_129_512.load(Ordering::Relaxed), MG_PP_PAIR_513_2048.load(Ordering::Relaxed), MG_PP_PAIR_EXHAUST.load(Ordering::Relaxed));
}
'''
assert anchor in s
s=s.replace(anchor,anchor+probe,1)
old='''    fn probe_pass(&mut self, depth: u32, pairs: &[(V<'t>, V<'t>)]) -> bool {
        let mut decided = true;
        for (va, vb) in pairs.iter().copied() {
            self.tc_cache.probe_budget = Self::PROBE_CAP;
            self.tc_cache.probe_exhausted = false;
            self.tc_cache.probe_depth = 1;
            let ok = self.unify::<true>(depth, va, vb);
            self.tc_cache.probe_depth = 0;
            if self.tc_cache.probe_exhausted {
                self.tc_cache.conv_cache_neg_probe.clear();
                decided = false;
                continue;
            }
            if !ok {
                return false;
            }
        }
        decided
    }'''
new='''    fn probe_pass(&mut self, depth: u32, pairs: &[(V<'t>, V<'t>)]) -> bool {
        MG_PP_CALLS.fetch_add(1, Ordering::Relaxed);
        let mut decided = true;
        let mut call_work = 0u64;
        let mut call_exhausted = false;
        for (va, vb) in pairs.iter().copied() {
            self.tc_cache.probe_budget = Self::PROBE_CAP;
            self.tc_cache.probe_exhausted = false;
            self.tc_cache.probe_depth = 1;
            let ok = self.unify::<true>(depth, va, vb);
            self.tc_cache.probe_depth = 0;
            let exhausted = self.tc_cache.probe_exhausted;
            let used = (Self::PROBE_CAP - self.tc_cache.probe_budget) as u64;
            call_work += used;
            mg_probe_pair_work(used, exhausted);
            if exhausted {
                self.tc_cache.conv_cache_neg_probe.clear();
                decided = false;
                call_exhausted = true;
                continue;
            }
            if !ok {
                MG_PP_FALSE.fetch_add(1, Ordering::Relaxed);
                MG_PP_FALSE_WORK.fetch_add(call_work, Ordering::Relaxed);
                if call_exhausted { MG_PP_EXHAUST_CALLS.fetch_add(1, Ordering::Relaxed); }
                return false;
            }
        }
        if decided {
            MG_PP_TRUE.fetch_add(1, Ordering::Relaxed);
            MG_PP_TRUE_WORK.fetch_add(call_work, Ordering::Relaxed);
        } else {
            MG_PP_FALSE.fetch_add(1, Ordering::Relaxed);
            MG_PP_FALSE_WORK.fetch_add(call_work, Ordering::Relaxed);
            MG_PP_EXHAUST_CALLS.fetch_add(1, Ordering::Relaxed);
        }
        decided
    }'''
assert old in s
s=s.replace(old,new,1)
p.write_text(s)

p=Path('/tmp/mg-probe-census/src/main.rs')
s=p.read_text()
old='''    // Pretty print as necessary
    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
new='''    sokonanoda::conv::report_spine_probe_cost_census();
    // Pretty print as necessary
    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());'''
assert old in s
p.write_text(s.replace(old,new,1))
PY

cd /tmp/mg-probe-census
cargo test --release --locked
RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp target/release/sokonanoda /tmp/mg-probe-census-bin
cat >/tmp/mg-probe-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/arena-probe
cd /tmp/arena-probe
for t in init-prelude perf/args-before-unfold perf/discarded-argument perf/unroll-versus-evaluate mathlib; do
  nix develop -c ./lka.py build-test "$t"
done

OUT="$GITHUB_WORKSPACE/spine-probe-cost-census.txt"
: > "$OUT"
for t in init-prelude perf/args-before-unfold perf/discarded-argument perf/unroll-versus-evaluate mathlib; do
  echo "MG_TEST $t" | tee -a "$OUT"
  safe=$(echo "$t" | tr '/' '_')
  MATHGRAPH_PROBE_CENSUS=1 /tmp/mg-probe-census-bin /tmp/mg-probe-config.json < "_build/tests/$t.ndjson" >/tmp/${safe}.out 2>/tmp/${safe}.err
  grep '^MG_PROBE' /tmp/${safe}.err | tee -a "$OUT"
done

python3 - "$OUT" <<'PY'
import re,sys
from pathlib import Path
p=Path(sys.argv[1]); rows={}; cur=None
for line in p.read_text().splitlines():
    if line.startswith('MG_TEST '):
        cur=line[8:]; rows[cur]={}
    elif line.startswith('MG_PROBE') and cur:
        rows[cur].update({k:int(v) for k,v in re.findall(r'(\w+)=(\d+)', line)})
print('\nDERIVED')
for t,r in rows.items():
    calls=r.get('calls',0); tr=r.get('true',0); fa=r.get('false',0); work=r.get('work',0); fw=r.get('false_work',0)
    print(f"{t}: calls={calls:,} success={tr/max(calls,1):.2%} failure={fa/max(calls,1):.2%} avg_work={work/max(calls,1):.2f} failed_work_share={fw/max(work,1):.2%}")
PY
