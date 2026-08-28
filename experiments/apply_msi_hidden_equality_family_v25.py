from pathlib import Path

p=Path('src/conv.rs')
s=p.read_text()
anchor="use crate::value::{self, ElimView, Env, RigidHead, Spine, UnfoldHead, Value, E, S, V};\n"
assert anchor in s
s=s.replace(anchor,anchor+r'''
use std::sync::atomic::{AtomicU64, Ordering::Relaxed};

static D_TOTAL: AtomicU64 = AtomicU64::new(0);
static D_RAW_EQ_FAM: [AtomicU64; 9] = [const { AtomicU64::new(0) }; 9];
static D_POST_EQ_FAM: [AtomicU64; 9] = [const { AtomicU64::new(0) }; 9];

#[inline]
fn d_fam(x: V<'_>, y: V<'_>) -> usize {
    match (x,y) {
        (Value::Sort {..}, Value::Sort {..}) => 0,
        (Value::NatLit {..}, Value::NatLit {..}) => 1,
        (Value::StrLit {..}, Value::StrLit {..}) => 2,
        (Value::Rigid {..}, Value::Rigid {..}) => 3,
        (Value::Unfold {..}, Value::Unfold {..}) => 4,
        (Value::Pi {..}, Value::Pi {..}) => 5,
        (Value::Lam {..}, Value::Lam {..}) => 6,
        (Value::Thunk {..}, Value::Thunk {..}) => 7,
        _ => 8,
    }
}

fn d_report(n:u64) {
    let raw: Vec<u64> = D_RAW_EQ_FAM.iter().map(|x| x.load(Relaxed)).collect();
    let post: Vec<u64> = D_POST_EQ_FAM.iter().map(|x| x.load(Relaxed)).collect();
    eprintln!("MSI_HIDDEN_FAM total={} raw_sort={} raw_nat={} raw_str={} raw_rigid={} raw_unfold={} raw_pi={} raw_lam={} raw_thunk={} raw_other={} post_sort={} post_nat={} post_str={} post_rigid={} post_unfold={} post_pi={} post_lam={} post_thunk={} post_other={}",
        n,raw[0],raw[1],raw[2],raw[3],raw[4],raw[5],raw[6],raw[7],raw[8],post[0],post[1],post[2],post[3],post[4],post[5],post[6],post[7],post[8]);
}
''',1)
old=r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            return true;
        }
        self.unify_general::<RIGID>(depth, x, y)
    }
'''
new=r'''    #[inline]
    fn unify<const RIGID: bool>(&mut self, depth: u32, x: V<'t>, y: V<'t>) -> bool {
        let n = D_TOTAL.fetch_add(1, Relaxed) + 1;
        let sampled = (n & 63) == 0;
        if sampled && !std::ptr::eq(x,y) && x.digest() == y.digest() {
            D_RAW_EQ_FAM[d_fam(x,y)].fetch_add(1,Relaxed);
        }
        let x = self.force_thunk(depth, x);
        let y = self.force_thunk(depth, y);
        if std::ptr::eq(x, y) {
            if n == 3_000_000 { d_report(n); }
            return true;
        }
        if sampled && x.digest() == y.digest() {
            D_POST_EQ_FAM[d_fam(x,y)].fetch_add(1,Relaxed);
        }
        let r=self.unify_general::<RIGID>(depth, x, y);
        if n == 3_000_000 { d_report(n); }
        r
    }
'''
assert old in s
p.write_text(s.replace(old,new))
print('applied MSI hidden equality family v25')
