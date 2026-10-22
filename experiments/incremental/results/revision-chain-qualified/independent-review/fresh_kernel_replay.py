#!/usr/bin/env python3
"""Fresh independent kernels on exact published exports; no cache/issuer imports."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import tempfile
import time
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def classify(code, timed_out):
    return ('TIMEOUT' if timed_out else 'ACCEPTED' if code == 0 else
            'REJECTED' if code == 1 else 'UNSUPPORTED' if code == 2 else
            'SIGNAL' if code is not None and code < 0 else 'CHECKER_FAILURE')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('artifact','inputs','repo','rust','cpp','paranoid','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source',required=True)
    p.add_argument('--timeout',type=int,default=300)
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    report=dict(schema='mathgraph.revision-chain-independent-fresh-kernels.v1',
                source_sha=args.source,completed=False,passed=False,inputs=[],
                historical_hmac_reauthenticated=False,
                host=list(platform.uname()),
                scope='Fresh full Rust and pinned normal/paranoid C++ on exact artifact export bytes; no incremental engine or cache authority.')
    def save():
        (args.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    repo=args.repo.resolve()
    pins=json.loads(subprocess.check_output(['git','show',args.source+':experiments/incremental/pins.json'],cwd=repo))
    binaries={k:getattr(args,k).resolve() for k in ('rust','cpp','paranoid')}
    binary_hashes={k:sha(v.read_bytes()) for k,v in binaries.items()}
    require(binary_hashes['cpp']==pins['lean_release_binaries_sha256']['leanchecker'],'normal C++ pin mismatch')
    require(binary_hashes['paranoid']==pins['lean_release_binaries_sha256']['leanchecker-paranoid'],'paranoid C++ pin mismatch')
    report['binary_sha256']=binary_hashes
    report['rust_source_scope']='Locally built exact research source; historical CI binary equality is not assumed.'
    require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==args.source,
            'fresh replay requires checkout of exact qualified source')
    require(not subprocess.check_output(['git','status','--porcelain','--','src','Cargo.toml','Cargo.lock'],cwd=repo,text=True).strip(),
            'fresh Rust sources are dirty')
    manifest=json.loads(args.inputs.read_bytes())
    entries=manifest['inputs']
    require(type(entries) is list and entries,'no exact inputs')
    archive=zipfile.ZipFile(args.artifact) if args.artifact.is_file() else None
    def read(member):
        require(type(member) is str and not member.startswith('/') and '..' not in Path(member).parts,
                'invalid artifact member')
        if archive is not None:
            require(len([i for i in archive.infolist() if i.filename==member])==1,'missing or duplicate input member')
            return archive.read(member)
        target=(args.artifact/member).resolve()
        require(target.is_relative_to(args.artifact.resolve()),'input outside artifact')
        return target.read_bytes()
    try:
        with tempfile.TemporaryDirectory(prefix='independent-kernel-replay-') as private:
            temp=Path(private)
            seen=set()
            for entry in entries:
                identity=entry['sha256']
                require(identity not in seen,'duplicate input identity')
                seen.add(identity)
                require(entry['expected_returncode'] in (0,1) and type(entry['expected_returncode']) is int,'invalid oracle expectation')
                stored=read(entry['member'])
                if 'compressed_member_sha256' in entry:
                    require(sha(stored)==entry['compressed_member_sha256'],'compressed input identity mismatch')
                    require(len(stored)==entry['compressed_member_bytes'],'compressed input size mismatch')
                raw=gzip.decompress(stored) if entry['encoding']=='gzip' else stored
                require(sha(raw)==identity and len(raw)==entry['bytes'],'exact input identity/size mismatch')
                snapshot=temp/'current.ndjson'
                snapshot.write_bytes(raw);snapshot.chmod(0o444)
                config=temp/'config.json'
                config.write_text(json.dumps(dict(export_file_path=str(snapshot),use_stdin=False,
                    permitted_axioms=['propext','Classical.choice','Quot.sound'],unpermitted_axiom_hard_error=True,
                    num_threads=1,nat_extension=True,string_extension=True,print_success_message=True)))
                input_folder=args.out/identity;input_folder.mkdir()
                (input_folder/'config.json').write_bytes(config.read_bytes())
                observation=dict(input=entry,config_sha256=sha(config.read_bytes()),oracles={})
                report['inputs'].append(observation)
                for label,binary in binaries.items():
                    command=[str(binary),str(config)] if label=='rust' else [str(binary),'--from-export',str(snapshot)]
                    before=resource.getrusage(resource.RUSAGE_CHILDREN);tick=time.perf_counter()
                    try:
                        result=subprocess.run(command,capture_output=True,timeout=args.timeout)
                        code,out,err,timed_out=result.returncode,result.stdout,result.stderr,False
                    except subprocess.TimeoutExpired as failure:
                        code,out,err,timed_out=None,failure.stdout or b'',failure.stderr or b'',True
                    wall=time.perf_counter()-tick;after=resource.getrusage(resource.RUSAGE_CHILDREN)
                    folder=args.out/identity/label;folder.mkdir(parents=True)
                    (folder/'stdout').write_bytes(out);(folder/'stderr').write_bytes(err)
                    observation['oracles'][label]=dict(command=command,returncode=code,timed_out=timed_out,
                        verdict=classify(code,timed_out),wall_seconds=wall,
                        completed_child_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                        stdout_sha256=sha(out),stderr_sha256=sha(err),input_sha256=sha(snapshot.read_bytes()),
                        input_bytes=snapshot.stat().st_size)
                    save()
                    require(code==entry['expected_returncode'] and not timed_out,'independent kernel verdict mismatch: '+label+' '+identity)
                    require(sha(snapshot.read_bytes())==identity,'fresh input changed during checking')
                snapshot.chmod(0o644)
                print(json.dumps(dict(input_sha256=identity,expected=entry['expected_returncode'],kernels=3,passed=True)),flush=True)
        require({k:sha(v.read_bytes()) for k,v in binaries.items()}==binary_hashes,'executed binary changed')
        report.update(completed=True,passed=True,unique_inputs=len(entries),real_kernel_processes=3*len(entries),
                      acceptance_rejection_agreement=True)
        save()
    except Exception as error:
        report['failure']=repr(error);save();raise
    finally:
        if archive is not None:archive.close()


if __name__=='__main__':main()
