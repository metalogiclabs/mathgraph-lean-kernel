#!/usr/bin/env python3
import hashlib,json,pathlib,subprocess,sys,time,zipfile
root=pathlib.Path('/workspace/kernel-audit/authenticated-state');ci=root/'ci-cec9941'
label=sys.argv[1];assert label in ('compact-00','compact-01')
metadata=json.loads((ci/'downloads/artifacts.json').read_bytes())
source='cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5'
provider=next(x for x in metadata['artifacts'] if x['name']=='authenticated-state-'+label+'-'+source)
manifest=ci/'permanent-provider-parts'/label/'manifest.json'
m=json.loads(manifest.read_bytes());assert m['qualified_source']==source and m['qualification_run']==39709067518 and m['original_artifact_id']==provider['id']
reader=root/'evidence-packaging/reconstruct_archive.py'
assert hashlib.sha256(reader.read_bytes()).hexdigest()=='d8fcf72c03c0e09e5d3c8634c9a0313905fcdbeabab9434fefd55e963236e1da'
output=ci/('root-exclusive-reconstructed-'+label+'.zip');assert not output.exists()
command=['python3',str(reader),'--manifest',str(manifest),'--output',str(output)]
run=subprocess.run(command,capture_output=True,text=True)
assert run.returncode==0,(run.returncode,run.stderr)
reported=json.loads(run.stdout);assert reported['passed'] is True and reported['zip_crc_checked'] is True
with output.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
assert output.stat().st_size==provider['size_in_bytes'] and 'sha256:'+digest==provider['digest']
with zipfile.ZipFile(output) as archive:assert archive.testzip() is None
original=ci/'downloads'/(provider['name']+'.zip')
with original.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==digest
assert original.stat().st_size==output.stat().st_size
proof={'schema':'mathgraph.root-provider-partset-reconstruction.v1','passed':True,'scope':'Exact provider ZIP byte preservation only; no new verification timing claim','source_sha':source,'run_id':39709067518,'artifact_id':provider['id'],'provider_bytes':output.stat().st_size,'provider_sha256':digest,'parts_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'unchanged_reader_sha256':hashlib.sha256(reader.read_bytes()).hexdigest(),'command':command,'reader_report':reported,'root_full_written_sha256_and_crc_rechecked':True,'original_provider_retained_unchanged':True,'own_exclusive_validation_duplicate_removed':False,'completed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
p=ci/('root-provider-partset-'+label+'-proof.json');p.write_text(json.dumps(proof,indent=2)+'\n')
output.unlink();proof['own_exclusive_validation_duplicate_removed']=True
p.write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof))
