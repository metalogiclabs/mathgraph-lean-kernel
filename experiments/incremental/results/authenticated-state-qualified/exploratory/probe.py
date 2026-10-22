#!/usr/bin/env python3
"""Local exploratory equal-cone real-kernel probe. Not CI qualification."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

REPO=Path('/workspace/mathgraph-lean-kernel-lifecycle')
sys.path.insert(0,str(REPO/'experiments/incremental'))
import engine
from authenticated_state import StateChainSession
from producer_delta import sources_at
from qualify_delta import configuration, independent_partition, audit_partition

ROOT=Path(__file__).parent
EXPECTED='cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5'
OLD=Path('/workspace/mathgraph-lean-kernel/target/release')
FRESH=Path('/workspace/kernel-audit/authenticated-state/independent-build/target/release')
PRODUCER=Path('/workspace/kernel-audit/revision-lifecycle/producer-build/delta-producer')
PROFILES={'original3436':Path('/workspace/kernel-audit/workloads-final'),
          'expanded11653':Path('/workspace/kernel-audit/delta-expanded-workloads-first')}
FILE='IncrementalWorkload/Leaves.lean'
NAME='IncrementalWorkload.leaf'
A='theorem leaf (n : Nat) : n = n := Eq.refl n'
B='theorem leaf (n : Nat) : n = n := (fun h : n = n => h) (Eq.refl n)'

def sha(raw): return hashlib.sha256(raw).hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(engine.encoded(value))
def archive(raw,kind):
    ident=sha(raw);path=ROOT/'blobs'/(ident+'.'+kind+'.gz')
    path.parent.mkdir(exist_ok=True)
    if not path.exists(): path.write_bytes(gzip.compress(raw,mtime=0))
    assert gzip.decompress(path.read_bytes())==raw
    return dict(path=str(path),sha256=sha(path.read_bytes()),bytes=path.stat().st_size,
                uncompressed_sha256=ident,uncompressed_bytes=len(raw))
def run_fresh(binary,export,path):
    cfg=path/'config.json';write(cfg,configuration(export))
    start=time.perf_counter();cpu=engine.cpu_time()
    p=subprocess.run([str(binary),str(cfg)],capture_output=True,timeout=300,cwd=REPO)
    rec=dict(command=[str(binary),str(cfg)],returncode=p.returncode,
        wall_seconds=time.perf_counter()-start,cpu_seconds=engine.cpu_time()-cpu,
        stdout=archive(p.stdout,'stdout'),stderr=archive(p.stderr,'stderr'))
    assert p.returncode==0,rec
    write(path/'process.json',rec)
    return p.stdout,rec

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pairs',type=int,default=5)
    parser.add_argument('--updates-per-pair',type=int,default=4)
    args=parser.parse_args()
    assert 1<=args.pairs<=5 and args.updates_per_pair in (2,4,6,8,10)
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    assert actual==EXPECTED
    assert subprocess.check_output(['git','status','--porcelain'],cwd=REPO)==b''
    source_files=subprocess.check_output(['git','ls-files','src','Cargo.toml','Cargo.lock'],cwd=REPO,text=True).splitlines()
    before={p:sha((REPO/p).read_bytes()) for p in source_files}
    independent_proof=Path('/workspace/kernel-audit/authenticated-state/independent-build/build-proof.json')
    proof=json.loads(independent_proof.read_bytes())
    assert proof['passed'] and proof['source_sha']==EXPECTED and proof['source_before']==before==proof['source_after']
    # Exact complete Rust source/Cargo closure equals the earlier native build's
    # source revision; only Python/harness files changed since that baseline.
    native_base='b1931f8479a2bcd78af85ba79e60958963f89d96'
    assert subprocess.run(['git','diff','--exit-code',native_base,EXPECTED,'--','src','Cargo.toml','Cargo.lock'],cwd=REPO,capture_output=True).returncode==0
    previous_native=Path('/workspace/kernel-audit/authenticated-state/benchmark-stable-original-v3/summary.json')
    oldpins=json.loads(previous_native.read_bytes())
    assert oldpins['source_sha']==native_base and oldpins['source_and_binary_stable'] is True
    binaries={}
    for binary in [PRODUCER,OLD/'check-selected',OLD/'export-index',OLD/'index-session',
                   OLD/'check-selected-retained-session',FRESH/'sokonanoda',FRESH/'export-index']:
        binaries[str(binary)]=dict(sha256=sha(binary.read_bytes()),bytes=binary.stat().st_size)
    for name,role in [('check-selected','checker'),('export-index','indexer'),('index-session','index_session'),('check-selected-retained-session','retained_checker')]:
        assert binaries[str(OLD/name)]['sha256']==oldpins['binary_sha256'][role]['sha256']
    assert binaries[str(PRODUCER)]['sha256']==oldpins['binary_sha256']['producer']['sha256']
    for name in ('sokonanoda','export-index'):
        assert binaries[str(FRESH/name)]['sha256']==proof['binary_sha256'][name]
    input_before={str(w/'manifest.json'):sha((w/'manifest.json').read_bytes()) for w in PROFILES.values()}
    for w in PROFILES.values():
        for name,text in sources_at(w/'baseline/source').items():
            input_before[str(w/'baseline/source'/name)]=sha(text.encode())
        input_before[str(w/'baseline/export.ndjson')]=sha((w/'baseline/export.ndjson').read_bytes())
    report=dict(schema='mathgraph.local-exploratory.equal-cone.v1',qualified=False,
        scope='LOCAL EXPLORATORY; not CI qualification or performance promotion',passed=False,
        source_sha=actual,probe_source_sha256=sha(Path(__file__).read_bytes()),
        started_unix=time.time(),configuration=vars(args),replacement=dict(file=FILE,name=NAME,before=A,after=B),
        binaries=binaries,source_closure=before,native_source_closure_equal_to=native_base,
        independent_build_proof=dict(path=str(independent_proof),sha256=sha(independent_proof.read_bytes())),
        original_native_build_pins=dict(path=str(previous_native),sha256=sha(previous_native.read_bytes())),
        input_pins=input_before,profiles={},steps=[],
        limitations=['One real leaf theorem and two workload profiles; five local paired groups, no CI qualification.',
          'Warm intervals include real producer/authentication/index/checking/persistence; full independent oracles run afterward.',
          'CPU includes live native procfs counters at clock-tick granularity. Memory observations are cumulative high-water samples, not phase peaks.',
          'No unchangedness, kernel, reuse or HMAC authority is replaced or monkeypatched. Issuer key is ephemeral and unpublished.',
          'Initial admission, explicit complete export, independent full-index and fresh checking are outside warm intervals.',
          'Full source capture remains bounded; imported environment pinned; full per-declaration output/applicability still may visit all declarations.',
          'Temporal pairing cannot eliminate host noise; no asymptotic or constant-cost conclusion.'])
    write(ROOT/'partial.json',report)
    sessions={};indexes={};sources={}
    try:
      with tempfile.TemporaryDirectory(prefix='equal-cone-issuer-') as private:
        key=Path(private)/'key';key.write_bytes(os.urandom(32));key.chmod(0o600)
        for profile,w in PROFILES.items():
            source=ROOT/profile/'source'
            for name,text in sources_at(w/'baseline/source').items():
                p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            sources[profile]=source
            session=StateChainSession(root=ROOT/profile/'session',workloads=w,producer=PRODUCER,
                checker=OLD/'check-selected',indexer=OLD/'export-index',index_session=OLD/'index-session',
                authority_key=key,retained_checker=OLD/'check-selected-retained-session')
            sessions[profile]=session;ready=session.start()
            output,index_run=run_fresh(FRESH/'export-index',w/'baseline/export.ndjson',ROOT/profile/'baseline-index')
            index=json.loads(output);assert engine.encoded(index)==engine.encoded(session.old['index'])
            _,kernel_run=run_fresh(FRESH/'sokonanoda',w/'baseline/export.ndjson',ROOT/profile/'baseline-fresh-rust')
            indexes[profile]=index
            report['profiles'][profile]=dict(workloads=str(w),ready=ready,
                count=index['count'],baseline_index=index_run,baseline_fresh_rust=kernel_run,
                baseline_index_sha256=sha(engine.encoded(index)))
            write(ROOT/'partial.json',report)
        # Same 4-step history length and same proof changes per paired group;
        # alternate which profile's group runs first to reduce ordering bias.
        for pair in range(args.pairs):
          profiles=list(PROFILES)
          if pair%2: profiles.reverse()
          for profile in profiles:
            s=sessions[profile];source=sources[profile]
            for local in range(args.updates_per_pair):
                revision=pair*args.updates_per_pair+local+1
                before,after=(A,B) if revision%2 else (B,A)
                p=source/FILE;old=p.read_text();assert old.count(before)==1
                p.write_text(old.replace(before,after))
                tick=time.perf_counter();cpu=s.cpu_time()
                result=s.apply(source,(FILE,before,after),[NAME])
                wall=time.perf_counter()-tick;cpu_elapsed=s.cpu_time()-cpu
                path=ROOT/profile/('revision-%03d'%revision)
                record=dict(pair=pair+1,profile=profile,revision=revision,
                    wall_seconds=wall,cpu_seconds=cpu_elapsed,
                    result=archive(engine.encoded(result),'result'),status=result['status'],
                    counts=result.get('counts'),timings=result.get('timings'),
                    memory=result.get('memory'),native_kernel_report=result.get('native_kernel_report'),
                    typed_update=result.get('typed_update'),representation=result.get('representation'))
                report['steps'].append(record);write(ROOT/'partial.json',report)
                assert result['status']=='VERIFIED',record
                assert result['counts']['scheduled']==1 and result['counts']['rechecked']==1,record
                assert result['native_kernel_report']['checked']==1
                assert result['representation']['full_export_bytes_materialized']==0
                assert result['representation']['full_export_bytes_hashed']==0
                previous=indexes[profile]
                # Actual complete-export materialization and all full oracles
                # occur only after the warm interval above has ended.
                exported=s.materialize_current()
                raw=Path(exported['path']).read_bytes();assert sha(raw)==exported['export_sha256']
                record['materialization']={k:v for k,v in exported.items() if k!='path'}
                output,index_run=run_fresh(FRESH/'export-index',exported['path'],path/'full-index')
                current=json.loads(output)
                assert engine.encoded(current)==engine.encoded(s.old['index'])
                assert current['schedule']==previous['schedule']
                assert current['meta']==previous['meta'] and current['builtins']==previous['builtins'] and current['complex']==previous['complex']
                assert [r['deps'] for r in current['declarations']]==[r['deps'] for r in previous['declarations']]
                selected,reused=independent_partition(previous,current)
                assert len(selected)==1 and current['declarations'][selected[0]]['name']==NAME
                audit=audit_partition(result,previous,current)
                acceptance=s.audit_current_acceptance(current)
                _,kernel_run=run_fresh(FRESH/'sokonanoda',exported['path'],path/'fresh-rust')
                assert sha(Path(exported['path']).read_bytes())==exported['export_sha256']
                record.update(full_index=index_run,fresh_rust=kernel_run,full_index_sha256=sha(engine.encoded(current)),
                    full_index_partition_audit=audit,acceptance_audit=acceptance,
                    selected_index=selected[0],selected_name=NAME,all_dependency_edges_unchanged=True,
                    full_index_exact=True,exact_export_sha256=exported['export_sha256'])
                indexes[profile]=current
                write(ROOT/'partial.json',report)
                print(json.dumps(dict(profile=profile,revision=revision,wall=wall,
                    counts=result['counts'],full_index_exact=True,fresh_rust=kernel_run['returncode'])),flush=True)
        report['pairs']=[]
        for pair in range(1,args.pairs+1):
            row={'pair':pair,'profiles':{}}
            for profile in PROFILES:
                steps=[s for s in report['steps'] if s['pair']==pair and s['profile']==profile]
                metrics={name:statistics.mean(s[name] for s in steps) for name in ('wall_seconds','cpu_seconds')}
                metrics['phases']={k:statistics.mean(s['timings'][k] for s in steps)
                    for k in steps[0]['timings'] if k.endswith('_seconds') and isinstance(steps[0]['timings'][k],(int,float))}
                row['profiles'][profile]=metrics
            row['expanded_over_original_wall']=row['profiles']['expanded11653']['wall_seconds']/row['profiles']['original3436']['wall_seconds']
            row['expanded_over_original_cpu']=row['profiles']['expanded11653']['cpu_seconds']/row['profiles']['original3436']['cpu_seconds']
            report['pairs'].append(row)
        report['summary']={}
        for profile in PROFILES:
            report['summary'][profile]={k:statistics.median(row['profiles'][profile][k] for row in report['pairs']) for k in ('wall_seconds','cpu_seconds')}
            report['summary'][profile]['phases']={k:statistics.median(row['profiles'][profile]['phases'][k] for row in report['pairs'])
                for k in report['pairs'][0]['profiles'][profile]['phases']}
        report['summary']['expanded_over_original_wall']=report['summary']['expanded11653']['wall_seconds']/report['summary']['original3436']['wall_seconds']
        report['summary']['expanded_over_original_cpu']=report['summary']['expanded11653']['cpu_seconds']/report['summary']['original3436']['cpu_seconds']
        report['passed']=True
    except BaseException as error:
        report['failure']=dict(type=type(error).__name__,reason=str(error));raise
    finally:
        for session in sessions.values(): session.close()
        report['finished_unix']=time.time()
        report['input_pins_unchanged']=all(sha(Path(p).read_bytes())==identity for p,identity in input_before.items())
        report['source_closure_unchanged']=before=={p:sha((REPO/p).read_bytes()) for p in source_files}
        report['source_worktree_clean']=subprocess.check_output(['git','status','--porcelain'],cwd=REPO)==b''
        write(ROOT/'summary.json',report)
    assert report['passed'] and report['input_pins_unchanged'] and report['source_closure_unchanged'] and report['source_worktree_clean']

if __name__=='__main__': main()
