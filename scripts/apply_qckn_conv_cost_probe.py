#!/usr/bin/env python3
"""Add an instrumentation-only wrapper. All original checking obligations remain."""
from pathlib import Path


def replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise ValueError(f'{label}: expected one exact anchor, got {text.count(old)}')
    return text.replace(old,new,1)


def apply(root):
    root=Path(root)
    paths={name:root/'src'/name for name in ['conv.rs','infer.rs','tc.rs']}
    source={name:p.read_text() for name,p in paths.items()}
    anchor='''    pub(crate) fn conv_types_at(&mut self, depth: u32, a: V<'t>, b: V<'t>) -> bool {
        self.unbudgeted(|s| s.unify::<true>(depth, a, b))
    }
'''
    wrapper='''
    pub(crate) fn conv_types_at_app_cost(&mut self, depth: u32, a: V<'t>, b: V<'t>) -> bool {
        let guard = qckn_cost_probe::begin();
        if !guard.sampled {
            return self.conv_types_at(depth, a, b);
        }
        let raw = qckn_cost_probe::raw_tag(a, b);
        // Same order as conv_types_at -> unbudgeted -> unify: force, identity, general.
        self.unbudgeted(|s| {
            let t0 = std::time::Instant::now();
            let x = s.force_thunk(depth, a);
            let y = s.force_thunk(depth, b);
            let force_ns = t0.elapsed().as_nanos() as u64;
            // Classification is outside both timed intervals and makes no decisions.
            let shape = qckn_cost_probe::shape(x, y);
            let t1 = std::time::Instant::now();
            let result = if std::ptr::eq(x, y) { true }
                else { s.unify_general::<true>(depth, x, y) };
            let compare_ns = t1.elapsed().as_nanos() as u64;
            qckn_cost_probe::record(shape, raw, force_ns, compare_ns);
            result
        })
    }
'''
    source['conv.rs']=replace_once(source['conv.rs'],anchor,anchor+wrapper,'conv entry')
    source['conv.rs']+='\n'+Path(__file__).with_name('qckn_conv_cost_probe.rs').read_text()
    source['conv.rs']+='\npub(crate) fn report_app_cost_probe() { qckn_cost_probe::report(); }\n'
    old='''                assert!(self.conv_types_at(depth, domain, arg_ty), "app arg def_eq failed");'''
    new='''                assert!(self.conv_types_at_app_cost(depth, domain, arg_ty), "app arg def_eq failed");'''
    source['infer.rs']=replace_once(source['infer.rs'],old,new,'app conversion only')
    old='''.spawn_scoped(sco, || self.run_session((0, total), || None))'''
    new='''.spawn_scoped(sco, || {
                    let result = self.run_session((0, total), || None);
                    crate::conv::report_app_cost_probe();
                    result
                })'''
    source['tc.rs']=replace_once(source['tc.rs'],old,new,'serial worker report')
    # Stage all modifications only after every anchor has matched.
    for name,path in paths.items():path.write_text(source[name])
    print('QCKN_CONV_COST_PROBE_PATCH_PASS')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('root');apply(p.parse_args().root)
