#!/usr/bin/env python3
"""Prove that removing the v88 intervention restores the frozen checker."""
import hashlib
import json
import shutil
import sys
from pathlib import Path
from patch_prune_dm_v88 import BASE, NEEDLE, REPLACEMENT, blob, transform

BASE_COMMIT = '08ddb26718c86213262943ca19ae8cf1b03fa922'
TEST_SUFFIX = b'mod prune_dm_v88;\n'

def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}

def verify(root):
    root = Path(root)
    control = tree(root / 'control')
    candidate = tree(root / 'candidate')
    assert blob(control['src/util.rs']) == BASE
    original = control['src/util.rs'].decode()
    expected = transform(original).encode()
    assert candidate['src/util.rs'] == expected, 'unexpected production change'
    restored = dict(candidate)
    restored['src/util.rs'] = expected.replace(REPLACEMENT.encode(), NEEDLE.encode())
    assert restored['src/util.rs'] == control['src/util.rs']
    assert restored['src/tests.rs'].endswith(TEST_SUFFIX)
    restored['src/tests.rs'] = restored['src/tests.rs'][:-len(TEST_SUFFIX)]
    assert blob(restored['src/tests.rs']) == '2ddc1124db83fee44b2fec9a4b3cb4e5e23f5cfc'
    assert 'src/tests/prune_dm_v88.rs' in restored
    del restored['src/tests/prune_dm_v88.rs']
    assert restored == control, 'ablation does not restore the complete frozen source tree'
    def digest(files):
        h = hashlib.sha256()
        for name, data in sorted(files.items()):
            h.update(name.encode() + b'\0' + str(len(data)).encode() + b'\0' + data)
        return h.hexdigest()
    result = {'base': BASE_COMMIT, 'source_ablation': 'EXACT',
              'control_is_ablated_candidate': True,
              'control_tree_sha256': digest(control),
              'restored_tree_sha256': digest(restored),
              'candidate_tree_sha256': digest(candidate),
              'production_patch_sha256': hashlib.sha256(expected).hexdigest(),
              'release_promoted': False}
    (root / 'out' / 'ablation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result

if __name__ == '__main__':
    verify(sys.argv[1])
    print('V89_EXACT_SOURCE_ABLATION=PASS')
    print('V89_CONTROL_IS_ABLATION=PASS')
