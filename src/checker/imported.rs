// SPDX-License-Identifier: Apache-2.0
// MathGraph: retain comparison with imported declarations when reconstructing them.

use super::cache::TcCache;
use super::context::{ExportFile, TcCtx};
use super::env::{Declar, EnvLimit};
use super::tc::{InferFlag::Check, TypeChecker};
use super::value::{EMPTY_CTX, EMPTY_ENV};
use crate::outcome::{CheckError, ensure};
use crate::term::id::NameId;
use std::error::Error;
use std::sync::Arc;

pub(crate) struct SourceBlock {
    pub names: Arc<[NameId]>,
    pub declarations: Vec<Declar>,
}

fn belongs(d: &Declar, names: &[NameId]) -> bool {
    match d {
        Declar::Inductive(d) => d.all_ind_names.as_ref() == names,
        Declar::Constructor(d) => names.contains(&d.inductive_name),
        Declar::Recursor(d) => d.all_inductives.as_ref() == names,
        _ => false,
    }
}

impl ExportFile {
    pub(crate) fn check_imported_blocks(
        &self,
        blocks: &[SourceBlock],
    ) -> Result<(), Box<dyn Error>> {
        std::thread::scope(|scope| {
            std::thread::Builder::new().name("imported-declarations".into())
                .stack_size(crate::STACK_SIZE).spawn_scoped(scope, || {
                for block in blocks {
                    let start = self.declars.get_index_of(&block.names[0]).expect("missing derived block");
                    let count = self.declars.iter().skip(start)
                        .take_while(|(_, d)| belongs(d, &block.names)).count();
                    ensure!(count == block.declarations.len(), "imported inductive block has missing or extra declarations");
                    let env = self.new_env(EnvLimit::ByIndex(start + count));
                    let mut seen = crate::term::hash::FxHashSet::default();
                    for source in &block.declarations {
                        ensure!(seen.insert(source.info().name), "duplicate imported declaration");
                        let Some(derived) = self.declars.get(&source.info().name) else {
                            crate::outcome::reject!("imported declaration was not reconstructed")
                        };
                        ensure!(belongs(derived, &block.names), "imported declaration belongs to a different block");
                        ensure!(source.info().uparams == derived.info().uparams, "imported declaration universe parameters differ");
                        match (source, derived) {
                            (Declar::Inductive(a), Declar::Inductive(b)) => ensure!(
                                a.all_ind_names == b.all_ind_names && a.all_ctor_names == b.all_ctor_names
                                && a.num_params == b.num_params && a.num_indices == b.num_indices
                                && a.is_recursive == b.is_recursive && a.is_nested == b.is_nested,
                                "imported inductive metadata differs"),
                            (Declar::Constructor(a), Declar::Constructor(b)) => ensure!(
                                a.inductive_name == b.inductive_name && a.ctor_idx == b.ctor_idx
                                && a.num_params == b.num_params && a.num_fields == b.num_fields,
                                "imported constructor metadata differs"),
                            (Declar::Recursor(a), Declar::Recursor(b)) => {
                                ensure!(a.all_inductives == b.all_inductives && a.num_params == b.num_params
                                    && a.num_indices == b.num_indices && a.num_motives == b.num_motives
                                    && a.num_minors == b.num_minors && a.is_k == b.is_k
                                    && a.rec_rules.len() == b.rec_rules.len(), "imported recursor metadata differs");
                                for (a, b) in a.rec_rules.iter().zip(b.rec_rules.iter()) {
                                    ensure!(a.ctor_name == b.ctor_name
                                        && a.ctor_telescope_size_wo_params == b.ctor_telescope_size_wo_params,
                                        "imported recursor rule constructor or field count differs");
                                }
                            },
                            _ => crate::outcome::reject!("imported declaration kind differs"),
                        }
                        let rules_differ = match (source, derived) {
                            (Declar::Recursor(a), Declar::Recursor(b)) =>
                                a.rec_rules.iter().zip(b.rec_rules.iter()).any(|(a,b)| a.val != b.val),
                            _ => false,
                        };
                        // The exact derived expression is already checked by reconstruction.
                        if source.info().ty == derived.info().ty && !rules_differ { continue }
                        let arena = bumpalo::Bump::new();
                        let mut ctx = TcCtx::new(self, &arena);
                        let mut cache = TcCache::new_small();
                        let mut tc = TypeChecker::new(&mut ctx, &env, Some(*source.info()), &mut cache);
                        if source.info().ty != derived.info().ty {
                            ensure!(tc.ctx.node(source.info().ty).loose == 0, "imported type contains a loose bound variable");
                            tc.infer_sort_of_v(Check, 0, EMPTY_ENV, EMPTY_CTX, source.info().ty);
                            let a = tc.eval(0, EMPTY_ENV, source.info().ty);
                            let b = tc.eval(0, EMPTY_ENV, derived.info().ty);
                            ensure!(tc.conv_types_at(0, a, b), "imported declaration type differs");
                        }
                        if let (Declar::Recursor(a), Declar::Recursor(b)) = (source, derived) {
                            for (a, b) in a.rec_rules.iter().zip(b.rec_rules.iter()) {
                                if a.val == b.val { continue }
                                ensure!(tc.ctx.node(a.val).loose == 0, "imported rule contains a loose bound variable");
                                let aty = tc.infer_value(Check, 0, EMPTY_ENV, EMPTY_CTX, a.val);
                                let bty = tc.infer_value(Check, 0, EMPTY_ENV, EMPTY_CTX, b.val);
                                ensure!(tc.conv_types_at(0, aty, bty), "imported recursor rule type differs");
                                let av = tc.eval(0, EMPTY_ENV, a.val);
                                let bv = tc.eval(0, EMPTY_ENV, b.val);
                                ensure!(tc.def_eq_at(0, av, bv), "imported recursor rule value differs");
                            }
                        }
                    }
                }
            })?.join().map_err(CheckError::from_panic)
                .map_err(|e| -> Box<dyn Error> { match e {
                    CheckError::Rejected(e) => Box::new(e), CheckError::Declined(e) => Box::new(e),
                    CheckError::Internal(p) => std::panic::resume_unwind(p),
                } })
        })
    }
}
