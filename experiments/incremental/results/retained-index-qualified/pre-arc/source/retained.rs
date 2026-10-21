//! Private, process-owned baseline graph. No serialized retained state is accepted.
//! Edge-preserving updates cannot change its SCC partition or condensation graph.
use super::*;
use std::time::Instant;

#[derive(Serialize)]
pub struct FinishStats {
    pub mode: String,
    pub reason: Option<String>,
    pub changed_sccs: usize,
    pub affected_sccs: usize,
    pub changed_declarations: usize,
    pub affected_declarations: usize,
    pub touched_declarations: usize,
    pub total_declarations: usize,
    pub total_sccs: usize,
    pub closure_hashes: usize,
    pub dependency_edges_touched: usize,
    pub affected_keys: Vec<String>,
    pub recomputed_sccs: Vec<usize>,
    pub compute_wall_seconds: f64,
    pub compute_cpu_seconds: Option<f64>,
    /// Entire post-parse finish call, including cache cleanup and statistics construction.
    pub finish_wall_seconds: f64,
    pub finish_cpu_seconds: Option<f64>,
}

pub(super) struct Clock(Instant, Option<f64>);
impl Clock {
    pub(super) fn start() -> Self { Self(Instant::now(), cpu_seconds()) }
    pub(super) fn elapsed(&self) -> (f64, Option<f64>) {
        (self.0.elapsed().as_secs_f64(), cpu_seconds().zip(self.1).map(|(now, start)| now - start))
    }
}
#[cfg(target_os = "linux")]
fn cpu_seconds() -> Option<f64> {
    #[repr(C)]
    struct Timespec { seconds: std::os::raw::c_long, nanos: std::os::raw::c_long }
    extern "C" { fn clock_gettime(clock: std::os::raw::c_int, value: *mut Timespec) -> std::os::raw::c_int; }
    let mut value = Timespec { seconds: 0, nanos: 0 };
    // Linux CLOCK_PROCESS_CPUTIME_ID. This never reads or authenticates external state.
    if unsafe { clock_gettime(2, &mut value) } == 0 {
        Some(value.seconds as f64 + value.nanos as f64 / 1e9)
    } else { None }
}
#[cfg(not(target_os = "linux"))]
fn cpu_seconds() -> Option<f64> { None }

#[derive(Clone)]
pub(super) struct RetainedGraph {
    index: ExportIdentityIndex,
    deps: Vec<Vec<Fingerprint>>,
    components: Vec<Vec<usize>>,
    component_of: Vec<usize>,
    outgoing: Vec<Vec<usize>>,
    reverse: Vec<Vec<usize>>,
    negatives: Vec<BTreeSet<String>>,
    roots: Vec<Fingerprint>,
}

