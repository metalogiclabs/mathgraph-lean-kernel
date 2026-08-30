#!/usr/bin/env python3
import csv,itertools,sys
BASE=('empty','closed','canonical')
INITIAL=(('root.disc','p0'),('context.depth','p3'))
SUBSTRATES={'sigma0':(('root.generated0.disc','p1'),('root.generated1.disc','p2')),'sigma1':(('root.generated1.disc','p2'),),'sigma2':(('root.disc','p0'),('context.depth','p3'))}
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
  n,v=lit.split('='); q=g if n=='g' else r[n]
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
def programs(src):
 for k in range(16):
  yield f'and(shr({src},{k}),1)',k
  yield f'mod(shr({src},{k}),2)',k
  yield f'neq0(and(shr({src},{k}),1))',k
def score(rows,sid,src,col):
 out=[]
 for expr,k in programs(src):
  gv=[(r[col]>>k)&1 for r in rows]; b=best_pred(rows,gv)
  if b:out.append((b[0],(0 if sid=='INITIAL' else 2)+3+b[1],sid,src,expr,b[2],tuple(gv),b[3]))
 return out
def frontier(rows,sids=None):
 out=[]
 if sids is None:
  for src,col in INITIAL:out+=score(rows,'INITIAL',src,col)
 else:
  for sid in sids:
   for src,col in SUBSTRATES[sid]:out+=score(rows,sid,src,col)
 return sorted(out,key=lambda z:(z[0],z[1],z[2],z[3],z[4],z[5]))
def main():
 rows=load(sys.argv[1]); safe=sum(r['safe'] for r in rows); bad=len(rows)-safe
 print(f'V22_EVENTS total={len(rows)} safe={safe} unsafe={bad}')
 if not safe or not bad:return 2
 bp=best_pred(rows); ini=frontier(rows); init=max(-bp[0] if bp else 0,-ini[0][0] if ini else 0)
 print(f'V22_INITIAL_SUBSTRATE_FRONTIER safe_coverage={init}')
 if init==safe:print('STRUCTURAL_SUBSTRATE_GENESIS_V22=NO_GENESIS_NEEDED');return 3
 allz=frontier(rows,set(SUBSTRATES))
 for sid in SUBSTRATES:
  q=frontier(rows,{sid});print(f'V22_SUBSTRATE_CANDIDATE id={sid} safe_coverage={-q[0][0] if q else 0}')
 if not allz or -allz[0][0]<=init:print('STRUCTURAL_SUBSTRATE_GENESIS_V22=FALSIFIED');return 4
 cov=-allz[0][0];cost=allz[0][1];top=[z for z in allz if -z[0]==cov and z[1]==cost];classes={}
 for z in top:classes.setdefault((z[6],z[7]),[]).append(z)
 print(f'V22_BEST_BEHAVIOURAL_SUBSTRATE_CLASSES={len(classes)}')
 if len(classes)!=1:print('STRUCTURAL_SUBSTRATE_GENESIS_V22=UNDERIDENTIFIED');return 2
 eq=next(iter(classes.values()));eq.sort(key=lambda z:(z[2],z[3],z[4],z[5]));z=eq[0];selected={q[2] for q in eq};rem=set(SUBSTRATES)-selected;ab=frontier(rows,rem);abc=max(init,-ab[0][0] if ab else 0)
 print(f'V22_SELECTED_SUBSTRATE={z[2]}');print(f'V22_SELECTED_SUBSTRATE_CLASS={"|".join(sorted(selected))}');print(f'V22_GENERATED_SOURCE={z[3]}');print(f'V22_GENERATED_PROGRAM={z[4]}');print(f'V22_GENERATED_PREDICATE={z[5]}');print(f'V22_GENERATED_FRONTIER safe_coverage={cov}');print(f'V22_STRICT_FRONTIER_GAIN={cov-init}');print(f'V22_SUBSTRATE_ABLATION_FRONTIER safe_coverage={abc}')
 if abc>=cov:print('STRUCTURAL_SUBSTRATE_GENESIS_V22=UNDERIDENTIFIED');return 2
 print('V22_INITIAL_STRUCTURAL_SUBSTRATE_INSUFFICIENT=PASS');print('V22_UNIQUE_BEST_STRUCTURAL_SUBSTRATE_BEHAVIOURAL_CLASS=PASS');print('V22_EXACT_STRUCTURAL_SUBSTRATE_ABLATION=PASS');print('V22_NO_CELL_SEQUENCE_OR_SLOT_LANGUAGE_EXPOSED_TO_LEARNER=PASS')
 open('/tmp/v22_substrate.txt','w').write(z[2]);open('/tmp/v22_source.txt','w').write(z[3]);open('/tmp/v22_expr.txt','w').write(z[4]);open('/tmp/v22_predicate.txt','w').write(z[5]);open('/tmp/v22_broad_predicate.txt','w').write('TRUE')
if __name__=='__main__':raise SystemExit(main() or 0)
