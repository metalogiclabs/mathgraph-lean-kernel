#!/usr/bin/env python3
"""Install the retained v61 rules into a pinned upstream representation.

The candidate representation comes from the independently authored upstream
commit. This installer is not a proof of semantic equivalence or a release gate.
"""
from pathlib import Path
import hashlib
import sys

UPSTREAM = 'ceaabb593e830dd318bfefd1675be3142fad8eb7'
RAW = '7b51784fe4ec9b82bf7a20c71ba6bf803a4ed7c0'
BLOBS = {
    'upstream': {'src/eval.rs':'0e96b06f2b8a3ad82a101483c877fb931f041852',
                 'src/relevance.rs':'970cc1af78c2741dbfcd2cf6aa6b31f86c9eaf98'},
    'raw': {'src/eval.rs':'3cefb018d461315d62a900e7347b02cfd0271d55',
            'src/relevance.rs':'970cc1af78c2741dbfcd2cf6aa6b31f86c9eaf98'},
}

def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def install(root, variant='upstream'):
    root=Path(root)
    for name, expected in BLOBS[variant].items():
        assert blob((root/name).read_bytes()) == expected, name+': pinned source mismatch'
    p=root/'src/eval.rs'; s=p.read_text()
    old="    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if let Some(r) = self.store_lookup(depth, v) {"
    new="    pub(crate) fn force_all(&mut self, depth: u32, v: V<'t>) -> V<'t> {\n        if matches!(v, Value::Pi { .. }) { return v; }\n        if let Some(r) = self.store_lookup(depth, v) {"
    assert s.count(old)==1
    p.write_text(s.replace(old,new))
    p=root/'src/relevance.rs'; s=p.read_text()
    old='''                for k in (0..n).rev() {
                    let Some(s) = dom[k] else { break };
                    let im = self.ctx.imax(s, r);
                    r = self.ctx.simplify(im);
                    result_known |= 1u64 << k;
                    if self.ctx.is_zero(r) {
                        prop_result |= 1u64 << k;
                    }
                }
'''
    assert s.count(old)==1
    p.write_text(s.replace(old,'                let _ = r;\n'))
    if variant=='upstream':
        fields=(root/'src/value.rs').read_text().split('pub enum Value',1)[1].split('impl<',1)[0]
        assert 'binder_name:' not in fields and 'binder_style:' not in fields
    print('V90_SOURCE_GUARD=PASS')
    print('V90_RETAINED_V61_RULES=PASS')
    print('V90_VARIANT='+variant)

if __name__=='__main__':
    install(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else 'upstream')