impl RetainedGraph {
    /// Cold preparation deliberately does not alter the independent full `finish` oracle.
    /// SCC traversal follows its exact deterministic order; root hashes come from that oracle.
    pub(super) fn prepare(builder: &IdentityBuilder, index: ExportIdentityIndex) -> Result<Self> {
        let adjacency = builder.declarations.iter().map(|d|
            d.deps.iter().filter_map(|key| builder.by_key.get(key).copied()).collect::<Vec<_>>()
        ).collect::<Vec<_>>();
        let n = adjacency.len();
        let mut reverse_declarations = vec![Vec::new(); n];
        for (i, edges) in adjacency.iter().enumerate() {
            for j in edges { reverse_declarations[*j].push(i); }
        }
        let (mut visited, mut order) = (vec![false; n], Vec::with_capacity(n));
        for start in 0..n {
            if visited[start] { continue; }
            let mut stack = vec![(start, false)];
            while let Some((k, done)) = stack.pop() {
                if done { order.push(k); }
                else if !visited[k] {
                    visited[k] = true;
                    stack.push((k, true));
                    for v in &adjacency[k] {
                        if !visited[*v] { stack.push((*v, false)); }
                    }
                }
            }
        }
        let (mut components, mut component_of) = (Vec::<Vec<usize>>::new(), vec![usize::MAX; n]);
        for start in order.into_iter().rev() {
            if component_of[start] != usize::MAX { continue; }
            let number = components.len();
            let mut members = Vec::new();
            let mut stack = vec![start];
            component_of[start] = number;
            while let Some(k) = stack.pop() {
                members.push(k);
                for v in &reverse_declarations[k] {
                    if component_of[*v] == usize::MAX {
                        component_of[*v] = number;
                        stack.push(*v);
                    }
                }
            }
            components.push(members);
        }
        let mut outgoing = vec![BTreeSet::new(); components.len()];
        let mut negatives = vec![BTreeSet::new(); components.len()];
        let mut roots = vec![[0; 32]; components.len()];
        for (number, members) in components.iter().enumerate() {
            if let Some(first) = members.first() { roots[number] = index.declarations[*first].closure.0; }
            for member in members {
                if index.declarations[*member].closure.0 != roots[number] {
                    return failure("baseline SCC closure mismatch during retained preparation");
                }
                for target in &adjacency[*member] {
                    if component_of[*target] != number { outgoing[number].insert(component_of[*target]); }
                }
                for key in &builder.declarations[*member].deps {
                    if !builder.by_key.contains_key(key) { negatives[number].insert(hex(*key)); }
                }
            }
        }
        let outgoing = outgoing.into_iter().map(|set| set.into_iter().collect::<Vec<_>>()).collect::<Vec<_>>();
        let mut reverse = vec![Vec::new(); components.len()];
        for (number, edges) in outgoing.iter().enumerate() {
            for target in edges {
                if *target <= number { return failure("retained condensation is not dependency ordered"); }
                reverse[*target].push(number);
            }
        }
        Ok(Self { index, deps: builder.declarations.iter().map(|d| d.deps.clone()).collect(),
            components, component_of, outgoing, reverse, negatives, roots })
    }

    fn fallback(self, builder: &IdentityBuilder, positions: &[usize], reason: &str) -> Result<(ExportIdentityIndex, FinishStats)> {
        let changed = positions.iter().filter(|i| self.index.declarations[**i].own.0 != builder.declarations[**i].own).copied().collect::<Vec<_>>();
        full_finish(builder, &changed, reason)
    }

