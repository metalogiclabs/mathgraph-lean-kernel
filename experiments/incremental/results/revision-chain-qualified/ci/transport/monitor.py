import subprocess,json,time,datetime,pathlib
root=pathlib.Path(__file__).parent
for attempt in range(50):
 data={}
 for label,path in [('run','actions/runs/39698586368'),('jobs','actions/runs/39698586368/jobs'),('artifacts','actions/runs/39698586368/artifacts')]:
  raw=subprocess.check_output(['gh','api','/repos/metalogiclabs/mathgraph-lean-kernel/'+path])
  root.joinpath(label+'-latest.json').write_bytes(raw)
  data[label]=json.loads(raw)
 out={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':data['run']['status'],'conclusion':data['run']['conclusion'],'steps':[(s['number'],s['status'],s['conclusion']) for j in data['jobs']['jobs'] for s in j['steps']], 'artifacts':[(a['id'],a['name'],a['size_in_bytes'],a['digest']) for a in data['artifacts']['artifacts']]}
 root.joinpath('poll-%03d.json'%attempt).write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(out),flush=True)
 if out['status']=='completed': break
 time.sleep(30)
