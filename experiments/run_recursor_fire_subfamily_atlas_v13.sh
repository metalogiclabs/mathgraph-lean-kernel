#!/usr/bin/env bash
set -euxo pipefail
BASE=2de1895a52d21ad266b77002defe3e6bc69bbcfd
ARENA=f0fe3b379dbce91537417b529140d0ca250f271c
rm -rf /tmp/v13 /tmp/v13-arena /tmp/v13-target /tmp/v13-base-target
git worktree add /tmp/v13 "$BASE"
cd /tmp/v13
cargo test --locked
python3 - <<'PY'
from pathlib import Path
p=Path('src/eval.rs'); s=p.read_text()
old='''        if self.ctx.export_file.config.nat_extension
            && rec.all_inductives.first().copied() == self.ctx.export_file.name_cache.nat
        {
            if let Value::NatLit { ptr , ..} = major {
                return Some(self.nat_rec_natlit(depth, args, *ptr, rec, levels));
            }
        }
'''
new='''        if self.ctx.export_file.config.nat_extension
            && rec.all_inductives.first().copied() == self.ctx.export_file.name_cache.nat
        {
            if let Value::NatLit { ptr , ..} = major {
                eprintln!("V13_FIRE kind=natlit args={} major_idx={} nprefix={} suffix={}", args.len(), rec.major_idx(), usize::from(rec.num_params + rec.num_motives + rec.num_minors), args.len().saturating_sub(rec.major_idx()+1));
                return Some(self.nat_rec_natlit(depth, args, *ptr, rec, levels));
            }
        }
'''
assert old in s; s=s.replace(old,new,1)
old2='''        let cache_key = (rec_rule.val, levels);
        let mut result = match self.tc_cache.rec_rule_cache.get(&cache_key) {
            Some(v) => *v,
            None => {
                let v = self.eval_inst(rec_rule.val, rec.info.uparams, levels);
                self.tc_cache.rec_rule_cache.insert(cache_key, v);
                v
            }
        };
        let nprefix = usize::from(rec.num_params + rec.num_motives + rec.num_minors);
'''
new2='''        let cache_key = (rec_rule.val, levels);
        let cache_hit = self.tc_cache.rec_rule_cache.get(&cache_key).is_some();
        let mut result = match self.tc_cache.rec_rule_cache.get(&cache_key) {
            Some(v) => *v,
            None => {
                let v = self.eval_inst(rec_rule.val, rec.info.uparams, levels);
                self.tc_cache.rec_rule_cache.insert(cache_key, v);
                v
            }
        };
        let nprefix = usize::from(rec.num_params + rec.num_motives + rec.num_minors);
        eprintln!("V13_FIRE kind=ctor args={} ctor_args={} tel={} nprefix={} suffix={} cache_hit={}", args.len(), ctor_args.len(), usize::from(rec_rule.ctor_telescope_size_wo_params), nprefix, args.len().saturating_sub(rec.major_idx()+1), if cache_hit {1} else {0});
'''
assert old2 in s; s=s.replace(old2,new2,1)
p.write_text(s)
PY
CARGO_TARGET_DIR=/tmp/v13-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v13-target/release/sokonanoda /tmp/v13-atlas-bin
printf '%s\n' '{"use_stdin":true,"nat_extension":true,"string_extension":true,"unpermitted_axiom_hard_error":false,"unsafe_permit_all_axioms":true,"num_threads":1,"print_success_message":false}' >/tmp/v13-checker.json
git clone https://github.com/leanprover/lean-kernel-arena /tmp/v13-arena
cd /tmp/v13-arena
git checkout "$ARENA"
for T in perf/app-lam perf/beta-ladder perf/let-ladder perf/grind-ring-5; do nix develop -c ./lka.py build-test "$T"; done
cd /tmp/v13
git checkout -- src/eval.rs
CARGO_TARGET_DIR=/tmp/v13-base-target RUSTFLAGS='-C target-cpu=x86-64 -C debuginfo=1' cargo build --release --locked
cp /tmp/v13-base-target/release/sokonanoda /tmp/v13-base-bin
python3 - <<'PY'
import subprocess,re,json,csv,collections,os
arena='/tmp/v13-arena/_build/tests'
tests=['perf/app-lam','perf/beta-ladder','perf/let-ladder','perf/grind-ring-5']
rows=[]
for t in tests:
    f=f'{arena}/{t}.ndjson'
    inp=open(f,'rb').read()
    b=subprocess.run(['/tmp/v13-base-bin','/tmp/v13-checker.json'],input=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    a=subprocess.run(['/tmp/v13-atlas-bin','/tmp/v13-checker.json'],input=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    assert a.stdout==b.stdout, t
    for line in a.stderr.decode(errors='replace').splitlines():
        if not line.startswith('V13_FIRE '): continue
        d=dict(re.findall(r'(\w+)=([^ ]+)',line)); d['test']=t; rows.append(d)
print('SEMANTIC_REPLAY=EXACT')
ctr=collections.Counter()
for r in rows:
    key=(r.get('kind'),r.get('args'),r.get('ctor_args','-'),r.get('tel','-'),r.get('nprefix'),r.get('suffix'),r.get('cache_hit','-'))
    ctr[key]+=1
N=len(rows)
out=[]
for key,n in ctr.most_common():
    out.append({'kind':key[0],'args':key[1],'ctor_args':key[2],'tel':key[3],'nprefix':key[4],'suffix':key[5],'cache_hit':key[6],'count':n,'share':n/N if N else 0})
json.dump({'total_fires':N,'groups':out},open('/tmp/v13-atlas.json','w'),indent=2)
with open('/tmp/v13-ranking.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=out[0].keys() if out else ['count']); w.writeheader(); w.writerows(out)
for g in out[:12]: print('GROUP',g)
if out:
    g=out[0]
    print('DOMINANT_RECURSOR_SUBFAMILY='+json.dumps(g,sort_keys=True))
    # Residual chooses the next grammar from measured dominant dimensions.
    if g['kind']=='natlit': nxt=['nat literal magnitude','zero-vs-successor','recursor family']
    else: nxt=['constructor telescope size','prefix application arity','recursive-field pattern','rule-cache reuse']
    residual={'residual':'fire_recursor dominates cost; direct-fire population is structurally nonuniform','dominant_group':g,'next_grammar':nxt,'promotion':'NONE_MEASUREMENT_ONLY'}
    json.dump(residual,open('/tmp/v13-residual.json','w'),indent=2)
    open('/tmp/v13-decision.txt','w').write('NEXT_GRAMMAR='+','.join(nxt)+'\nDECISION=BUILD_DOMINANT_SUBFAMILY_COST_SEPARATOR\nPROMOTION=NONE\n')
PY
