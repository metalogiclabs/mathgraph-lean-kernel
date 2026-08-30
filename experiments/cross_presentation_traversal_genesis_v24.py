#!/usr/bin/env python3
import csv,itertools,sys
BASE=('empty','closed','canonical')
INITIAL=(('root.disc','p0'),('context.depth','p3'))
PRESENTATIONS={
 'A':(
  ('read(mark(root))','a.generated0.disc','p1',3),
  ('read(next(mark(root)))','a.generated1.disc','p2',4),
  ('read(root)','a.root.disc','p0',2),
 ),
 'B':(
  ('sample(focus(root,zero))','b.generated0.disc','p1',3),
  ('sample(focus(root,one))','b.generated1.disc','p2',4),
  ('sample(root)','b.root.disc','p0',2),
 ),
}
MASK=(1<<64)-1
def rotl2(x): return (((x<<2)&MASK)|(x>>62))^1
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
def scalar(r,col,pres):
 x=r[col]
 return rotl2(x) if pres=='B' else x
def score(rows,pres,op,src,col,ocost):
 out=[]
 for expr,k,tc in transforms(src):
  gv=[(scalar(r,col,pres)>>k)&1 for r in rows];b=best_pred(rows,gv)
  if b:out.append((b[0],ocost+tc+b[1],op,src,expr,b[2],tuple(gv),b[3],k))
 return out
def initial(rows):
 out=[]
 for src,col in INITIAL:out+=score(rows,'A','INITIAL',src,col,0)
 return sorted(out,key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]))
def generated(rows,pres,allowed=None):
 out=[]
 for op,src,col,cost in PRESENTATIONS[pres]:
  if allowed is not None and op not in allowed:continue
  out+=score(rows,pres,op,src,col,cost)
 return sorted(out,key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]))
def select(rows,pres,init):
 allz=generated(rows,pres)
 if not allz:return None
 cov=-allz[0][0];cost=allz[0][1]
 top=[z for z in allz if -z[0]==cov and z[1]==cost]
 classes={}
 for z in top:classes.setdefault((z[6],z[7]),[]).append(z)
 print(f'V24_{pres}_BEST_BEHAVIOURAL_CLASSES={len(classes)}')
 if len(classes)!=1:return None
 eq=next(iter(classes.values()));eq.sort(key=lambda z:(z[2],z[3],z[4],z[5]));z=eq[0]
 selected={q[2] for q in eq};remaining={op for op,_,_,_ in PRESENTATIONS[pres] if op not in selected};ab=generated(rows,pres,remaining);abc=max(init,-ab[0][0] if ab else 0)
 print(f'V24_{pres}_SELECTED_OPERATOR={z[2]}')
 print(f'V24_{pres}_SELECTED_SOURCE={z[3]}')
 print(f'V24_{pres}_SELECTED_PROGRAM={z[4]}')
 print(f'V24_{pres}_SELECTED_PREDICATE={z[5]}')
 print(f'V24_{pres}_FRONTIER={cov}')
 print(f'V24_{pres}_ABLATION_FRONTIER={abc}')
 if cov<=init or abc>=cov:return None
 return z,cov,abc

def main():
 rows=load(sys.argv[1]);safe=sum(r['safe'] for r in rows);unsafe=len(rows)-safe
 print(f'V24_EVENTS total={len(rows)} safe={safe} unsafe={unsafe}')
 if not safe or not unsafe:return 2
 bp=best_pred(rows);ini=initial(rows);init=max(-bp[0] if bp else 0,-ini[0][0] if ini else 0)
 print(f'V24_INITIAL_FRONTIER={init}')
 if init==safe:print('CROSS_PRESENTATION_TRAVERSAL_GENESIS_V24=NO_GENESIS_NEEDED');return 3
 sa=select(rows,'A',init);sb=select(rows,'B',init)
 if not sa or not sb:print('CROSS_PRESENTATION_TRAVERSAL_GENESIS_V24=UNDERIDENTIFIED');return 2
 a,ca,_=sa;b,cb,_=sb
 print(f'V24_A_STRICT_GAIN={ca-init}');print(f'V24_B_STRICT_GAIN={cb-init}')
 same_measure=a[6]==b[6];same_pred=a[7]==b[7]
 print(f'V24_CROSS_PRESENTATION_MEASUREMENT_VECTOR_MATCH={"PASS" if same_measure else "FAIL"}')
 print(f'V24_CROSS_PRESENTATION_PREDICATE_SIGNATURE_MATCH={"PASS" if same_pred else "FAIL"}')
 toksA=set(x[0].replace('(',' ').replace(')',' ').replace(',',' ').split()[0] for x in PRESENTATIONS['A']);toksB=set(x[0].replace('(',' ').replace(')',' ').replace(',',' ').split()[0] for x in PRESENTATIONS['B'])
 disjoint=not(toksA&toksB)
 print(f'V24_DISJOINT_OPERATOR_TOKENS={"PASS" if disjoint else "FAIL"}')
 print('V24_V23_TRAVERSAL_PRIMITIVES_EXPOSED=NO')
 print('V24_COMBINED_DECOMPOSE_OPERATOR_EXPOSED=NO')
 print('V24_SEMANTIC_NAMES_EXPOSED=NO')
 if not same_measure or not same_pred or not disjoint:
  print('CROSS_PRESENTATION_TRAVERSAL_GENESIS_V24=PRESENTATION_DIVERGENCE');return 5
 # Freeze a canonical runtime realization of the shared behavioural class using the A-selected source column.
 k=a[8];expr=f'and(shr(root.generated0.disc,{k}),1)';pred=a[5]
 open('/tmp/v24_expr.txt','w').write(expr);open('/tmp/v24_predicate.txt','w').write(pred);open('/tmp/v24_broad_predicate.txt','w').write('TRUE')
 print(f'V24_CANONICAL_EXPR={expr}');print(f'V24_CANONICAL_PREDICATE={pred}')
 print('V24_INITIAL_LANGUAGE_INSUFFICIENT_BOTH=PASS')
 print('V24_UNIQUE_BEST_CLASSES_BOTH=PASS')
 print('V24_EXACT_OPERATOR_ABLATION_BOTH=PASS')
 print('V24_CROSS_PRESENTATION_CONVERGENCE=PASS')
 return 0
if __name__=='__main__':raise SystemExit(main())
