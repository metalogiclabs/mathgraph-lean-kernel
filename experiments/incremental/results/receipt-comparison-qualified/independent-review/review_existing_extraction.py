#!/usr/bin/env python3
"""Run the frozen sibling reviewer against its one existing extraction.

CLI is identical to review_receipt_comparison.py. Every extracted byte is
checked against the provider-SHA-bound ZIP; no extraction/copy is performed.
"""
import importlib.util, zipfile
from pathlib import Path, PurePosixPath
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('receipt_review',HERE/'review_receipt_comparison.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def existing(archive,destination,c):
 destination=Path(destination)
 c.need('reuse:existing extraction',destination.is_dir())
 with zipfile.ZipFile(archive) as z:
  c.eq('reuse:CRC',z.testzip(),None)
  c.eq('reuse:unique members',len(z.namelist()),len(set(z.namelist())))
  expected=set()
  for info in z.infolist():
   name=PurePosixPath(info.filename)
   c.need('reuse:safe member',not name.is_absolute() and '..' not in name.parts and ((info.external_attr>>16)&0o170000)!=0o120000)
   if info.is_dir():continue
   expected.add(info.filename);p=destination/Path(info.filename)
   c.eq('reuse:actual member bytes',p.stat().st_size,info.file_size)
   c.eq('reuse:actual member SHA',m.file_sha(p),m.sha(z.read(info)))
  actual={str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()}
  c.eq('reuse:exact files',actual,expected)
 roots=list(destination.rglob('ci-observations.json'))
 c.eq('reuse:single evidence root',len(roots),1)
 return roots[0].parent
m.archive_extract=existing
if __name__=='__main__':m.main()
