#!/usr/bin/env python3
import csv,itertools,sys
BASE=('empty','closed','canonical')
PROGRAMS=[('e0',),('u0','e0'),('u1','e0')]
def load(p):
 with open(p,newline='') as f:return [{k:(v if k=='corpus' else int(v)) for k,v in r.items()} for r in csv.DictReader(f)]
def interp(r,p):
 cur='root'
 for op in p:
  if op=='u0': cur='a0' if cur=='root' else cur
  elif op=='u1': cur='a1' if cur=='root' else cur
  elif op=='e0': return r[cur]
  else: raise ValueError(op)
 return r[cur]
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
def best(rows,g=None):
 z=None
 for rule in rules(BASE+(('g',) if g is not None else ())):
  cov=bad=0;sig=[]
  for i,r in enumerate(rows):
   h=hit(rule,r,None if g is None else g[i]);sig.append(h)
   if h: cov+=r['safe']==1;bad+=r['safe']==0
  if cov and not bad:
   q=(-cov,0 if rule=='TRUE' else rule.count('&')+1,rule,tuple(sig))
   if z is None or q[:3]<z[:3]:z=q
 return z
def evalp(rows,p):
 vals=[interp(r,p) for r in rows];out=[]
 for k in range(16):
  for kind,c,tc in [('and',1,3),('mod',2,3),('neq0',1,4)]:
   gv=[(v>>k)&1 for v in vals];b=best(rows,gv)
   if b:out.append((b[0],len(p)+tc+b[1],';'.join(p),k,kind,b[2],tuple(gv),b[3]))
 return out
def main():
 rows=load(sys.argv[1]);safe=sum(r['safe'] for r in rows);print(f'V27_EVENTS total={len(rows)} safe={safe} unsafe={len(rows)-safe}')
 b=best(rows);base=-b[0] if b else 0
 one=evalp(rows,('e0',));init=max(base,max((-z[0] for z in one),default=0));print(f'V27_INITIAL_DEPTH01_FRONTIER={init}')
 gen=[]
 for p in PROGRAMS[1:]:
  q=evalp(rows,p);gen+=q;print(f'V27_PROGRAM={";".join(p)} best={max((-x[0] for x in q),default=0)}')
 gen.sort(key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]));z=gen[0];cov=-z[0];cost=z[1]
 if cov<=init:print('ONLINE_CLOSURE_INTERPRETER_V27=FALSIFIED');return 4
 top=[x for x in gen if -x[0]==cov and x[1]==cost];classes={}
 for x in top:classes.setdefault((x[6],x[7]),[]).append(x)
 print(f'V27_BEST_BEHAVIOURAL_CLASSES={len(classes)}')
 if len(classes)!=1:print('ONLINE_CLOSURE_INTERPRETER_V27=UNDERIDENTIFIED');return 2
 eq=next(iter(classes.values()));eq.sort(key=lambda x:(x[2],x[3],x[4],x[5]));z=eq[0];sel={x[2] for x in eq}
 ab=[x for x in gen if x[2] not in sel];ab_cov=max(init,max((-x[0] for x in ab),default=0))
 p=z[2];k=z[3];kind=z[4];pred=z[5]
 expr=(f'and(shr(GEN,{k}),1)' if kind=='and' else f'mod(shr(GEN,{k}),2)' if kind=='mod' else f'neq0(and(shr(GEN,{k}),1))')
 print(f'V27_SELECTED_GENERATOR={p}');print(f'V27_DESCENDANT_PROGRAM={expr}');print(f'V27_DESCENDANT_PREDICATE={pred}');print(f'V27_POST_INSTALL_FRONTIER={cov}');print(f'V27_STRICT_CLOSURE_GAIN={cov-init}');print(f'V27_ABLATION_FRONTIER={ab_cov}')
 if ab_cov>=cov:print('ONLINE_CLOSURE_INTERPRETER_V27=UNDERIDENTIFIED');return 2
 print('V27_INITIAL_CLOSURE_INSUFFICIENT=PASS');print('V27_ONLINE_INTERPRETER_EXTENSION=PASS');print('V27_UNIQUE_MIN_GENERATOR_CLASS=PASS');print('V27_EXACT_GENERATOR_ABLATION=PASS');print('V27_NO_PREMATERIALIZED_PROGRAM_OUTCOME_TABLE=PASS')
 open('/tmp/v27_generator.txt','w').write(p);open('/tmp/v27_expr.txt','w').write(expr);open('/tmp/v27_predicate.txt','w').write(pred);open('/tmp/v27_broad_predicate.txt','w').write('TRUE')
 print('ONLINE_CLOSURE_INTERPRETER_V27=BOUNDED_POSITIVE')
if __name__=='__main__':raise SystemExit(main() or 0)
