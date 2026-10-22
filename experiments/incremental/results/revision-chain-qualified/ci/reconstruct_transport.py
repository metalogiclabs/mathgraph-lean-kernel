#!/usr/bin/env python3
"""Reconstruct exact qualification ZIP from authenticated transport envelopes."""
import hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent
metadata=json.loads((root.parent/'artifact-transport/artifacts-now.json').read_text())
artifacts=metadata['artifacts']
proof={'schema':'mathgraph.exact-artifact-reconstruction.v1','parts':[]}
with zipfile.ZipFile(root/'transport-partmanifest.zip') as z:
    assert z.testzip() is None
    for n in z.namelist():
        assert n in ('transport-manifest.json','original-artifact.json','original-run.json')
        (root/n).write_bytes(z.read(n))
manifest=json.loads((root/'transport-manifest.json').read_text())
assert manifest['qualified_source']=='d1b22447d23a928ae536cbe838a47fc9682a4b39'
assert manifest['qualification_run']==39679768047
expected=manifest['original_archive_sha256']
assert expected=='878fbeeb4f6241084fd89ca20a2b9b8077c9071e2ada7e2e0b94d054e743d766'
out=root/'revision-chain-summaries-d1b2244.zip.part'
total=0;whole=hashlib.sha256()
with out.open('xb') as dest:
    for i,entry in enumerate(manifest['parts']):
        p=root/('transport-part%02d.zip'%i)
        outer=hashlib.sha256(p.read_bytes()).hexdigest()
        a=next(a for a in artifacts if a['name']=='revision-chain-transport-part%02d-d1b2244'%i)
        assert p.stat().st_size==a['size_in_bytes'] and a['digest']=='sha256:'+outer
        digest=hashlib.sha256();size=0
        with zipfile.ZipFile(p) as z:
            assert z.namelist()==[entry['name']]
            with z.open(entry['name']) as source:
                while True:
                    b=source.read(4*1024*1024)
                    if not b:break
                    dest.write(b);size+=len(b);total+=len(b);digest.update(b);whole.update(b)
        assert size==entry['bytes'] and digest.hexdigest()==entry['sha256']
        proof['parts'].append(dict(part=i,artifact_id=a['id'],outer_bytes=p.stat().st_size,
                                   outer_sha256=outer,inner=entry))
assert total==manifest['original_archive_bytes']==1250298163
assert whole.hexdigest()==expected
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    proof['zip_members']=len(z.infolist())
out.rename(out.with_suffix(''))
proof.update(passed=True,original_bytes=total,original_sha256=expected,
             qualified_source=manifest['qualified_source'],qualification_run=39679768047,
             original_artifact_id=12390854795,zip_crc_passed=True)
(root/'reconstruction-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof,indent=2))
