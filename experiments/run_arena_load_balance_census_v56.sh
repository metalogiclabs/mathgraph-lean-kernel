#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
rm -rf /tmp/v56-*

for c in 64 128; do
  git worktree add "/tmp/v56-$c" "$BASE"
  python3 - "$c" "/tmp/v56-$c" <<'PY'
from pathlib import Path
import sys
c=sys.argv[1]; root=Path(sys.argv[2])
# Verified semantic incumbent: Pi-only + relevance propagation-off.
p=root/'src/eval.rs'; s=p.read_text()
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"""
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
p=root/'src/relevance.rs'; s=p.read_text()
old='''                for k in (0..n).rev() {\n                    let Some(s) = dom[k] else { break };\n                    let im = self.ctx.imax(s, r);\n                    r = self.ctx.simplify(im);\n                    result_known |= 1u64 << k;\n                    if self.ctx.is_zero(r) {\n                        prop_result |= 1u64 << k;\n                    }\n                }'''
assert s.count(old)==1
p.write_text(s.replace(old,'                let _ = r;',1))

p=root/'src/tc.rs'; s=p.read_text()
assert s.count('const CHUNK_SIZE: usize = 64;')==1
s=s.replace('const CHUNK_SIZE: usize = 64;',f'const CHUNK_SIZE: usize = {c};',1)
old='''            for i in 0..num_threads {\n                handles.push(\n                    thread::Builder::new()\n                        .name(format!("thread_{}", i))\n                        .stack_size(crate::STACK_SIZE)\n                        .spawn_scoped(sco, || {\n                            if let Some(first) = claim() {\n                                self.run_session(first, claim);\n                            }\n                        })\n                        .unwrap(),\n                )\n            }'''
new='''            for i in 0..num_threads {\n                let claim_ref = &claim;\n                handles.push(\n                    thread::Builder::new()\n                        .name(format!("thread_{}", i))\n                        .stack_size(crate::STACK_SIZE)\n                        .spawn_scoped(sco, move || {\n                            let started = std::time::Instant::now();\n                            let mut chunks = 0usize;\n                            let mut decls = 0usize;\n                            if let Some(first) = claim_ref() {\n                                chunks += 1;\n                                decls += first.1 - first.0;\n                                let mut tracked_claim = || {\n                                    let r = claim_ref();\n                                    if let Some((a, b)) = r {\n                                        chunks += 1;\n                                        decls += b - a;\n                                    }\n                                    r\n                                };\n                                self.run_session(first, &mut tracked_claim);\n                            }\n                            eprintln!(\n                                "V56_THREAD chunk={} thread={} chunks={} decls={} elapsed_us={}",\n                                CHUNK_SIZE, i, chunks, decls, started.elapsed().as_micros()\n                            );\n                        })\n                        .unwrap(),\n                )\n            }'''
assert s.count(old)==1
p.write_text(s.replace(old,new,1))
PY
done

cat >/tmp/v56-config.json <<'EOF'
{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":4,"print_success_message":false}
EOF

git clone --depth 1 https://github.com/leanprover/lean-kernel-arena /tmp/v56-arena
cd /tmp/v56-arena
for t in init-prelude mathlib; do nix develop -c ./lka.py build-test "$t"; done

# Use identical Arena-style init-prelude PGO for each chunk policy.
for c in 64 128; do
  mkdir -p "/tmp/v56-$c-pgo"
  (cd "/tmp/v56-$c" && RUSTFLAGS="-C target-cpu=native -Cprofile-generate=/tmp/v56-$c-pgo" cargo build --release --locked)
  "/tmp/v56-$c/target/release/sokonanoda" /tmp/v56-config.json < /tmp/v56-arena/_build/tests/init-prelude.ndjson >/dev/null 2>"/tmp/v56-$c-train.err"
  llvm-profdata merge -o "/tmp/v56-$c-pgo/merged.profdata" "/tmp/v56-$c-pgo"
  (cd "/tmp/v56-$c" && RUSTFLAGS="-C target-cpu=native -Cprofile-use=/tmp/v56-$c-pgo/merged.profdata" cargo build --release --locked)
  cp "/tmp/v56-$c/target/release/sokonanoda" "/tmp/v56-$c-bin"
done

# Exact replay first, retaining census stderr.
/tmp/v56-64-bin /tmp/v56-config.json < /tmp/v56-arena/_build/tests/mathlib.ndjson >/tmp/v56-64.out 2>/tmp/v56-64-census.err
/tmp/v56-128-bin /tmp/v56-config.json < /tmp/v56-arena/_build/tests/mathlib.ndjson >/tmp/v56-128.out 2>/tmp/v56-128-census.err
cmp /tmp/v56-64.out /tmp/v56-128.out
echo V56_MATHLIB_SEMANTIC_REPLAY=EXACT

python3 - <<'PY' | tee /tmp/v56-decision.txt
from pathlib import Path
import re
for c in (64,128):
    text=Path(f'/tmp/v56-{c}-census.err').read_text()
    rows=[]
    for m in re.finditer(r'V56_THREAD chunk=(\d+) thread=(\d+) chunks=(\d+) decls=(\d+) elapsed_us=(\d+)',text):
        rows.append(tuple(map(int,m.groups())))
    assert len(rows)==4,(c,rows)
    rows=sorted(rows,key=lambda r:r[1])
    times=[r[4] for r in rows]
    chunks=[r[2] for r in rows]
    decls=[r[3] for r in rows]
    skew=max(times)-min(times)
    rel=skew/max(times)*100
    print(f'V56_CHUNK={c} THREAD_ROWS={rows}')
    print(f'V56_CHUNK={c} total_claimed_chunks={sum(chunks)} total_decls={sum(decls)} finish_skew_us={skew} finish_skew_pct={rel:.4f}%')
print('DECISION=V56_CENSUS_ONLY__READ_MECHANISM_BEFORE_CREATING_SCHEDULER')
print('RULE=IF_128_REDUCES_CLAIMS_WITHOUT_WORSENING_FINISH_SKEW_RETAIN_FIXED128;_IF_SKEW_DOMINATES_CREATE_ONLY_THE_MINIMAL_LOAD_DISTINCTION')
PY
