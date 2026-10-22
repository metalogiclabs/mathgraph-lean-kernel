Completed independent-reader output preservation
==============================================

These local tools package evidence losslessly. Their compression time, size,
and replay cost make no runtime performance or speedup claim.

Current completed local status (2026-10-22): the actual reader output was
archived to actual-independent-replay-preserved and independently verified.
All original actual-independent-replay files are RETAINED. Root explicitly
directed that no actual reader-output removal is needed or authorized now.
No production removal command has been run. See that bundle's
retention-status.json, manifest.json, archive-proof.json and independent-proof.json.
The dormant removal interface below requires a future explicit instruction;
its presence does not authorize deleting the retained original reader output.

Production archive/removal scope is ONLY:
  /workspace/kernel-audit/authenticated-state/actual-independent-replay
Parent execution JSON/log/resource files remain outside that scope.
The archive command has no source-path argument and never removes source.
It requires completed=true, passed=true, exact CEC source identity, 800 primary
transitions and 108 fresh kernel processes in summary.json, plus the completed
successful matching external reader execution proof. If actual qualified
counts differ, stop and investigate; do not weaken the completion gate.

Output is one standard lossless CRC64 XZ stream containing a PAX tar, written
directly into ordered parts of at most 48 MiB. There is no duplicate full XZ
file. The manifest records every part and the concatenated compressed stream
SHA-256/length, every source path, regular/hardlinked file SHA-256/length,
mode/uid/gid/nanosecond mtime/ctime, and hardlink identity. Symlinks, special
files, and hardlinks to outside this source tree are refused. All byte-bearing
members are fully read back and every logical member is covered. Original
source hashes/metadata are checked before and after. Parts are durable before
the manifest/proof is written. Both paths and existing outputs are guarded.

After the actual reader has completed successfully, choose a fresh output
directory outside the reader tree. This exact example has already completed
locally; repeating it refuses to overwrite the existing preserved bundle:

  python3 -B archive_reader_output.py archive \
    --destination /workspace/kernel-audit/authenticated-state/actual-independent-replay-preserved

Independently verify every part/member against all original source paths:

  python3 -B verify_reader_archive.py \
    --manifest /workspace/kernel-audit/authenticated-state/actual-independent-replay-preserved/manifest.json \
    --source /workspace/kernel-audit/authenticated-state/actual-independent-replay \
    --proof /workspace/kernel-audit/authenticated-state/actual-independent-replay-preserved/independent-proof.json

Do not remove the source merely because archive creation succeeded. Root must
review both complete proofs and the original reader proof, and explicitly
create its own root-removal-proof.json with these exact fields:

  schema: mathgraph.reader-output-root-removal-authorization.v1
  status: passed
  source_root: /workspace/kernel-audit/authenticated-state/actual-independent-replay
  source_sha: cec99419a0bcd9df70ccb55bc9dc9ebbf3bfe5c5
  manifest_sha256: SHA-256 of the exact manifest.json
  reader_execution_sha256: SHA-256 of actual-independent-replay-execution.json
  independent_proof_sha256: SHA-256 of independent-proof.json

Only then may root separately request the explicit removal command:

  python3 -B archive_reader_output.py remove \
    --manifest /workspace/kernel-audit/authenticated-state/actual-independent-replay-preserved/manifest.json \
    --independent-proof /workspace/kernel-audit/authenticated-state/actual-independent-replay-preserved/independent-proof.json \
    --root-proof /absolute/path/root-removal-proof.json

This repeats complete archive/source readback, validates proof hashes and
checks all originals before deleting only the fixed production source root.
It writes removal-proof.json with the observed disk free-space change.
Creation/verification failures leave originals in place and retain partial
new packaging files for diagnosis. No existing outputs are overwritten.

Portable restoration (fresh destination only)
-------------------------------------------
Keep manifest.json and all named parts together. A standard Python 3 install
can check and concatenate them without any workspace-specific path:

  python3 -B - MANIFEST.json FRESH-reader-output.tar.xz <<'PY'
  import hashlib,json,pathlib,sys
  manifest_path=pathlib.Path(sys.argv[1]); m=json.loads(manifest_path.read_bytes())
  h=hashlib.sha256(); total=0
  with pathlib.Path(sys.argv[2]).open('xb') as output:
      for part in m['parts']:
          name=part['name']
          if pathlib.PurePosixPath(name).name != name or name in ('.','..'):
              raise ValueError('unsafe part name')
          ph=hashlib.sha256(); size=0
          with (manifest_path.parent/name).open('rb') as source:
              while block:=source.read(1048576):
                  ph.update(block); h.update(block); size+=len(block); total+=len(block)
                  output.write(block)
          if (size,ph.hexdigest())!=(part['size'],part['sha256']):
              raise ValueError('part length/hash mismatch')
      if (total,h.hexdigest())!=(m['archive']['size'],m['archive']['sha256']):
          raise ValueError('whole archive length/hash mismatch')
  PY

  xz --test FRESH-reader-output.tar.xz
  mkdir FRESH-restore-directory
  tar -xJpf FRESH-reader-output.tar.xz -C FRESH-restore-directory

This reproduces file bytes, modes, timestamps and in-tree hardlinks. The tar
retains archived uid/gid; restoring ownership needs appropriate privileges.
Original ctime/device/inode values are recorded as evidence, rather than
promised as assignable filesystem state on a new machine. Use Python with
lzma/tarfile if system xz/tar is unavailable. Preserve a failed partial fresh
reconstruction for inspection, then choose another fresh output on retry.

Fixture-only validation
-----------------------
  python3 -B test_reader_preservation.py

Tests use temporary tiny fixtures under this helper directory. They do not
archive, verify, modify, or delete the production reader output.
