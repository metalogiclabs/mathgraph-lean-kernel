#!/usr/bin/env python3
"""V2: source-acquired local sharing, preserving typed witnesses and tactics.

Finite programmer-supplied grammar; no new mathematical equality is asserted.
Every emitted representation requires actual native Lean/cost qualification.
"""
import argparse,hashlib,json,re
from pathlib import Path
RULE_VERSION='source-local-sharing-v2'
IDENT=r'[^\W\d]\w*(?:\.[^\W\d]\w*)*'
ATOM=re.compile(IDENT)
KEYWORDS=set('have let fun intro exact apply rw simp simpa only using at by theorem lemma show from change refine obtain rcases cases all_goals field_simp ring trans conv_lhs enter'.split())
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def tokens(s):return re.findall(IDENT+r'|[^\s]',s)
def discover(row,limit=4):
 source=row['proof'];mark=':= by\n'
 if mark not in source or re.search(r'\b(sorry|admit|axiom)\b|--|/\-|"',source):return []
 header,body=source.split(mark,1)
 if 'mg_acquired' in source:return []
 locals_=set(re.findall(r'\b(?:let|have) +(\w+)',body))
 for binders in re.findall(r'\b(?:intro|fun) +([^\n:=]+)',body):locals_.update(re.findall(r'\b\w+\b',binders))
 expressions=set();stack=[]
 for i,c in enumerate(body):
  if c=='(':stack.append(i)
  elif c==')' and stack:
   start=stack.pop();term=body[start:i+1]
   if '\n' not in term and ':=' not in term and not re.search(r'\bby\b',term):expressions.add(term)
 # Mine partial applications, including prefixes of longer applications.
 for match in ATOM.finditer(body):
  if match.group() in KEYWORDS:continue
  end=match.end()
  for _ in range(3):
   arg=re.match(r' +('+IDENT+r')',body[end:])
   if not arg or arg.group(1) in KEYWORDS:break
   end+=arg.end();expressions.add(body[match.start():end])
 proposals=[]
 for term in expressions:
  names=set(re.findall(r'\b\w+\b',term))
  own=set()
  for b in re.findall(r'\bfun +([^=]+)=>',term):own.update(re.findall(r'\b\w+\b',b))
  if (names-own)&locals_:continue
  n=body.count(term);cost=len(tokens(term));saving=(n-1)*cost-n-4
  if n<2 or cost<3 or saving<=0:continue
  # Exact token boundaries avoid rewriting a substring of a longer identifier.
  pattern=re.compile(r'(?<![\w.])'+re.escape(term)+r'(?!\w)')
  replaced,n2=pattern.subn('mg_acquired',body)
  if n2!=n:continue
  proof=header+mark+'  let mg_acquired := '+term+'\n'+replaced
  proposals.append((saving,term,proof,n))
 proposals.sort(key=lambda r:(-r[0],r[1]))
 out=[];seen={digest(source)}
 def emit(proof,operator,site):
  sha=digest(proof)
  if sha in seen:return
  assert proof.split(mark,1)[0]==header
  seen.add(sha);out.append(dict(name=row['name'],label=operator+'_'+sha[:12],proof=proof,
   proof_sha256=sha,parent_sha256=digest(source),operator=operator,rule_version=RULE_VERSION,
   discovered=site,status='CANDIDATE_UNVERIFIED'))
 for saving,term,proof,n in proposals[:limit]:
  emit(proof,'local_expression_sharing',dict(expression=term,occurrences=n,estimated_lexical_saving=saving))
 # Preserve directed rw semantics, rather than changing to simplifier semantics.
 pattern=re.compile(r'(?m)^( +)rw \[([^\[\]]+)\] at (\w+)\n')
 for match in pattern.finditer(body):
  indent,rules,name=match.groups();pos=match.end();parts=[rules]
  while True:
   nxt=re.match(re.escape(indent)+r'rw \[([^\[\]]+)\] at '+re.escape(name)+r'(?:\n|$)',body[pos:])
   if not nxt:break
   parts.append(nxt.group(1));pos+=nxt.end()
  if len(parts)>1:
   replacement=indent+'rw ['+', '.join(parts)+'] at '+name+'\n'
   emit(header+mark+body[:match.start()]+replacement+body[pos:],'merge_directed_rewrites',dict(witness=name,ordered_normalizers=parts))
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--portfolio',required=True);ap.add_argument('--out',required=True);ap.add_argument('--name',action='append');a=ap.parse_args()
 bank=[]
 for r in map(json.loads,Path(a.portfolio).read_text().splitlines()):
  if a.name and r['name'] not in a.name:continue
  bank.append(dict(name=r['name'],proof=r['proof'],label='v16_control',operator='control',parent_sha256=digest(r['proof'])))
  bank.extend(discover(r))
 Path(a.out).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in bank))
 print(json.dumps(dict(rule_version=RULE_VERSION,rows=len(bank),bank_sha256=digest(Path(a.out).read_text()))))
if __name__=='__main__':main()
