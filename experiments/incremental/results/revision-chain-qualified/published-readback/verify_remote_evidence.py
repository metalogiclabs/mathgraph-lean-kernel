#!/usr/bin/env python3
"""Read back published evidence commit/tree and critical report bytes."""
import argparse,base64,hashlib,json,subprocess
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
prefix='experiments/incremental/results/revision-chain-qualified/'
def api(endpoint):return json.loads(subprocess.check_output(['gh','api','/repos/metalogiclabs/mathgraph-lean-kernel/'+endpoint],timeout=300))
commit=api('commits/'+a.commit);assert commit['sha']==a.commit
(a.out/'commit.json').write_text(json.dumps(commit,indent=2)+'\n')
tree=api('git/trees/'+commit['commit']['tree']['sha']+'?recursive=1');assert not tree.get('truncated',False)
(a.out/'tree.json').write_text(json.dumps(tree,indent=2)+'\n')
remote={r['path']:r for r in tree['tree'] if r['type']=='blob'}
raw=subprocess.check_output(['git','ls-tree','-rz',a.commit,'--',prefix],cwd=a.repo)
expected={}
for line in raw.split(b'\0'):
    if not line:continue
    info,path=line.split(b'\t',1);mode,kind,identity=info.split();assert kind==b'blob'
    expected[path.decode()]=identity.decode()
assert expected and set(expected)=={p for p in remote if p.startswith(prefix)}
for path,identity in expected.items():assert remote[path]['sha']==identity
critical=['README.md','SHA256SUMS','qualification.json','packaging/manifest.json','independent-review/actual-ci/ci-review.json','fresh-kernels/summary.json']
checks=[]
for relative in critical:
    path=prefix+relative;data=api('git/blobs/'+expected[path]);assert data['encoding']=='base64' and data['sha']==expected[path]
    content=base64.b64decode(data['content'],validate=False);local=(a.repo/path).read_bytes()
    assert content==local and len(content)==remote[path]['size']
    checks.append(dict(path=path,bytes=len(content),git_blob_sha=expected[path],decoded_sha256=hashlib.sha256(content).hexdigest()))
result=dict(schema='mathgraph.published-evidence-readback.v1',passed=True,commit=a.commit,
            tree_sha=commit['commit']['tree']['sha'],all_evidence_blob_ids_equal=len(expected),
            critical_report_bytes_checked=checks,
            archive_scope='Every part Git blob identity matches the local committed object; critical report bytes are independently decoded and SHA256 checked. Archive parts were not downloaded a second time through GitHub.',
            qualified_runtime='d1b22447d23a928ae536cbe838a47fc9682a4b39')
(a.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
