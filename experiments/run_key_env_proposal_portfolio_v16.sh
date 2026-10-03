#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v16 /tmp/v16-arena /tmp/v16-target /tmp/v16-base-target
git worktree add /tmp/v16 "$BASE"
cd /tmp/v16
cargo test --locked
python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs'); s=p.read_text()
s=s.replace('use std::cell::OnceCell;','use std::cell::OnceCell;\nuse std::sync::atomic::{AtomicU64, Ordering};',1)
anchor="pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;"
inject=r'''pub(crate) type SpineArgs<'t> = smallvec::SmallVec<[V<'t>; 8]>;
static V16_DOM:AtomicU64=AtomicU64::new(0);
static V16_KEY:AtomicU64=AtomicU64::new(0);
static V16_K0:AtomicU64=AtomicU64::new(0);
static V16_K1_64:AtomicU64=AtomicU64::new(0);
static V16_KGT64:AtomicU64=AtomicU64::new(0);
static V16_PC0:AtomicU64=AtomicU64::new(0);
static V16_PC1:AtomicU64=AtomicU64::new(0);
static V16_PC2:AtomicU64=AtomicU64::new(0);
static V16_PC3:AtomicU64=AtomicU64::new(0);
static V16_PC4:AtomicU64=AtomicU64::new(0);
static V16_PC5_8:AtomicU64=AtomicU64::new(0);
static V16_PCGT8:AtomicU64=AtomicU64::new(0);
static V16_SAME_ENV:AtomicU64=AtomicU64::new(0);
static V16_ENV_NIL:AtomicU64=AtomicU64::new(0);
static V16_ENV_CONS:AtomicU64=AtomicU64::new(0);
static V16_ENV_FRAMED:AtomicU64=AtomicU64::new(0);
static V16_EXPR_HIT:AtomicU64=AtomicU64::new(0);
static V16_EXPR_MISS:AtomicU64=AtomicU64::new(0);
static V16_ENV_HIT:AtomicU64=AtomicU64::new(0);
static V16_ENV_MISS:AtomicU64=AtomicU64::new(0);
static V16_EXPR_DM:[AtomicU64;4096]=[const { AtomicU64::new(0) };4096];
static V16_ENV_DM:[AtomicU64;4096]=[const { AtomicU64::new(0) };4096];
static V16_BODY_VAR:AtomicU64=AtomicU64::new(0);
static V16_BODY_SORT:AtomicU64=AtomicU64::new(0);
static V16_BODY_CONST:AtomicU64=AtomicU64::new(0);
static V16_BODY_APP:AtomicU64=AtomicU64::new(0);
static V16_BODY_PI:AtomicU64=AtomicU64::new(0);
static V16_BODY_LAM:AtomicU64=AtomicU64::new(0);
static V16_BODY_LET:AtomicU64=AtomicU64::new(0);
static V16_BODY_PROJ:AtomicU64=AtomicU64::new(0);
static V16_BODY_LIT:AtomicU64=AtomicU64::new(0);
pub fn v16_report(){
 let g=|x:&AtomicU64|x.load(Ordering::Relaxed);
 eprintln!("V16_PORTFOLIO dom={} key={} k0={} k1_64={} kgt64={} pc0={} pc1={} pc2={} pc3={} pc4={} pc5_8={} pcgt8={} same_env={} env_nil={} env_cons={} env_framed={} expr_hit={} expr_miss={} env_hit={} env_miss={} body_var={} body_sort={} body_const={} body_app={} body_pi={} body_lam={} body_let={} body_proj={} body_lit={}",g(&V16_DOM),g(&V16_KEY),g(&V16_K0),g(&V16_K1_64),g(&V16_KGT64),g(&V16_PC0),g(&V16_PC1),g(&V16_PC2),g(&V16_PC3),g(&V16_PC4),g(&V16_PC5_8),g(&V16_PCGT8),g(&V16_SAME_ENV),g(&V16_ENV_NIL),g(&V16_ENV_CONS),g(&V16_ENV_FRAMED),g(&V16_EXPR_HIT),g(&V16_EXPR_MISS),g(&V16_ENV_HIT),g(&V16_ENV_MISS),g(&V16_BODY_VAR),g(&V16_BODY_SORT),g(&V16_BODY_CONST),g(&V16_BODY_APP),g(&V16_BODY_PI),g(&V16_BODY_LAM),g(&V16_BODY_LET),g(&V16_BODY_PROJ),g(&V16_BODY_LIT));
}'''
assert anchor in s; s=s.replace(anchor,inject,1)
fire_anchor="    fn fire_recursor(\n        &mut self, depth: u32,"
helpers=r'''    #[inline(never)]
    fn v16_key_env_subset(&mut self, env: E<'t>, e: ExprPtr<'t>) -> E<'t> {
        V16_KEY.fetch_add(1, Ordering::Relaxed);
        let k=e.num_loose_bvars();
        if k==0 {V16_K0.fetch_add(1,Ordering::Relaxed);} else if k<=64 {V16_K1_64.fetch_add(1,Ordering::Relaxed);} else {V16_KGT64.fetch_add(1,Ordering::Relaxed);}
        let pc=e.as_ref().fv_mask().count_ones();
        match pc {0=>&V16_PC0,1=>&V16_PC1,2=>&V16_PC2,3=>&V16_PC3,4=>&V16_PC4,5..=8=>&V16_PC5_8,_=>&V16_PCGT8}.fetch_add(1,Ordering::Relaxed);
        match env {value::Env::Nil{..}=>&V16_ENV_NIL,value::Env::Cons{..}=>&V16_ENV_CONS,value::Env::Framed{..}=>&V16_ENV_FRAMED}.fetch_add(1,Ordering::Relaxed);
        let ep=e as *const crate::expr::Expr<'t> as usize as u64; let es=((ep>>3) as usize)&4095;
        if V16_EXPR_DM[es].swap(ep,Ordering::Relaxed)==ep {V16_EXPR_HIT.fetch_add(1,Ordering::Relaxed);} else {V16_EXPR_MISS.fetch_add(1,Ordering::Relaxed);}
        let vp=env as *const value::Env<'t> as usize as u64; let vs=((vp>>3) as usize)&4095;
        if V16_ENV_DM[vs].swap(vp,Ordering::Relaxed)==vp {V16_ENV_HIT.fetch_add(1,Ordering::Relaxed);} else {V16_ENV_MISS.fetch_add(1,Ordering::Relaxed);}
        let r=self.key_env(env,e);
        if std::ptr::eq(r,env) {V16_SAME_ENV.fetch_add(1,Ordering::Relaxed);}
        r
    }

    #[inline(never)]
    fn v16_apply_dominant_prefix(&mut self, depth:u32, f0:V<'t>, args:&[V<'t>])->V<'t>{
        V16_DOM.fetch_add(1,Ordering::Relaxed);
        let mut f=f0; let mut i=0usize;
        while i<args.len(){
            let Value::Lam{body:clo,..}=f else {f=self.apply(depth,f,args[i]);i+=1;continue};
            let mut env=value::env_extend(self.arena,clo.env,args[i]); let mut body=clo.body; i+=1;
            while i<args.len(){
                let Expr::Lambda{body:inner,..}=self.ctx.read_expr(body) else {break};
                let pruned=self.v16_key_env_subset(env,body);
                env=value::env_extend(self.arena,pruned,args[i]); body=inner; i+=1;
            }
            match self.ctx.read_expr(body){
              Expr::Var{..}=>&V16_BODY_VAR, Expr::Sort{..}=>&V16_BODY_SORT, Expr::Const{..}=>&V16_BODY_CONST,
              Expr::App{..}=>&V16_BODY_APP, Expr::Pi{..}=>&V16_BODY_PI, Expr::Lambda{..}=>&V16_BODY_LAM,
              Expr::Let{..}=>&V16_BODY_LET, Expr::Proj{..}=>&V16_BODY_PROJ,
              Expr::StringLit{..}|Expr::NatLit{..}=>&V16_BODY_LIT
            }.fetch_add(1,Ordering::Relaxed);
            f=self.eval(depth,env,body);
        }
        f
    }

    fn fire_recursor(
        &mut self, depth: u32,'''
