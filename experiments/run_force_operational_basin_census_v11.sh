#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
git worktree add /tmp/v11 "$BASE"
cd /tmp/v11
cargo test --locked
python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs'); s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::OnceCell;\nuse std::sync::atomic::{AtomicU64, Ordering};')
a="pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;"
i=r'''pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;
static FC_CALLS: AtomicU64=AtomicU64::new(0); static FC_CACHE: AtomicU64=AtomicU64::new(0); static FC_CACHE_SAME: AtomicU64=AtomicU64::new(0);
static FC_TERMINAL: AtomicU64=AtomicU64::new(0); static FC_TERMINAL_SAME: AtomicU64=AtomicU64::new(0);
static FC_THUNK: AtomicU64=AtomicU64::new(0); static FC_THUNK_SAME: AtomicU64=AtomicU64::new(0);
static FC_UNFOLD: AtomicU64=AtomicU64::new(0); static FC_UNFOLD_SAME: AtomicU64=AtomicU64::new(0);
static FC_IOTA: AtomicU64=AtomicU64::new(0); static FC_IOTA_SAME: AtomicU64=AtomicU64::new(0);
static FC_THUNK_FORCE: AtomicU64=AtomicU64::new(0); static FC_UNFOLD_TRY: AtomicU64=AtomicU64::new(0); static FC_UNFOLD_REDUCED: AtomicU64=AtomicU64::new(0);
static FC_IOTA_REDUCED: AtomicU64=AtomicU64::new(0); static FC_IOTA_DESCEND: AtomicU64=AtomicU64::new(0); static FC_FIRE_SUCCESS: AtomicU64=AtomicU64::new(0); static FC_FIRE_STUCK: AtomicU64=AtomicU64::new(0); static FC_ZERO_STEP: AtomicU64=AtomicU64::new(0);
pub fn force_census_report(){let g=|x:&AtomicU64|x.load(Ordering::Relaxed); eprintln!("FORCE_CENSUS calls={} cache={} cache_same={} terminal={} terminal_same={} thunk={} thunk_same={} unfold={} unfold_same={} iota={} iota_same={} thunk_force={} unfold_try={} unfold_reduced={} iota_reduced={} iota_descend={} fire_success={} fire_stuck={} zero_step={}",g(&FC_CALLS),g(&FC_CACHE),g(&FC_CACHE_SAME),g(&FC_TERMINAL),g(&FC_TERMINAL_SAME),g(&FC_THUNK),g(&FC_THUNK_SAME),g(&FC_UNFOLD),g(&FC_UNFOLD_SAME),g(&FC_IOTA),g(&FC_IOTA_SAME),g(&FC_THUNK_FORCE),g(&FC_UNFOLD_TRY),g(&FC_UNFOLD_REDUCED),g(&FC_IOTA_REDUCED),g(&FC_IOTA_DESCEND),g(&FC_FIRE_SUCCESS),g(&FC_FIRE_STUCK),g(&FC_ZERO_STEP));}'''
assert a in s; s=s.replace(a,i,1)
old="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {\n            return r;\n        }\n        let mut cur = v;"""
new="""    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        FC_CALLS.fetch_add(1, Ordering::Relaxed);\n        if let Some(r) = self.store_lookup(depth, v) { FC_CACHE.fetch_add(1, Ordering::Relaxed); if std::ptr::eq(r,v){FC_CACHE_SAME.fetch_add(1,Ordering::Relaxed);} return r; }\n        let basin=match v { Value::Thunk{..}=>{FC_THUNK.fetch_add(1,Ordering::Relaxed);1u8}, Value::Unfold{..}=>{FC_UNFOLD.fetch_add(1,Ordering::Relaxed);2u8}, Value::Rigid{head:RigidHead::Recursor(..)|RigidHead::QuotConst(..),..}=>{FC_IOTA.fetch_add(1,Ordering::Relaxed);3u8}, _=>{FC_TERMINAL.fetch_add(1,Ordering::Relaxed);0u8} };\n        let mut cur = v;"""
assert old in s; s=s.replace(old,new,1)
# Scope all instrumentation edits to force_all so similarly shaped code in whnf_head cannot be touched.
start=s.index("    pub(crate) fn force_all")
end=s.find("\n    pub(crate) fn ", start+1)
if end < 0: end=len(s)
pre,seg,post=s[:start],s[start:end],s[end:]
seg=seg.replace('Value::Thunk { .. } => cur = self.force_thunk(depth, cur),','Value::Thunk { .. } => { FC_THUNK_FORCE.fetch_add(1,Ordering::Relaxed); cur=self.force_thunk(depth,cur) },',1)
seg=seg.replace('Value::Unfold { .. } => {\n                        let next = self.unfold_value(depth, cur);','Value::Unfold { .. } => {\n                        FC_UNFOLD_TRY.fetch_add(1,Ordering::Relaxed); let next=self.unfold_value(depth,cur);',1)
seg=seg.replace('steps += 1;\n                        cur = next;','steps += 1; FC_UNFOLD_REDUCED.fetch_add(1,Ordering::Relaxed);\n                        cur = next;',1)
seg=seg.replace('ForceStep::Reduced(next) => {\n                    steps += 1;','ForceStep::Reduced(next) => {\n                    FC_IOTA_REDUCED.fetch_add(1,Ordering::Relaxed); steps += 1;',1)
seg=seg.replace('ForceStep::Descend(major) => {\n                    waiting.push(cur);','ForceStep::Descend(major) => {\n                    FC_IOTA_DESCEND.fetch_add(1,Ordering::Relaxed); waiting.push(cur);',1)
seg=seg.replace('Some(res) => {\n                                self.tc_cache.iota_cache.insert(key, res);','Some(res) => {\n                                FC_FIRE_SUCCESS.fetch_add(1,Ordering::Relaxed); self.tc_cache.iota_cache.insert(key,res);',1)
seg=seg.replace('None => {\n                                self.tc_cache.iota_stuck.insert(key);','None => {\n                                FC_FIRE_STUCK.fetch_add(1,Ordering::Relaxed); self.tc_cache.iota_stuck.insert(key);',1)
e='''        self.note_whnf(depth, v, result, steps);\n        result'''
r='''        if steps==0{FC_ZERO_STEP.fetch_add(1,Ordering::Relaxed);} if std::ptr::eq(result,v){match basin{0=>{FC_TERMINAL_SAME.fetch_add(1,Ordering::Relaxed);},1=>{FC_THUNK_SAME.fetch_add(1,Ordering::Relaxed);},2=>{FC_UNFOLD_SAME.fetch_add(1,Ordering::Relaxed);},3=>{FC_IOTA_SAME.fetch_add(1,Ordering::Relaxed);},_=>{}}}\n        self.note_whnf(depth, v, result, steps);\n        result'''
assert e in seg
seg=seg.replace(e,r,1)
p.write_text(pre+seg+post)
p=Path('src/main.rs'); s=p.read_text(); a='''    match out {\n        Ok(Some(msg)) => println!("{}", msg),'''; r='''    sokonanoda::eval::force_census_report();\n    match out {\n        Ok(Some(msg)) => println!("{}", msg),'''; assert a in s; p.write_text(s.replace(a,r,1))
PY
CARGO_TARGET_DIR=/tmp/v11-target RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp /tmp/v11-target/release/sokonanoda /tmp/v11-census-bin
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v11-checker.json
git clone https://github.com/leanprover/lean-kernel-arena /tmp/v11-arena
cd /tmp/v11-arena; git checkout "$ARENA"
for T in perf/app-lam perf/beta-ladder perf/let-ladder perf/grind-ring-5; do nix develop -c ./lka.py build-test "$T"; done
cd /tmp/v11; git checkout -- src/eval.rs src/main.rs
CARGO_TARGET_DIR=/tmp/v11-base-target RUSTFLAGS='-C target-cpu=x86-64' cargo build --release --locked
cp /tmp/v11-base-target/release/sokonanoda /tmp/v11-base-bin
python3 - <<'PY'
from pathlib import Path
import subprocess,json,re,csv
A=Path('/tmp/v11-arena'); tests=['app-lam','beta-ladder','let-ladder','grind-ring-5']; rs=[]
for t in tests:
 f=A/f'_build/tests/perf/{t}.ndjson'
 with f.open('rb') as i:b=subprocess.run(['/tmp/v11-base-bin','/tmp/v11-checker.json'],stdin=i,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 with f.open('rb') as i:c=subprocess.run(['/tmp/v11-census-bin','/tmp/v11-checker.json'],stdin=i,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 assert b.stdout==c.stdout,t
 line=next(x for x in c.stderr.decode().splitlines() if x.startswith('FORCE_CENSUS ')); d={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)};d['test']=t;rs.append(d);print(t,line)
Path('/tmp/v11-census.json').write_text(json.dumps(rs,indent=2));print('SEMANTIC_REPLAY=EXACT')
keys=['cache','terminal','thunk','unfold','iota']; agg={k:sum(r.get(k,0) for r in rs) for k in keys}; same={k:sum(r.get(k+'_same',0) for r in rs) for k in keys}; total=sum(agg.values()); rows=[]
for k in keys:
 n=agg[k]; sr=same[k]/n if n else 0.; unresolved=k in ('thunk','unfold','iota'); rows.append({'basin':k,'calls':n,'share':n/total if total else 0,'same':same[k],'same_rate':sr,'unresolved':unresolved,'priority':n*sr if unresolved else 0})
rows.sort(key=lambda x:x['priority'],reverse=True)
with open('/tmp/v11-ranking.csv','w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
for x in rows:print(f"BASIN {x['basin']} calls={x['calls']} share={x['share']:.4%} same_rate={x['same_rate']:.4%} priority={x['priority']:.1f}")
active=[x for x in rows if x['unresolved'] and x['calls']]; winner=active[0]['basin'] if active else 'none'; actions={k:sum(r.get(k,0) for r in rs) for k in ['thunk_force','unfold_try','unfold_reduced','iota_reduced','iota_descend','fire_success','fire_stuck','zero_step']}
g={'thunk':['deferred-evaluation predicate','environment-demand predicate','expression-loose-bvar predicate','force-thunk memo/identity separator'],'unfold':['unfold-hint predicate','stuck-vs-reducing unfold predicate','continuation/depth predicate','head-demand predicate'],'iota':['pending-spine-action predicate','major-shape predicate','stuck-vs-fire predicate','descend-demand predicate'],'none':['force_all caller/demand grammar']}[winner]
out={'residual':'constructor-membership plateau','selected_unresolved_basin':winner,'ranking':rows,'actions':actions,'next_candidate_grammar':g,'rule':'measure prefix-cost separators next; do not infer speedup from census alone'};Path('/tmp/v11-residual.json').write_text(json.dumps(out,indent=2)); Path('/tmp/v11-decision.txt').write_text('SELECTED_UNRESOLVED_BASIN='+winner+'\nNEXT_GRAMMAR='+','.join(g)+'\nDECISION=MEASURE_PREFIX_COST_SEPARATOR_FOR_SELECTED_BASIN\n');print(Path('/tmp/v11-decision.txt').read_text());print('ACTIONS',json.dumps(actions,sort_keys=True))
PY
