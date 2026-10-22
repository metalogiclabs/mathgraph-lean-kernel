#!/usr/bin/env python3
import hashlib,json,pathlib,subprocess,time,resource
root=pathlib.Path('/workspace/kernel-audit/authenticated-state')
repo=pathlib.Path('/workspace/mathgraph-lean-kernel-lifecycle')
source='cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5'
inputs=root/'ci-cec9941/extracted-compact/artifacts'
out=root/'actual-independent-replay'
assert not out.exists(), 'exclusive replay output required'
assert (inputs/'authenticated-state/summary.json').is_file()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==source
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
command=['python3',str(repo/'experiments/incremental/replay_authenticated_state.py'),'--benchmark',str(inputs/'authenticated-state'),'--controls',str(inputs/'state-controls-original'),'--controls',str(inputs/'state-controls-expanded'),'--repo',str(repo),'--source',source,'--rust',str(root/'independent-build/target/release/sokonanoda'),'--indexer',str(root/'independent-build/target/release/export-index'),'--cpp','/home/agent/.elan/toolchains/leanprover--lean4---v4.35.0/bin/leanchecker','--paranoid','/home/agent/.elan/toolchains/leanprover--lean4---v4.35.0/bin/leanchecker-paranoid','--out',str(out)]
observed=dict(scope='Independent actual CI artifact replay; resource observations are replay cost, not benchmark observations',source_sha=source,run_id=39709067518,command=command,started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),input_summary_sha256=hashlib.sha256((inputs/'authenticated-state/summary.json').read_bytes()).hexdigest(),reader_sha256=hashlib.sha256(pathlib.Path(command[1]).read_bytes()).hexdigest(),completed=False)
proof=root/'actual-independent-replay-execution.json'
proof.write_text(json.dumps(observed,indent=2)+'\n')
start=time.monotonic(); usage_before=resource.getrusage(resource.RUSAGE_CHILDREN)
with (root/'actual-independent-replay.log').open('xb') as log:
    process=subprocess.run(command,cwd=repo,stdout=log,stderr=subprocess.STDOUT)
usage_after=resource.getrusage(resource.RUSAGE_CHILDREN)
observed['replay_resources']={'method':'Python stdlib resource.getrusage RUSAGE_CHILDREN after completed reader process','cpu_user_seconds':usage_after.ru_utime-usage_before.ru_utime,'cpu_system_seconds':usage_after.ru_stime-usage_before.ru_stime,'maximum_child_rss_kib':usage_after.ru_maxrss,'scope':'Replay observation only; maximum child high-water RSS is not aggregate process-tree peak memory'}
observed.update(completed=True,returncode=process.returncode,wall_seconds=time.monotonic()-start,completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),head_after=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),status_after=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True),log_sha256=hashlib.sha256((root/'actual-independent-replay.log').read_bytes()).hexdigest())
proof.write_text(json.dumps(observed,indent=2)+'\n')
print(json.dumps(observed))
raise SystemExit(process.returncode)