assert s.count(fire_anchor)==1; s=s.replace(fire_anchor,helpers,1)
old='''        result = self.apply_many(depth, result, &args[..nprefix]);
        result = self.apply_many(depth, result, &ctor_args[num_extra..]);
        result = self.apply_many(depth, result, &args[rec.major_idx() + 1..]);'''
new='''        let v16_dom = args.len()==4 && ctor_args.is_empty()
            && usize::from(rec_rule.ctor_telescope_size_wo_params)==0
            && nprefix==3 && args.len().saturating_sub(rec.major_idx()+1)==0;
        result=if v16_dom {self.v16_apply_dominant_prefix(depth,result,&args[..nprefix])} else {self.apply_many(depth,result,&args[..nprefix])};
        result = self.apply_many(depth, result, &ctor_args[num_extra..]);
        result = self.apply_many(depth, result, &args[rec.major_idx() + 1..]);'''
assert old in s; s=s.replace(old,new,1)
p.write_text(s)
m=Path('src/main.rs'); t=m.read_text(); needle='    match out {'; assert t.count(needle)==1
t=t.replace(needle,'    sokonanoda::eval::v16_report();\n'+needle,1); m.write_text(t)
PY
CARGO_TARGET_DIR=/tmp/v16-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v16-target/release/sokonanoda /tmp/v16-probe-bin
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v16-checker.json
git clone https://github.com/leanprover/lean-kernel-arena /tmp/v16-arena
cd /tmp/v16-arena; git checkout "$ARENA"
for T in perf/app-lam perf/beta-ladder perf/let-ladder perf/grind-ring-5; do nix develop -c ./lka.py build-test "$T"; done
cd /tmp/v16; git checkout -- src/eval.rs src/main.rs
CARGO_TARGET_DIR=/tmp/v16-base-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v16-base-target/release/sokonanoda /tmp/v16-base-bin
python3 - <<'PY'
import subprocess,re,json
arena='/tmp/v16-arena/_build/tests'; agg={}
for t in ['perf/app-lam','perf/beta-ladder','perf/let-ladder','perf/grind-ring-5']:
 inp=open(f'{arena}/{t}.ndjson','rb').read()
 b=subprocess.run(['/tmp/v16-base-bin','/tmp/v16-checker.json'],input=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 a=subprocess.run(['/tmp/v16-probe-bin','/tmp/v16-checker.json'],input=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 assert a.stdout==b.stdout,t
 lines=[x for x in a.stderr.decode(errors='replace').splitlines() if x.startswith('V16_PORTFOLIO ')]
 if lines:
  d={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',lines[-1])};agg[t]=d;print(t,d)
print('SEMANTIC_REPLAY=EXACT');json.dump(agg,open('/tmp/v16-census.json','w'),indent=2)
g=agg['perf/grind-ring-5']; n=g['key'];
pct=lambda x:100*g[x]/n if n else 0
small4=sum(g[x] for x in ['pc0','pc1','pc2','pc3','pc4']); small8=small4+g['pc5_8']
expr_rep=pct('expr_hit'); env_rep=pct('env_hit'); same=pct('same_env')
body_total=sum(g[x] for x in ['body_var','body_sort','body_const','body_app','body_pi','body_lam','body_let','body_proj','body_lit'])
body=[(g[k],k) for k in ['body_var','body_sort','body_const','body_app','body_pi','body_lam','body_let','body_proj','body_lit']]; body.sort(reverse=True)
cands=[
 {'id':'C_SMALL4','class':'PUSH/REFRAME','score':small4/n if n else 0,'evidence':f'subset mask popcount<=4 {100*small4/n:.3f}%'},
 {'id':'C_SMALL8','class':'PUSH/REFRAME','score':0.92*(small8/n if n else 0),'evidence':f'subset mask popcount<=8 {100*small8/n:.3f}%'},
 {'id':'C_EXPR_SUPPORT_METADATA','class':'REFRAME','score':0.9*(g['expr_hit']/n if n else 0),'evidence':f'direct-mapped expression reuse {expr_rep:.3f}%'},
 {'id':'C_ENV_REUSE','class':'PUSH','score':0.75*(g['env_hit']/n if n else 0),'evidence':f'direct-mapped env reuse {env_rep:.3f}%'},
 {'id':'C_SAME_ENV_BYPASS','class':'PUSH','score':g['same_env']/n if n else 0,'evidence':f'key_env returns same env {same:.3f}%'},
 {'id':'C_FINAL_BODY_SPECIALIZE','class':'PROBE/PUSH','score':0.7*(body[0][0]/body_total if body_total else 0),'evidence':f'dominant final body {body[0][1]} {100*body[0][0]/body_total:.3f}%'}]
cands.sort(key=lambda x:x['score'],reverse=True)
res={'generation_id':'v16','semantic_replay':'EXACT','subset_key_calls':n,'metrics':{'small4_pct':100*small4/n,'small8_pct':100*small8/n,'expr_reuse_pct':expr_rep,'env_reuse_pct':env_rep,'same_env_pct':same,'dominant_final_body':body[0][1],'dominant_final_body_pct':100*body[0][0]/body_total},'candidate_actions_ranked':cands,'selected_action':cands[0]['id'],'promotion':'NONE_MEASUREMENT_AND_SELECTION_ONLY','next_generation':'execute top licensed challenger against exact replay and Callgrind; retain portfolio alternatives if challenger fails'}
json.dump(res,open('/tmp/v16-generation.json','w'),indent=2)
open('/tmp/v16-decision.txt','w').write('SELECTED_ACTION='+cands[0]['id']+'\nRANKING='+','.join(x['id'] for x in cands)+'\nDECISION=EXECUTE_TOP_LICENSED_CHALLENGER\nPROMOTION=NONE\n')
print(json.dumps(res,indent=2))
PY
