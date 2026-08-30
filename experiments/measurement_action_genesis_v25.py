#!/usr/bin/env python3
import csv,itertools,sys
BASE=('empty','closed','canonical')
INITIAL=(('root.disc','p0'),('context.depth','p3'))
ACTIONS=(
 ('delta(root,act(root,0),0)','root.generated0.disc','p1',3),
 ('delta(root,act(root,1),0)','root.generated1.disc','p2',3),
 ('delta(root,act(root,0),1)','root.disc','p0',3),
)
def load(p):
 with open(p,newline='') as f:return [{k:(v if k=='corpus' else int(v)) for k,v in r.items()} for r in csv.DictReader(f)]
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
def score(rows,action,src,col,acost):
 out=[]
 for expr,k,tc in transforms(src):
  gv=[(r[col]>>k)&1 for r in rows];b=best_pred(rows,gv)
  if b:out.append((b[0],acost+tc+b[1],action,src,expr,b[2],tuple(gv),b[3]))
 return out
def initial(rows):
 out=[]
 for src,col in INITIAL:out+=score(rows,'INITIAL',src,col,0)
 return sorted(out,key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]))
def generated(rows,allowed=None):
 out=[]
 for action,src,col,cost in ACTIONS:
  if allowed is not None and action not in allowed:continue
  out+=score(rows,action,src,col,cost)
 return sorted(out,key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]))
def main():
 rows=load(sys.argv[1]);safe=sum(r['safe'] for r in rows);unsafe=len(rows)-safe
 print(f'V25_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
 if not safe or not unsafe:return 2
 bp=best_pred(rows);ini=initial(rows);init=max(-bp[0] if bp else 0,-ini[0][0] if ini else 0)
 print(f'V25_INITIAL_MEASUREMENT_FRONTIER safe_coverage={init}')
 if init==safe:print('MEASUREMENT_ACTION_GENESIS_V25=NO_GENESIS_NEEDED');return 3
 allz=generated(rows)
 for action,_,_,_ in ACTIONS:
  q=generated(rows,{action});print(f'V25_ACTION_CANDIDATE program={action} safe_coverage={-q[0][0] if q else 0}')
 if not allz or -allz[0][0]<=init:print('MEASUREMENT_ACTION_GENESIS_V25=FALSIFIED');return 4
 cov=-allz[0][0];cost=allz[0][1];top=[z for z in allz if -z[0]==cov and z[1]==cost];classes={}
 for z in top:classes.setdefault((z[6],z[7]),[]).append(z)
 print(f'V25_BEST_BEHAVIOURAL_ACTION_CLASSES={len(classes)}')
 if len(classes)!=1:print('MEASUREMENT_ACTION_GENESIS_V25=UNDERIDENTIFIED');return 2
 eq=next(iter(classes.values()));eq.sort(key=lambda z:(z[2],z[3],z[4],z[5]));z=eq[0];selected={q[2] for q in eq};remaining={a for a,_,_,_ in ACTIONS if a not in selected};ab=generated(rows,remaining);abc=max(init,-ab[0][0] if ab else 0)
 print(f'V25_SELECTED_MEASUREMENT_ACTION={z[2]}');print(f'V25_SELECTED_ACTION_CLASS={"|".join(sorted(selected))}');print(f'V25_GENERATED_SOURCE={z[3]}');print(f'V25_GENERATED_PROGRAM={z[4]}');print(f'V25_GENERATED_PREDICATE={z[5]}');print(f'V25_GENERATED_FRONTIER safe_coverage={cov}');print(f'V25_STRICT_FRONTIER_GAIN={cov-init}');print(f'V25_ACTION_ABLATION_FRONTIER safe_coverage={abc}')
 if abc>=cov:print('MEASUREMENT_ACTION_GENESIS_V25=UNDERIDENTIFIED');return 2
 print('V25_INITIAL_MEASUREMENT_LANGUAGE_INSUFFICIENT=PASS');print('V25_UNIQUE_BEST_MEASUREMENT_ACTION_BEHAVIOURAL_CLASS=PASS');print('V25_EXACT_MEASUREMENT_ACTION_ABLATION=PASS');print('V25_NO_PASSIVE_TRAVERSAL_OR_DECOMPOSITION_LANGUAGE_EXPOSED=PASS')
 open('/tmp/v25_action.txt','w').write(z[2]);open('/tmp/v25_source.txt','w').write(z[3]);open('/tmp/v25_expr.txt','w').write(z[4]);open('/tmp/v25_predicate.txt','w').write(z[5]);open('/tmp/v25_broad_predicate.txt','w').write('TRUE')
if __name__=='__main__':raise SystemExit(main() or 0)
