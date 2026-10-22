#!/usr/bin/env python3
"""Scoped decoded control-report cap: large valid gzip JSON, no full extraction."""
import contextlib
import gzip
import hashlib
import json
from pathlib import Path
import unittest

import controls

ROOT=Path(__file__).resolve().parent
BIG=ROOT/'controls-cap-fixture-65mib.json.gz'
SMALL=ROOT/'controls-cap-fixture-small.json.gz'
ACTUAL_CHAIN=ROOT/'chain-wrapper-cap-fixture-actual-expanded.json.gz'
PAYLOAD=65*1024*1024


def hashes(path):
 def one(encoded):
  h=hashlib.sha256();length=0
  with path.open('rb') as raw:
   with (gzip.GzipFile(fileobj=raw) if encoded else contextlib.nullcontext(raw)) as source:
    for chunk in iter(lambda:source.read(1<<20),b''):
     h.update(chunk);length+=len(chunk)
  return h.hexdigest(),length
 return one(False),one(True)


class Store:
 artifact=''
 def __init__(self,large_tests=False,oversized=False):
  self.paths={}
  self.records=[]
  for folder in ('revision-chain-tests-original','revision-chain-tests-expanded',
                 'revision-chain-controls-original','revision-chain-controls-expanded'):
   member=folder+'/summary.json.gz'
   path=(BIG if 'controls' in folder else ACTUAL_CHAIN if large_tests and folder=='revision-chain-tests-expanded' else SMALL)
   self.paths[member]=path
   compressed,decoded=hashes(path)
   self.records.append(dict(path=member,sha256=compressed[0],bytes=compressed[1],
                           uncompressed_path=member[:-3],uncompressed_sha256=decoded[0],
                           uncompressed_bytes=(512*1024*1024+1 if (oversized is True and 'controls-original' in folder) or (oversized=='chain' and 'tests-expanded' in folder) else decoded[1])))
  self.members=set(self.paths)|{'revision-control-archive.json'}
 def join(self,*parts):return '/'.join(str(x).strip('/') for x in parts if str(x).strip('/'))
 def map(self,path):return path
 def json(self,path):
  assert path=='revision-control-archive.json'
  return self.records
 def stream_hash(self,member,gzip_encoded=False):return hashes(self.paths[member])[1 if gzip_encoded else 0]
 @contextlib.contextmanager
 def open(self,member):
  with self.paths[member].open('rb') as f:yield f


class ControlCapTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not BIG.exists():
   with BIG.open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as f:
    f.write(b'{"payload":"')
    for _ in range(65):f.write(b'x'*(1024*1024))
    f.write(b'"}')
  if not SMALL.exists():
   with SMALL.open('wb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as f:f.write(b'{}')
 def test_control_report_decodes_valid_json_above_generic64mib(self):
  store=Store()
  value=controls._report(store,'revision-chain-controls-original/summary.json.gz')
  self.assertEqual(len(value['payload']),PAYLOAD)
 def test_manifest_accepts_large_control_reports(self):
  observed=controls._manifest(Store())
  self.assertEqual(len(observed),4)
 def test_actual_expanded_chain_wrapper_above64mib_is_valid(self):
  self.assertGreater(hashes(ACTUAL_CHAIN)[1][1],64*1024*1024)
  self.assertEqual(len(controls._manifest(Store(large_tests=True))),4)
 def test_chain_descriptor_above512mib_refuses(self):
  with self.assertRaises(ValueError):controls._manifest(Store(oversized='chain'))
 def test_control_descriptor_above512mib_refuses(self):
  with self.assertRaises(ValueError):controls._manifest(Store(oversized=True))


if __name__=='__main__':unittest.main(verbosity=2)
