#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v12 /tmp/v12-arena /tmp/v12-target /tmp/v12-base-target
git worktree add /tmp/v12 "$BASE"
cd /tmp/v12
cargo test --locked
python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs'); s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::OnceCell;\nuse std::sync::atomic::{AtomicU64, Ordering};',1)
anchor="pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;"
inject=r'''pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;
static I_ENTRY:AtomicU64=AtomicU64::new(0); static I_RECURSOR:AtomicU64=AtomicU64::new(0); static I_QUOT:AtomicU64=AtomicU64::new(0);
static I_STUCK_CACHE:AtomicU64=AtomicU64::new(0); static I_VALUE_CACHE:AtomicU64=AtomicU64::new(0);
static I_REC_MISSING:AtomicU64=AtomicU64::new(0); static I_SPINE_FAIL:AtomicU64=AtomicU64::new(0); static I_SHORT_ARGS:AtomicU64=AtomicU64::new(0);
static I_PRE_REDUCE:AtomicU64=AtomicU64::new(0); static I_DESCEND:AtomicU64=AtomicU64::new(0); static I_DIRECT_FIRE:AtomicU64=AtomicU64::new(0); static I_DIRECT_STUCK:AtomicU64=AtomicU64::new(0);
static I_QUOT_UNSUPPORTED:AtomicU64=AtomicU64::new(0); static I_WAIT_DESCEND:AtomicU64=AtomicU64::new(0); static I_WAIT_FIRE:AtomicU64=AtomicU64::new(0); static I_WAIT_STUCK:AtomicU64=AtomicU64::new(0);
pub fn iota_separator_report(){let g=|x:&AtomicU64|x.load(Ordering::Relaxed); eprintln!("IOTA_SEPARATOR entry={} recursor={} quot={} stuck_cache={} value_cache={} rec_missing={} spine_fail={} short_args={} pre_reduce={} descend={} direct_fire={} direct_stuck={} quot_unsupported={} wait_descend={} wait_fire={} wait_stuck={}",g(&I_ENTRY),g(&I_RECURSOR),g(&I_QUOT),g(&I_STUCK_CACHE),g(&I_VALUE_CACHE),g(&I_REC_MISSING),g(&I_SPINE_FAIL),g(&I_SHORT_ARGS),g(&I_PRE_REDUCE),g(&I_DESCEND),g(&I_DIRECT_FIRE),g(&I_DIRECT_STUCK),g(&I_QUOT_UNSUPPORTED),g(&I_WAIT_DESCEND),g(&I_WAIT_FIRE),g(&I_WAIT_STUCK));}'''
assert anchor in s; s=s.replace(anchor,inject,1)
start=s.index("    fn iota_step(&mut self, depth: u32, v: V<'t>) -> ForceStep<'t> {")
end=s.index("\n    fn strip_head", start)
pre=s[:start]; fn=s[start:end]; post=s[end:]
fn=fn.replace("        let key = v as *const Value<'t> as usize;","        I_ENTRY.fetch_add(1, Ordering::Relaxed);\n        let key = v as *const Value<'t> as usize;",1)
fn=fn.replace("        if self.tc_cache.iota_stuck.contains(&key) {\n            return ForceStep::Done;\n        }","        if self.tc_cache.iota_stuck.contains(&key) { I_STUCK_CACHE.fetch_add(1,Ordering::Relaxed); return ForceStep::Done; }",1)
fn=fn.replace("        if let Some(c) = self.tc_cache.iota_cache.get(&key) {\n            return ForceStep::Reduced(c);\n        }","        if let Some(c) = self.tc_cache.iota_cache.get(&key) { I_VALUE_CACHE.fetch_add(1,Ordering::Relaxed); return ForceStep::Reduced(c); }",1)
fn=fn.replace("            Value::Rigid { head: RigidHead::Recursor(name, levels), spine , ..} => {","            Value::Rigid { head: RigidHead::Recursor(name, levels), spine , ..} => {\n                I_RECURSOR.fetch_add(1,Ordering::Relaxed);",1)
fn=fn.replace("                    None => return ForceStep::Done,","                    None => { I_REC_MISSING.fetch_add(1,Ordering::Relaxed); return ForceStep::Done },",1)
fn=fn.replace("                    None => return ForceStep::Done,","                    None => { I_SPINE_FAIL.fetch_add(1,Ordering::Relaxed); return ForceStep::Done },",1)
fn=fn.replace("                if args.len() <= rec.major_idx() {\n                    return ForceStep::Done;\n                }","                if args.len() <= rec.major_idx() { I_SHORT_ARGS.fetch_add(1,Ordering::Relaxed); return ForceStep::Done; }",1)
fn=fn.replace("                    self.tc_cache.iota_cache.insert(key, r);\n                    return ForceStep::Reduced(r);","                    I_PRE_REDUCE.fetch_add(1,Ordering::Relaxed); self.tc_cache.iota_cache.insert(key, r);\n                    return ForceStep::Reduced(r);",1)
fn=fn.replace("                    return ForceStep::Descend(major_h);","                    I_DESCEND.fetch_add(1,Ordering::Relaxed); return ForceStep::Descend(major_h);",1)
fn=fn.replace("                        self.tc_cache.iota_cache.insert(key, res);\n                        ForceStep::Reduced(res)","                        I_DIRECT_FIRE.fetch_add(1,Ordering::Relaxed); self.tc_cache.iota_cache.insert(key, res);\n                        ForceStep::Reduced(res)",1)
fn=fn.replace("                        self.tc_cache.iota_stuck.insert(key);\n                        ForceStep::Done","                        I_DIRECT_STUCK.fetch_add(1,Ordering::Relaxed); self.tc_cache.iota_stuck.insert(key);\n                        ForceStep::Done",1)
fn=fn.replace("            Value::Rigid { head: RigidHead::QuotConst(name, _), spine , ..} => {","            Value::Rigid { head: RigidHead::QuotConst(name, _), spine , ..} => {\n                I_QUOT.fetch_add(1,Ordering::Relaxed);",1)
fn=fn.replace("                } else {\n                    return ForceStep::Done;\n                };","                } else { I_QUOT_UNSUPPORTED.fetch_add(1,Ordering::Relaxed); return ForceStep::Done; };",1)
# second descend/direct fire/stuck are Quot paths
pos=fn.find("return ForceStep::Descend(major_h);", fn.find("RigidHead::QuotConst"))
if pos!=-1: fn=fn[:pos]+"I_DESCEND.fetch_add(1,Ordering::Relaxed); "+fn[pos:]
pos=fn.find("self.tc_cache.iota_cache.insert(key, res);", fn.find("RigidHead::QuotConst"))
if pos!=-1: fn=fn[:pos]+"I_DIRECT_FIRE.fetch_add(1,Ordering::Relaxed); "+fn[pos:]
pos=fn.find("self.tc_cache.iota_stuck.insert(key);", fn.find("RigidHead::QuotConst"))
if pos!=-1: fn=fn[:pos]+"I_DIRECT_STUCK.fetch_add(1,Ordering::Relaxed); "+fn[pos:]
s=pre+fn+post
# Scope force_all only for descend-after-normalization outcome counts.
fs=s.index("    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {")
fe=s.index("\n    fn iota_step", fs)
f=s[fs:fe]
f=f.replace("                ForceStep::Descend(major) => {\n                    waiting.push(cur);","                ForceStep::Descend(major) => {\n                    I_WAIT_DESCEND.fetch_add(1,Ordering::Relaxed); waiting.push(cur);",1)
f=f.replace("                            Some(res) => {\n                                self.tc_cache.iota_cache.insert(key, res);","                            Some(res) => {\n                                I_WAIT_FIRE.fetch_add(1,Ordering::Relaxed); self.tc_cache.iota_cache.insert(key, res);",1)
f=f.replace("                            None => {\n                                self.tc_cache.iota_stuck.insert(key);","                            None => {\n                                I_WAIT_STUCK.fetch_add(1,Ordering::Relaxed); self.tc_cache.iota_stuck.insert(key);",1)
s=s[:fs]+f+s[fe:]
p.write_text(s)
p=Path('src/main.rs'); s=p.read_text(); a='''    match out {\n        Ok(Some(msg)) => println!("{}", msg),'''; r='''    sokonanoda::eval::iota_separator_report();\n    match out {\n        Ok(Some(msg)) => println!("{}", msg),'''; assert a in s; p.write_text(s.replace(a,r,1))
PY
CARGO_TARGET_DIR=/tmp/v12-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v12-target/release/sokonanoda /tmp/v12-separator-bin
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v12-checker.json
git clone https://github.com/leanprover/lean-kernel-arena /tmp/v12-arena
cd /tmp/v12-arena; git checkout "$ARENA"
for T in perf/app-lam perf/beta-ladder perf/let-ladder perf/grind-ring-5; do nix develop -c ./lka.py build-test "$T"; done
cd /tmp/v12; git checkout -- src/eval.rs src/main.rs
CARGO_TARGET_DIR=/tmp/v12-base-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v12-base-target/release/sokonanoda /tmp/v12-base-bin
python3 - <<'PY'
from pathlib import Path
import subprocess,re,json
A=Path('/tmp/v12-arena'); tests=['app-lam','beta-ladder','let-ladder','grind-ring-5']; rows=[]
for t in tests:
 f=A/f'_build/tests/perf/{t}.ndjson'
 with f.open('rb') as i:b=subprocess.run(['/tmp/v12-base-bin','/tmp/v12-checker.json'],stdin=i,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 with f.open('rb') as i:c=subprocess.run(['/tmp/v12-separator-bin','/tmp/v12-checker.json'],stdin=i,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 assert b.stdout==c.stdout, f'semantic mismatch {t}'
 line=next(x for x in c.stderr.decode().splitlines() if x.startswith('IOTA_SEPARATOR ')); d={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}; d['test']=t; rows.append(d); print(t,line)
Path('/tmp/v12-census.json').write_text(json.dumps(rows,indent=2)); print('SEMANTIC_REPLAY=EXACT')
agg={k:sum(r.get(k,0) for r in rows) for k in rows[0] if k!='test'}
print('AGG',json.dumps(agg,sort_keys=True))
regular = agg['wait_descend']>0 and agg['wait_stuck']==0 and agg['wait_fire']==agg['wait_descend']
status='OBSERVED_DESCEND_ALWAYS_FIRES__NOT_STRUCTURAL_LAW' if regular else 'DESCEND_HAS_COUNTEREXAMPLE_OR_INCOMPLETE_FIRE'
# Choose the dominant reason inside iota_step, not raw constructor identity.
reasons={k:agg[k] for k in ['value_cache','stuck_cache','pre_reduce','descend','direct_fire','direct_stuck','rec_missing','spine_fail','short_args']}
winner=max(reasons,key=reasons.get)
next_grammar={
 'descend':['normalized-major shape','recursor/quot family','descent-chain depth','proof-of-fire precondition'],
 'pre_reduce':['pre-reduction trigger','recursor family','argument-shape predicate'],
 'direct_fire':['major constructor shape','recursor rule family','spine arity'],
 'value_cache':['iota cache provenance','reuse distance','caller-demand'],
}.get(winner,['iota caller-demand','head family','spine/major shape'])
out={'status':status,'aggregate':agg,'reason_counts':reasons,'dominant_iota_reason':winner,'next_candidate_grammar':next_grammar,'promotion_rule':'No promotion from finite no-stuck observation; require proof or complete lawful coverage.'}
Path('/tmp/v12-residual.json').write_text(json.dumps(out,indent=2))
Path('/tmp/v12-decision.txt').write_text('STATUS='+status+'\nDOMINANT_IOTA_REASON='+winner+'\nNEXT_GRAMMAR='+','.join(next_grammar)+'\nDECISION=PROFILE_INCLUSIVE_COST_AND_BUILD_LAWFUL_SEPARATOR\n')
print(Path('/tmp/v12-decision.txt').read_text())
PY
# Deterministic inclusive instruction profile on the only workload with substantial iota traffic.
sudo apt-get update -qq
sudo apt-get install -y -qq valgrind
F=/tmp/v12-arena/_build/tests/perf/grind-ring-5.ndjson
valgrind --tool=callgrind --callgrind-out-file=/tmp/v12-callgrind.out /tmp/v12-base-bin /tmp/v12-checker.json < "$F" >/tmp/v12-cg.stdout 2>/tmp/v12-cg.stderr
callgrind_annotate --inclusive=yes --auto=no /tmp/v12-callgrind.out > /tmp/v12-callgrind.txt
grep -E 'force_all|iota_step|fire_value|fire_recursor|fire_quot|strip_head|is_iota_reducible' /tmp/v12-callgrind.txt | head -100 | tee /tmp/v12-iota-cost.txt || true
