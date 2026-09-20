// Diagnostic-only: sampled, non-overlapping application conversion roots.
// This module never decides whether a conversion is valid.
mod qckn_cost_probe {
    use crate::value::{RigidHead, Value, V};
    use std::cell::RefCell;
    use std::time::Instant;

    const SHAPES: [&str; 12] = ["ptr", "sort_same_level", "sort_distinct_level",
        "rigid_same_short", "rigid_same_long", "rigid_other", "pi_pi",
        "unfold_unfold", "unfold_rigid", "unfold_other", "lam_lam", "other"];
    const RAW: [&str; 4] = ["plain_distinct", "plain_identical", "thunk_distinct", "thunk_identical"];

    #[derive(Clone, Copy, Default)]
    struct Row { samples: u64, force_ns: u64, compare_ns: u64, max_ns: u64 }
    impl Row {
        fn add(&mut self, force: u64, compare: u64) {
            self.samples += 1;
            self.force_ns = self.force_ns.saturating_add(force);
            self.compare_ns = self.compare_ns.saturating_add(compare);
            self.max_ns = self.max_ns.max(force.saturating_add(compare));
        }
    }
    struct Stats {
        seed: u64, rng: u64, depth: u32, roots: u64, nested: u64, samples: u64,
        rows: [Row; 48],
    }
    impl Stats {
        fn new(seed: u64) -> Self {
            Self {seed, rng: seed, depth: 0, roots: 0, nested: 0, samples: 0,
                rows: [Row::default(); 48]}
        }
        fn draw(&mut self) -> bool {
            self.rng = self.rng.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            self.rng >> 54 == 0 // deterministic pseudo-random 1/1024 sampling
        }
    }
    thread_local! {
        static TRACE: RefCell<Stats> = RefCell::new(Stats::new(
            std::env::var("QCKN_COST_SEED").ok().and_then(|s|s.parse().ok()).unwrap_or(17)));
    }
    pub(super) struct Guard { pub(super) sampled: bool }
    impl Drop for Guard {
        fn drop(&mut self) {
            TRACE.with(|s| { let mut s=s.borrow_mut(); debug_assert!(s.depth>0); s.depth-=1; });
        }
    }
    pub(super) fn begin() -> Guard {
        let sampled=TRACE.with(|s| {
            let mut s=s.borrow_mut(); let root=s.depth==0; s.depth+=1;
            if root { s.roots+=1; s.draw() } else { s.nested+=1; false }
        });
        Guard{sampled}
    }
    pub(super) fn raw_tag<'a>(a: V<'a>, b: V<'a>) -> usize {
        usize::from(std::ptr::eq(a,b)) + 2*usize::from(
            matches!(a,Value::Thunk{..}) || matches!(b,Value::Thunk{..}))
    }
    fn same_head<'a>(a: RigidHead<'a>, b: RigidHead<'a>) -> bool {
        match (a,b) {
            (RigidHead::BVar(x,_),RigidHead::BVar(y,_)) => x==y,
            (RigidHead::Axiom(n,l),RigidHead::Axiom(m,k))
            | (RigidHead::Ctor(n,l),RigidHead::Ctor(m,k))
            | (RigidHead::Recursor(n,l),RigidHead::Recursor(m,k))
            | (RigidHead::QuotConst(n,l),RigidHead::QuotConst(m,k))
            | (RigidHead::Inductive(n,l),RigidHead::Inductive(m,k)) => n==m && l==k,
            _ => false,
        }
    }
    pub(super) fn shape<'a>(a: V<'a>, b: V<'a>) -> usize {
        if std::ptr::eq(a,b) {return 0;}
        match (a,b) {
            (Value::Sort{level:x,..},Value::Sort{level:y,..}) => if x==y {1}else{2},
            (Value::Rigid{head:x,spine:s,..},Value::Rigid{head:y,spine:t,..}) if same_head(*x,*y) =>
                if s.len().max(t.len())<=4 {3}else{4},
            (Value::Rigid{..},Value::Rigid{..}) => 5,
            (Value::Pi{..},Value::Pi{..}) => 6,
            (Value::Unfold{..},Value::Unfold{..}) => 7,
            (Value::Unfold{..},Value::Rigid{..}) | (Value::Rigid{..},Value::Unfold{..}) => 8,
            (Value::Unfold{..},_) | (_,Value::Unfold{..}) => 9,
            (Value::Lam{..},Value::Lam{..}) => 10,
            _ => 11,
        }
    }
    pub(super) fn record(shape: usize, raw: usize, force: u64, compare: u64) {
        TRACE.with(|s|{let mut s=s.borrow_mut();s.samples+=1;s.rows[shape*4+raw].add(force,compare);});
    }
    pub(super) fn report() {
        let mut floor=0u64;
        for _ in 0..10000 {let t=Instant::now();floor+=t.elapsed().as_nanos() as u64;}
        TRACE.with(|s|{
            let s=s.borrow();assert_eq!(s.depth,0);
            let rows: Vec<_>=s.rows.iter().enumerate().filter(|(_,r)|r.samples>0).map(|(i,r)|
                serde_json::json!({"shape":SHAPES[i/4],"raw":RAW[i%4],"samples":r.samples,
                    "force_ns":r.force_ns,"compare_ns":r.compare_ns,"max_ns":r.max_ns})).collect();
            eprintln!("QCKN_CONV_COST {}",serde_json::json!({"schema":1,"seed":s.seed,
                "root_calls":s.roots,"nested_calls":s.nested,"samples":s.samples,
                "sample_denominator":1024,"timer_floor_ns":floor/10000,"rows":rows,
                "kind":"SAMPLED_NATIVE_TIME_NOT_RETIRED_INSTRUCTIONS"}));
        });
    }
    #[cfg(test)]
    mod tests {
        use super::*;
        #[test] fn qckn_cost_probe_nested_roots_do_not_overlap() {
            TRACE.with(|s|*s.borrow_mut()=Stats::new(17));
            {let _outer=begin();{let inner=begin();assert!(!inner.sampled);}}
            TRACE.with(|s|{let s=s.borrow();assert_eq!((s.depth,s.roots,s.nested),(0,1,1));});
        }
        #[test] fn qckn_cost_probe_sampling_is_reproducible() {
            let (mut a,mut b)=(Stats::new(17),Stats::new(17));let mut n=0;
            for _ in 0..1000000 {let x=a.draw();assert_eq!(x,b.draw());n+=usize::from(x);}
            assert!(n>500 && n<2000);
        }
        #[test] fn qckn_cost_probe_phase_costs_stay_separate() {
            let mut r=Row::default();r.add(100,200);r.add(10,20);
            assert_eq!((r.samples,r.force_ns,r.compare_ns,r.max_ns),(2,110,220,300));
        }
    }
}
