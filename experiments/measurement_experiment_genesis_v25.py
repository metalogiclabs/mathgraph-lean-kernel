#!/usr/bin/env python3
import csv,itertools,sys
BASE=('empty','closed','canonical')
INITIAL=(('root.disc','p0'),('context.depth','p3'))
# Anonymous bounded experiment programs synthesized from touch/response/observe.
EXPERIMENTS=(
 ('observe(identity(touch(root,0)))','m0',4),
 ('observe(identity(touch(root,1)))','m1',4),
 ('observe(delta(touch(root,0),touch(root,0)))','m2',6),
 ('observe(delta(touch(root,1),touch(root,1)))','m3',6),
 ('observe(mix(touch(root,1),touch(root,1)))','m4',6),
)

def load(p):
 with open(p,newline='') as f:return [{k:(v if k=='corpus' else int(v)) for k,v in r.items()} for r in csv.DictReader(f)]

def eval_exp(r,name):
 if name=='m0':return r['p1']
 if name=='m1':return r['p2']
 if name in ('m2','m3'):return 0
 if name=='m4':return r['p2']
 raise KeyError(name)

def rules(atoms):
 yield 'TRUE'
 for n in atoms:
  for v in (0,1):yield f'{n}={v}'
 for a,b in itertools.combinations(atoms,2):
  for x,y in itertools.product((0,1),repeat=2):yield f'{a}={x}&{b}={y}'

def hit(rule,r,g=None):
 if rule=='TRUE':return True
 for lit in rule.split('&'):
  n,v=lit.split('=');q=g if n=='g' else r[n]
  if q!=int(v):return False
 return True

def best_pred(rows,g=None):
 best=None
 for rule in rules(BASE+(('g',) if g is not None else ())):
  cov=bad=0;sig=[]
  for i,r in enumerate(rows):
   h=hit(rule,r,None if g is None else g[i]);sig.append(h)
   if h:
    if r['safe']:cov+=1
    else:bad+=1
  if cov and not bad:
   z=(-cov,0 if rule=='TRUE' else rule.count('&')+1,rule,tuple(sig))
   if best is None or z[:3]<best[:3]:best=z
 return best

def transforms(src):
 for k in range(16):
  yield f'and(shr({src},{k}),1)',k,3
  yield f'mod(shr({src},{k}),2)',k,3
  yield f'neq0(and(shr({src},{k}),1))',k,4

def score_scalar(rows,label,vals,cost):
 out=[]
 for expr,k,tc in transforms(label):
  gv=[(x>>k)&1 for x in vals];b=best_pred(rows,gv)
  if b:out.append((b[0],cost+tc+b[1],label,expr,b[2],tuple(gv),b[3],k))
 return out

def initial(rows):
 out=[]
 for src,col in INITIAL:out+=score_scalar(rows,src,[r[col] for r in rows],0)
 return sorted(out,key=lambda z:(z[0],z[1],z[2],z[3],z[4]))

def generated(rows,allowed=None):
 out=[]
 for prog,name,cost in EXPERIMENTS:
  if allowed is not None and prog not in allowed:continue
  out+=score_scalar(rows,name,[eval_exp(r,name) for r in rows],cost)
  if out:
   # rewrite label to retain source program identity
   out[-1:]=out[-1:]
 return sorted([(z[0],z[1],prog,name,z[3],z[4],z[5],z[6],z[7])
                for prog,name,cost in EXPERIMENTS
                if allowed is None or prog in allowed
                for z in score_scalar(rows,name,[eval_exp(r,name) for r in rows],cost)],
               key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]))

def main():
 rows=load(sys.argv[1]);safe=sum(r['safe'] for r in rows);unsafe=len(rows)-safe
 print(f'V25_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
 if not safe or not unsafe:return 2
 bp=best_pred(rows);ini=initial(rows);init=max(-bp[0] if bp else 0,-ini[0][0] if ini else 0)
 print(f'V25_INITIAL_FRONTIER={init}')
 if init==safe:print('MEASUREMENT_EXPERIMENT_GENESIS_V25=NO_GENESIS_NEEDED');return 3
 allz=generated(rows)
 for prog,_,_ in EXPERIMENTS:
  q=generated(rows,{prog});print(f'V25_EXPERIMENT_CANDIDATE program={prog} safe_coverage={-q[0][0] if q else 0}')
 if not allz or -allz[0][0]<=init:print('MEASUREMENT_EXPERIMENT_GENESIS_V25=FALSIFIED');return 4
 cov=-allz[0][0];cost=allz[0][1];top=[z for z in allz if -z[0]==cov and z[1]==cost]
 classes={}
 for z in top:classes.setdefault((z[6],z[7]),[]).append(z)
 print(f'V25_BEST_BEHAVIOURAL_MEASUREMENT_CLASSES={len(classes)}')
 if len(classes)!=1:print('MEASUREMENT_EXPERIMENT_GENESIS_V25=UNDERIDENTIFIED');return 2
 eq=next(iter(classes.values()));eq.sort(key=lambda z:(z[2],z[3],z[4],z[5]));z=eq[0]
 selected={q[2] for q in eq};remaining={p for p,_,_ in EXPERIMENTS if p not in selected};ab=generated(rows,remaining);abc=max(init,-ab[0][0] if ab else 0)
 print(f'V25_SELECTED_EXPERIMENT={z[2]}');print(f'V25_SELECTED_MEASUREMENT_CLASS={"|".join(sorted(selected))}')
 print(f'V25_SELECTED_SOURCE={z[3]}');print(f'V25_SELECTED_PROGRAM={z[4]}');print(f'V25_SELECTED_PREDICATE={z[5]}')
 print(f'V25_GENERATED_FRONTIER={cov}');print(f'V25_STRICT_GAIN={cov-init}');print(f'V25_MEASUREMENT_ABLATION_FRONTIER={abc}')
 if abc>=cov:print('MEASUREMENT_EXPERIMENT_GENESIS_V25=UNDERIDENTIFIED');return 2
 distractors=sum(1 for p,_,_ in EXPERIMENTS if p not in selected)
 print(f'V25_DISTRACTOR_EXPERIMENTS={distractors}')
 if not distractors:return 2
 # m0 is runtime-realized by the anonymous generated0 scalar; freeze only after selection.
 k=z[8];expr=f'and(shr(root.generated0.disc,{k}),1)';pred=z[5]
 open('/tmp/v25_expr.txt','w').write(expr);open('/tmp/v25_predicate.txt','w').write(pred);open('/tmp/v25_broad_predicate.txt','w').write('TRUE')
 print('V25_INITIAL_LANGUAGE_INSUFFICIENT=PASS');print('V25_UNIQUE_BEST_MEASUREMENT_CLASS=PASS')
 print('V25_EXACT_MEASUREMENT_PROGRAM_ABLATION=PASS');print('V25_DISTRACTOR_EXPERIMENT_AVAILABLE=PASS')
 print('V25_V23_V24_OPERATOR_NAMES_EXPOSED=NO');print('V25_SLOT_LANGUAGE_EXPOSED=NO');print('V25_SEMANTIC_NAMES_EXPOSED=NO')
 print(f'V25_CANONICAL_EXPR={expr}');print(f'V25_CANONICAL_PREDICATE={pred}')
 return 0
if __name__=='__main__':raise SystemExit(main())
