#!/usr/bin/env python3
"""Stream one exact provider ZIP into existing 48 MiB XZ evidence-part format.

Lossless evidence storage only. No runtime verification or speedup claim.
The unchanged prior reconstruct_archive.verify_parts performs both replay checks.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import stat
import time
import zipfile

from reconstruct_archive import verify_parts

BLOCK=1<<20
PART_BYTES=48<<20


def require(value,message):
    if not value:
        raise ValueError(message)


def source_stat(path):
    value=path.lstat()
    require(stat.S_ISREG(value.st_mode),'input ZIP must be a regular file')
    return {key:getattr(value,key) for key in ('st_dev','st_ino','st_nlink','st_size','st_mode','st_uid','st_gid','st_mtime_ns','st_ctime_ns')}


def identity(path):
    with path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'bytes':path.stat().st_size,'sha256':digest}


def write_json(path,value):
    temp=path.with_name(path.name+'.tmp')
    with temp.open('x') as output:
        json.dump(value,output,indent=2,sort_keys=True)
        output.write('\n');output.flush();os.fsync(output.fileno())
    os.replace(temp,path)
    directory=os.open(path.parent,os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)


class PartWriter:
    def __init__(self,out):
        self.out=out;self.parts=[];self.handle=None
        self.whole=hashlib.sha256();self.total=0
        self.part_hash=None;self.part_bytes=0
    def emit(self,raw):
        self.whole.update(raw);self.total+=len(raw)
        while raw:
            if self.handle is None:
                index=len(self.parts)
                name='archive.zip.xz.part'+str(index).zfill(3)
                self.handle=(self.out/name).open('xb')
                self.parts.append({'index':index,'name':name})
                self.part_hash=hashlib.sha256();self.part_bytes=0
            chunk,raw=raw[:PART_BYTES-self.part_bytes],raw[PART_BYTES-self.part_bytes:]
            self.handle.write(chunk);self.part_hash.update(chunk);self.part_bytes+=len(chunk)
            if self.part_bytes==PART_BYTES:self.finish()
    def finish(self):
        if self.handle is None:return
        self.handle.flush();os.fsync(self.handle.fileno());self.handle.close();self.handle=None
        self.parts[-1].update(bytes=self.part_bytes,sha256=self.part_hash.hexdigest())
    def abort(self):
        if self.handle is not None:self.handle.close();self.handle=None


def package_zip(*,input_zip,expected_size,expected_sha256,source,run_id,artifact_id,out,
                keep_reconstructed=False,preset=3):
    input_zip=Path(input_zip);out=Path(out)
    started=time.perf_counter()
    require(type(expected_size) is int and expected_size>0,'invalid expected byte count')
    require(re.fullmatch('[0-9a-f]{64}',expected_sha256),'expected exact SHA256 required')
    require(re.fullmatch('[0-9a-f]{40}',source),'expected exact source SHA required')
    require(type(run_id) is int and run_id>0 and type(artifact_id) is int and artifact_id>0,'invalid run/artifact IDs')
    before=source_stat(input_zip)
    expected={'bytes':expected_size,'sha256':expected_sha256}
    require(before['st_size']==expected_size,'input ZIP expected size mismatch')
    require(identity(input_zip)==expected,'input ZIP expected SHA256 mismatch')
    with zipfile.ZipFile(input_zip) as archive:
        require(archive.testzip() is None,'input ZIP member CRC failure')
        members=len(archive.infolist())
    require(not out.exists(),'output directory already exists')
    out.mkdir(mode=0o700)
    original_hash=hashlib.sha256();original_bytes=0
    compressor=lzma.LZMACompressor(format=lzma.FORMAT_XZ,check=lzma.CHECK_CRC64,preset=preset)
    writer=PartWriter(out)
    try:
        with input_zip.open('rb') as stream:
            for raw in iter(lambda:stream.read(BLOCK),b''):
                original_hash.update(raw);original_bytes+=len(raw)
                writer.emit(compressor.compress(raw))
        writer.emit(compressor.flush());writer.finish()
    except BaseException:
        writer.abort();raise
    require({'bytes':original_bytes,'sha256':original_hash.hexdigest()}==expected,'input ZIP changed during compression')
    require(source_stat(input_zip)==before,'input ZIP metadata changed during compression')
    require(writer.parts and all(0<p['bytes']<=PART_BYTES for p in writer.parts),'invalid wrapper part sizes')
    require(all(p['bytes']==PART_BYTES for p in writer.parts[:-1]),'short intermediate wrapper part')
    manifest={'schema':'mathgraph.lossless-xz-evidence-parts.v1',
              'purpose':'Lossless exact provider ZIP evidence storage only; not runtime performance evidence.',
              'created_at_utc':datetime.now(timezone.utc).isoformat(),
              'qualified_source':source,'qualification_run':run_id,'original_artifact_id':artifact_id,
              'original':dict(name=input_zip.name,source_path=str(input_zip),**expected),
              'original_stat_before':before,'input_zip_crc_checked':True,'input_zip_members':members,
              'wrapper':{'name':'archive.zip.xz','bytes':writer.total,'sha256':writer.whole.hexdigest(),
                         'format':'XZ','check':'CRC64','materialized_separately':False},
              'compression':{'implementation':'Python stdlib lzma.LZMACompressor','preset':preset,'streamed_directly_to_parts':True},
              'part_bytes':PART_BYTES,'part_count':len(writer.parts),'parts':writer.parts}
    manifest_path=out/'manifest.json'
    write_json(manifest_path,manifest)
    streamed=verify_parts(manifest_path)
    require(streamed['passed'],'unchanged stream replay failed')
    replay=out/'exclusive-verified-original.zip'
    reconstructed=verify_parts(manifest_path,replay)
    require(reconstructed['passed'] and reconstructed['zip_crc_checked'] and reconstructed['written_output_sha256_verified'],
            'unchanged exclusive reconstruction/CRC replay failed')
    require(identity(replay)==expected,'exclusive reconstruction readback mismatch')
    require(source_stat(input_zip)==before and identity(input_zip)==expected,'input ZIP changed during packaging/replay')
    manifest.update(parts_concatenation_and_stream_decompression_verification=streamed,
                    exclusive_zip_reconstruction_and_crc_verification=reconstructed,
                    original_file_unchanged_after_all_verification=True,
                    total_packaging_and_verification_wall_seconds=time.perf_counter()-started,
                    reconstructed_verification_duplicate_retained=keep_reconstructed,
                    transport_files_deleted=[])
    if not keep_reconstructed:
        # This path was created exclusively by verify_parts in this operation.
        # Never delete or move the original provider ZIP or prior evidence.
        require(identity(replay)==expected,'verification duplicate changed before cleanup')
        replay.unlink()
        manifest['verification_duplicate_deleted_after_exact_readback']=True
    write_json(manifest_path,manifest)
    require(json.loads(manifest_path.read_text())==manifest,'persisted part manifest mismatch')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path,dest='input_zip')
    parser.add_argument('--expected-size',required=True,type=int)
    parser.add_argument('--expected-sha256',required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--run-id',required=True,type=int)
    parser.add_argument('--artifact-id',required=True,type=int)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--keep-reconstructed',action='store_true')
    args=parser.parse_args()
    print(json.dumps(package_zip(**vars(args)),indent=2))


if __name__=='__main__':main()