    pub(super) fn finish(mut self, builder: &IdentityBuilder, positions: &[usize], builtin_name_inserted: bool) -> Result<(ExportIdentityIndex, FinishStats)> {
        let clock = Clock::start();
        if builtin_name_inserted { return self.fallback(builder, positions, "builtin_name_inventory_changed"); }
        for position in positions {
            let declaration = &builder.declarations[*position];
            let old = &self.index.declarations[*position];
            if old.key.0 != declaration.key || old.kind != declaration.kind || old.name != declaration.name {
                return self.fallback(builder, positions, "declaration_identity_changed");
            }
            // Include unresolved negative name keys, not merely resolved adjacency.
            if self.deps[*position] != declaration.deps {
                return self.fallback(builder, positions, "dependency_edges_changed");
            }
            if old.own.0 != declaration.own && declaration.kind == "axiom" {
                return self.fallback(builder, positions, "axiom_assumption_changed");
            }
            if old.own.0 != declaration.own && BUILTINS.split_whitespace().any(|b| b == declaration.name) {
                return self.fallback(builder, positions, "builtin_declaration_changed");
            }
        }
        let changed = positions.iter().filter(|i| self.index.declarations[**i].own.0 != builder.declarations[**i].own).copied().collect::<Vec<_>>();
        let changed_components = changed.iter().map(|i| self.component_of[*i]).collect::<BTreeSet<_>>();
        let mut affected = changed_components.clone();
        let mut pending = changed_components.iter().copied().collect::<Vec<_>>();
        while let Some(component) = pending.pop() {
            for dependent in &self.reverse[component] {
                if affected.insert(*dependent) { pending.push(*dependent); }
            }
        }
        let mut touched = 0;
        let mut edges_touched = positions.iter().map(|i| builder.declarations[*i].deps.len()).sum::<usize>();
        // Kosaraju numbers components source-first. Reverse order hashes dependencies first.
        for number in affected.iter().rev() {
            let mut contents = self.components[*number].iter().map(|i| {
                let d = &builder.declarations[*i]; (hex(d.key), hex(d.own))
            }).collect::<Vec<_>>();
            touched += contents.len();
            contents.sort_unstable();
            let mut dependencies = self.outgoing[*number].iter().map(|i| hex(self.roots[*i])).collect::<Vec<_>>();
            dependencies.sort_unstable();
            edges_touched += self.outgoing[*number].len() + self.negatives[*number].len();
            self.roots[*number] = digest_value(&json!(["scc", contents, dependencies, self.negatives[*number]]));
        }
        for position in &changed { self.index.declarations[*position].own = HexFingerprint(builder.declarations[*position].own); }
        for component in &affected {
            for position in &self.components[*component] {
                self.index.declarations[*position].closure = HexFingerprint(self.roots[*component]);
            }
        }
        // A builtin's body may be unchanged while a helper in its dependency cone changes.
        for (key, closure) in self.index.builtins.values_mut() {
            if let Some(position) = key.as_ref().and_then(|key| builder.by_key.get(&key.0)) {
                let component = self.component_of[*position];
                if affected.contains(&component) { *closure = Some(HexFingerprint(self.roots[component])); }
            }
        }
        let (wall, cpu) = clock.elapsed();
        let mut affected_keys = affected.iter().flat_map(|c| self.components[*c].iter()).map(|i| hex(builder.declarations[*i].key)).collect::<Vec<_>>();
        affected_keys.sort_unstable();
        let stats = FinishStats { mode: "retained".into(), reason: None, changed_sccs: changed_components.len(),
            affected_sccs: affected.len(), changed_declarations: changed.len(), affected_declarations: touched,
            touched_declarations: touched, total_declarations: self.index.count, total_sccs: self.components.len(),
            closure_hashes: affected.len(), dependency_edges_touched: edges_touched, affected_keys,
            recomputed_sccs: affected.iter().rev().copied().collect(), compute_wall_seconds: wall, compute_cpu_seconds: cpu, finish_wall_seconds: 0.0, finish_cpu_seconds: None };
        Ok((self.index, stats))
    }
    pub(super) fn baseline(&self) -> ExportIdentityIndex { self.index.clone() }
}

/// Independent old full algorithm, with observation-only counters calculated afterward.
pub(super) fn full_finish(builder: &IdentityBuilder, changed: &[usize], reason: &str) -> Result<(ExportIdentityIndex, FinishStats)> {
    let clock = Clock::start();
    let index = builder.finish()?;
    let (wall, cpu) = clock.elapsed();
    let total_sccs = index.declarations.iter().map(|d| d.closure.0).collect::<BTreeSet<_>>().len();
    let changed_sccs = changed.iter().map(|i| index.declarations[*i].closure.0).collect::<BTreeSet<_>>().len();
    let stats = FinishStats { mode: "full".into(), reason: Some(reason.into()), changed_sccs,
        affected_sccs: total_sccs, changed_declarations: changed.len(), affected_declarations: index.count,
        touched_declarations: index.count, total_declarations: index.count, total_sccs,
        closure_hashes: total_sccs, dependency_edges_touched: builder.declarations.iter().map(|d| d.deps.len()).sum(),
        affected_keys: index.declarations.iter().map(|d| hex(d.key.0)).collect(),
        recomputed_sccs: (0..total_sccs).collect(), compute_wall_seconds: wall, compute_cpu_seconds: cpu, finish_wall_seconds: 0.0, finish_cpu_seconds: None };
    Ok((index, stats))
}
