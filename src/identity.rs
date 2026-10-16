//! Typed export identities matching experiments/incremental/engine.py.
//!
//! This observer is driven by the kernel parser. It supplies cache witnesses,
//! never verification authority: declarations are still checked by ExportFile.
use crate::identity_support::{digest_bytes, digest_value, hex, write_hex, write_string, Fingerprint, StrictValue};
use crate::util::{new_fx_hash_map, FxHashMap};
use serde::{Serialize, Serializer};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::collections::BTreeSet;
use std::error::Error;
use std::sync::Arc;

type Result<T> = std::result::Result<T, Box<dyn Error>>;
const BUILTINS: &str = "Quot Quot.mk Quot.lift Quot.ind String String.ofList Nat Nat.zero Nat.succ Nat.add Nat.sub Nat.mul Nat.pow Nat.mod Nat.div Nat.div.go Nat.modCore.go Nat.beq Nat.ble Nat.gcd Nat.land Nat.lor Nat.xor Nat.shiftLeft Nat.shiftRight Bool.true Bool.false Char Char.ofNat List List.nil List.cons";
fn simple(k: &str) -> bool {
    matches!(k, "axiom" | "def" | "opaque" | "thm")
}
fn failure<T>(s: impl Into<String>) -> Result<T> {
    Err(s.into().into())
}
#[derive(Clone)]
struct Name {
    hash: Fingerprint,
    display: String,
}
#[derive(Clone)]
struct Expression {
    hash: Fingerprint,
    deps: Arc<[u32]>,
}
struct Declaration {
    key: Fingerprint,
    name: String,
    kind: String,
    own: Fingerprint,
    deps: Vec<Fingerprint>,
}

fn subset(left: &[u32], right: &[u32]) -> bool {
    if left.len() > right.len() {
        return false;
    }
    let mut n = 0;
    for value in right {
        if n < left.len() && left[n] == *value {
            n += 1;
        }
    }
    n == left.len()
}

#[derive(Clone, Copy)]
struct HexFingerprint(Fingerprint);
impl Serialize for HexFingerprint {
    fn serialize<S: Serializer>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error> {
        let mut bytes = [0u8; 64];
        const HEX: &[u8; 16] = b"0123456789abcdef";
        for (i, b) in self.0.iter().enumerate() {
            bytes[2 * i] = HEX[(b >> 4) as usize];
            bytes[2 * i + 1] = HEX[(b & 15) as usize];
        }
        serializer.serialize_str(std::str::from_utf8(&bytes).expect("hexadecimal ASCII"))
    }
}
#[derive(Clone, Serialize)]
struct ExportDeclaration {
    key: HexFingerprint,
    name: String,
    kind: String,
    own: HexFingerprint,
    deps: Vec<HexFingerprint>,
    index: usize,
    closure: HexFingerprint,
}
/// The same JSON index schema returned by the Python identity oracle.
#[derive(Clone, Serialize)]
pub struct ExportIdentityIndex {
    meta: Value,
    declarations: Vec<ExportDeclaration>,
    count: usize,
    builtins: BTreeMap<String, (Option<HexFingerprint>, Option<HexFingerprint>)>,
    complex: HexFingerprint,
    schedule: HexFingerprint,
}

/// Retained typed identity DAG. This is a cache witness, never proof authority.
pub struct IdentityBuilder {
    names: Vec<Option<Name>>,
    levels: Vec<Option<Fingerprint>>,
    exprs: Vec<Option<Expression>>,
    declarations: Vec<Declaration>,
    seen: FxHashMap<Fingerprint, ()>,
    blocks: Vec<(usize, usize)>,
    meta: Option<Value>,
    rows: usize,
    buffer: Vec<u8>,
    delta_attempted: bool,
    retained: Option<RetainedClosure>,
}
#[derive(Serialize)]
pub struct IdentityDelta {
    pub index: ExportIdentityIndex,
    pub rows_processed: usize,
    pub dag_rows: usize,
    pub replaced_names: Vec<String>,
    pub retained_graph_used: bool,
    pub recomputed_sccs: usize,
}

/// Baseline SCC cache. Never grants acceptance; the authenticated source
/// transition and real selected kernel are required independently.
struct RetainedComponent {
    members: Vec<usize>,
    outgoing: Vec<usize>,
    reverse: Vec<usize>,
    negatives: Vec<String>,
}
struct RetainedClosure {
    baseline: ExportIdentityIndex,
    component_for: Vec<usize>,
    components: Vec<RetainedComponent>,
    roots: Vec<Fingerprint>,
    builtin_components: Vec<(String, usize)>,
}
impl RetainedClosure {
    fn capture(baseline: ExportIdentityIndex) -> Result<Self> {
        let n = baseline.declarations.len();
        if baseline.count != n { return failure("retained count mismatch"); }
        let mut by_key: FxHashMap<Fingerprint, usize> = new_fx_hash_map();
        for (i, d) in baseline.declarations.iter().enumerate() {
            if by_key.insert(d.key.0, i).is_some() {
                return failure("duplicate retained declaration");
            }
        }
        let adjacency = baseline.declarations.iter()
            .map(|d| d.deps.iter().filter_map(|k| by_key.get(&k.0).copied()).collect::<Vec<_>>())
            .collect::<Vec<_>>();
        let mut reverse = vec![Vec::<usize>::new(); n];
        for (i, edges) in adjacency.iter().enumerate() {
            for j in edges { reverse[*j].push(i); }
        }
        // Exactly mirror the original finish() SCC ordering.
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
        let (mut groups, mut component_for) =
            (Vec::<Vec<usize>>::new(), vec![usize::MAX; n]);
        for start in order.into_iter().rev() {
            if component_for[start] != usize::MAX { continue; }
            let number = groups.len();
            let mut members = Vec::new();
            let mut stack = vec![start];
            component_for[start] = number;
            while let Some(k) = stack.pop() {
                members.push(k);
                for v in &reverse[k] {
                    if component_for[*v] == usize::MAX {
                        component_for[*v] = number;
                        stack.push(*v);
                    }
                }
            }
            groups.push(members);
        }
        let mut components = Vec::with_capacity(groups.len());
        let mut roots = Vec::with_capacity(groups.len());
        for (number, members) in groups.into_iter().enumerate() {
            let Some(first) = members.first() else { return failure("empty SCC"); };
            let root = baseline.declarations[*first].closure.0;
            let mut outgoing = BTreeSet::new();
            let mut negatives = BTreeSet::new();
            for &i in &members {
                if baseline.declarations[i].closure.0 != root {
                    return failure("inconsistent baseline SCC identity");
                }
                for &dependency in &adjacency[i] {
                    let other = component_for[dependency];
                    if other != number { outgoing.insert(other); }
                }
                for dependency in &baseline.declarations[i].deps {
                    if !by_key.contains_key(&dependency.0) {
                        negatives.insert(hex(dependency.0));
                    }
                }
            }
            components.push(RetainedComponent {
                members, outgoing: outgoing.into_iter().collect(),
                reverse: Vec::new(), negatives: negatives.into_iter().collect(),
            });
            roots.push(root);
        }
        for number in 0..components.len() {
            let outgoing = components[number].outgoing.clone();
            for dependency in outgoing { components[dependency].reverse.push(number); }
        }
        // Independently reconstruct all baseline hashes once on the cold path.
        // Refuse the cache if it differs from the full-index result.
        for number in (0..components.len()).rev() {
            let component = &components[number];
            let mut contents = component.members.iter().map(|&i|
                (hex(baseline.declarations[i].key.0), hex(baseline.declarations[i].own.0)))
                .collect::<Vec<_>>();
            contents.sort_unstable();
            let mut dependencies = component.outgoing.iter().map(|&c| hex(roots[c]))
                .collect::<Vec<_>>();
            dependencies.sort_unstable();
            let expected = digest_value(&json!(["scc", contents, dependencies, component.negatives]));
            if expected != roots[number] { return failure("retained SCC baseline oracle mismatch"); }
        }
        let mut builtin_components = Vec::new();
        for (name, (Some(key), Some(root))) in &baseline.builtins {
            let Some(&i) = by_key.get(&key.0) else { return failure("missing builtin declaration"); };
            if root.0 != roots[component_for[i]] { return failure("builtin closure mismatch"); }
            builtin_components.push((name.clone(), component_for[i]));
        }
        Ok(Self { baseline, component_for, components, roots, builtin_components })
    }

    fn update(&self, current: &[Declaration], positions: &[usize])
        -> Result<(ExportIdentityIndex, usize)>
    {
        if current.len() != self.baseline.count { return failure("retained count drift"); }
        let mut result = self.baseline.clone();
        let mut frontier = Vec::new();
        for &i in positions {
            let previous = result.declarations.get(i).ok_or("unknown replacement index")?;
            let d = current.get(i).ok_or("missing replacement declaration")?;
            if previous.key.0 != d.key || previous.kind != d.kind
                || previous.deps.len() != d.deps.len()
                || previous.deps.iter().zip(&d.deps).any(|(a,b)| a.0 != *b)
            {
                return failure("retained graph topology drift");
            }
            if previous.own.0 != d.own { frontier.push(self.component_for[i]); }
            result.declarations[i].own = HexFingerprint(d.own);
        }
        let mut affected = vec![false; self.components.len()];
        while let Some(c) = frontier.pop() {
            if affected[c] { continue; }
            affected[c] = true;
            frontier.extend(self.components[c].reverse.iter().copied());
        }
        let mut roots = self.roots.clone();
        let mut recomputed = 0;
        for number in (0..self.components.len()).rev() {
            if !affected[number] { continue; }
            recomputed += 1;
            let component = &self.components[number];
            let mut contents = component.members.iter().map(|&i|
                (hex(current[i].key), hex(current[i].own))).collect::<Vec<_>>();
            contents.sort_unstable();
            let mut dependencies = component.outgoing.iter().map(|&c| hex(roots[c]))
                .collect::<Vec<_>>();
            dependencies.sort_unstable();
            roots[number] = digest_value(&json!(["scc", contents, dependencies, component.negatives]));
        }
        for (number, component) in self.components.iter().enumerate() {
            if !affected[number] { continue; }
            for &i in &component.members {
                result.declarations[i].closure = HexFingerprint(roots[number]);
            }
        }
        for (name, component) in &self.builtin_components {
            if affected[*component] {
                let entry = result.builtins.get_mut(name).ok_or("missing retained builtin")?;
                entry.1 = Some(HexFingerprint(roots[*component]));
            }
        }
        Ok((result, recomputed))
    }
}

impl IdentityBuilder {
    pub(crate) fn new(input_len: usize) -> Self {
        Self {
            names: vec![Some(Name { hash: digest_bytes(b"[\"anonymous\"]"), display: String::new() })],
            levels: vec![Some(digest_bytes(b"[\"zero\"]"))],
            exprs: Vec::with_capacity(input_len / 48),
            declarations: Vec::new(),
            seen: new_fx_hash_map(),
            blocks: Vec::new(),
            meta: None,
            rows: 0,
            buffer: Vec::with_capacity(512),
            delta_attempted: false,
            retained: None,
        }
    }
    fn begin(&mut self) -> Result<()> {
        if self.meta.is_none() {
            return failure("metadata missing");
        }
        self.rows += 1;
        Ok(())
    }
    fn name(&self, i: u32) -> Result<&Name> {
        self.names
            .get(i as usize)
            .and_then(Option::as_ref)
            .ok_or_else(|| format!("invalid or forward name DAG reference: {i}").into())
    }
    fn level(&self, i: u32) -> Result<Fingerprint> {
        self.levels
            .get(i as usize)
            .copied()
            .flatten()
            .ok_or_else(|| format!("invalid or forward level DAG reference: {i}").into())
    }
    fn expr(&self, i: u32) -> Result<&Expression> {
        self.exprs
            .get(i as usize)
            .and_then(Option::as_ref)
            .ok_or_else(|| format!("invalid or forward expression DAG reference: {i}").into())
    }
    fn put<T>(table: &mut Vec<Option<T>>, i: u32, value: T) -> Result<()> {
        let i = i as usize;
        if table.get(i).is_some_and(Option::is_some) {
            return failure("duplicate DAG index");
        }
        if i >= table.len() {
            table.resize_with(i + 1, || None);
        }
        table[i] = Some(value);
        Ok(())
    }
    fn prefix(&mut self, tag: &str) {
        self.buffer.clear();
        self.buffer.push(b'[');
        write_string(tag, &mut self.buffer);
        self.buffer.push(b',');
    }
    fn finish_hash(&mut self) -> Fingerprint {
        self.buffer.push(b']');
        digest_bytes(&self.buffer)
    }
    fn hash_text(&mut self, hash: &Fingerprint) {
        self.buffer.push(b'"');
        write_hex(hash, &mut self.buffer);
        self.buffer.push(b'"');
    }
    pub(crate) fn name_str(&mut self, i: u32, pre: u32, suffix: &str) -> Result<()> {
        self.begin()?;
        let parent = self.name(pre)?.clone();
        self.prefix("str");
        self.hash_text(&parent.hash);
        self.buffer.push(b',');
        write_string(suffix, &mut self.buffer);
        let hash = self.finish_hash();
        let display =
            if parent.display.is_empty() { suffix.to_owned() } else { format!("{}.{}", parent.display, suffix) };
        Self::put(&mut self.names, i, Name { hash, display })
    }
    pub(crate) fn name_num(&mut self, i: u32, pre: u32, suffix: u64) -> Result<()> {
        self.begin()?;
        let parent = self.name(pre)?.clone();
        self.prefix("num");
        self.hash_text(&parent.hash);
        self.buffer.push(b',');
        self.buffer.extend_from_slice(suffix.to_string().as_bytes());
        let hash = self.finish_hash();
        let display =
            if parent.display.is_empty() { suffix.to_string() } else { format!("{}.{}", parent.display, suffix) };
        Self::put(&mut self.names, i, Name { hash, display })
    }
    pub(crate) fn level_node(&mut self, tag: &str, i: u32, left: u32, right: Option<u32>) -> Result<()> {
        self.begin()?;
        let l = if tag == "param" { self.name(left)?.hash } else { self.level(left)? };
        let r = right.map(|r| self.level(r)).transpose()?;
        self.prefix(tag);
        if r.is_some() {
            self.buffer.push(b'[');
        }
        self.hash_text(&l);
        if let Some(r) = r {
            self.buffer.push(b',');
            self.hash_text(&r);
            self.buffer.push(b']');
        }
        let hash = self.finish_hash();
        Self::put(&mut self.levels, i, hash)
    }
    pub(crate) fn atom(&mut self, tag: &str, i: u32, value: &str, numeric: bool) -> Result<()> {
        self.begin()?;
        self.prefix(tag);
        if numeric {
            self.buffer.extend_from_slice(value.as_bytes());
        } else {
            write_string(value, &mut self.buffer);
        }
        let hash = self.finish_hash();
        Self::put(&mut self.exprs, i, Expression { hash, deps: Arc::from([]) })
    }
    pub(crate) fn sort(&mut self, i: u32, level: u32) -> Result<()> {
        self.begin()?;
        let level = self.level(level)?;
        self.prefix("sort");
        self.hash_text(&level);
        let hash = self.finish_hash();
        Self::put(&mut self.exprs, i, Expression { hash, deps: Arc::from([]) })
    }
    pub(crate) fn constant(&mut self, i: u32, name: u32, levels: &[u32]) -> Result<()> {
        self.begin()?;
        let hash = self.name(name)?.hash;
        self.prefix("const");
        self.buffer.push(b'[');
        self.hash_text(&hash);
        self.buffer.extend_from_slice(b",[");
        for (n, l) in levels.iter().enumerate() {
            let h = self.level(*l)?;
            if n > 0 {
                self.buffer.push(b',');
            }
            self.hash_text(&h);
        }
        self.buffer.extend_from_slice(b"]]");
        let hash = self.finish_hash();
        Self::put(&mut self.exprs, i, Expression { hash, deps: Arc::from([name]) })
    }
    fn merged(&self, exprs: &[u32], extra: Option<u32>) -> Result<Arc<[u32]>> {
        let mut current: Option<Arc<[u32]>> = None;
        for i in exprs {
            let next = &self.expr(*i)?.deps;
            if next.is_empty() {
                continue;
            }
            current = Some(match current {
                None => next.clone(),
                Some(old) if old == *next => old,
                Some(old) if subset(next, &old) => old,
                Some(old) if subset(&old, next) => next.clone(),
                Some(old) => {
                    let mut out = Vec::with_capacity(old.len() + next.len());
                    let (mut a, mut b) = (0, 0);
                    while a < old.len() || b < next.len() {
                        let v = if b == next.len() || (a < old.len() && old[a] < next[b]) {
                            let v = old[a];
                            a += 1;
                            v
                        } else if a == old.len() || next[b] < old[a] {
                            let v = next[b];
                            b += 1;
                            v
                        } else {
                            let v = old[a];
                            a += 1;
                            b += 1;
                            v
                        };
                        out.push(v);
                    }
                    Arc::from(out)
                }
            });
        }
        let mut result = current.unwrap_or_else(|| Arc::from([]));
        if let Some(extra) = extra {
            if let Err(at) = result.binary_search(&extra) {
                let mut v = result.to_vec();
                v.insert(at, extra);
                result = Arc::from(v);
            }
        }
        Ok(result)
    }
    pub(crate) fn expression(
        &mut self,
        tag: &str,
        i: u32,
        fields: &[(&str, u32)],
        name: Option<(&str, u32)>,
        text: Option<(&str, &str)>,
        flag: Option<(&str, bool)>,
        number: Option<(&str, usize)>,
    ) -> Result<()> {
        self.begin()?;
        let edges: smallvec::SmallVec<[u32; 4]> = fields.iter().map(|(_, v)| *v).collect();
        let deps = self.merged(&edges, name.filter(|(k, _)| *k == "typeName").map(|(_, v)| v))?;
        enum Field<'s> {
            Hash(Fingerprint),
            Text(&'s str),
            Bool(bool),
            Number(usize),
        }
        let mut all: smallvec::SmallVec<[(&str, Field<'_>); 6]> = smallvec::SmallVec::new();
        for (k, v) in fields {
            all.push((k, Field::Hash(self.expr(*v)?.hash)));
        }
        if let Some((k, v)) = name {
            all.push((k, Field::Hash(self.name(v)?.hash)));
        }
        if let Some((k, v)) = text {
            all.push((k, Field::Text(v)));
        }
        if let Some((k, v)) = flag {
            all.push((k, Field::Bool(v)));
        }
        if let Some((k, v)) = number {
            all.push((k, Field::Number(v)));
        }
        all.sort_unstable_by_key(|(k, _)| *k);
        self.prefix(tag);
        self.buffer.push(b'{');
        for (n, (k, v)) in all.into_iter().enumerate() {
            if n > 0 {
                self.buffer.push(b',');
            }
            write_string(k, &mut self.buffer);
            self.buffer.push(b':');
            match v {
                Field::Hash(hash) => self.hash_text(&hash),
                Field::Text(s) => write_string(s, &mut self.buffer),
                Field::Bool(b) => self.buffer.extend_from_slice(if b { b"true" } else { b"false" }),
                Field::Number(n) => self.buffer.extend_from_slice(n.to_string().as_bytes()),
            }
        }
        self.buffer.push(b'}');
        let hash = self.finish_hash();
        Self::put(&mut self.exprs, i, Expression { hash, deps })
    }

    pub(crate) fn app(&mut self, i: u32, fun: u32, arg: u32) -> Result<()> {
        self.begin()?;
        let deps = self.merged(&[fun, arg], None)?;
        let f = self.expr(fun)?.hash;
        let a = self.expr(arg)?.hash;
        self.prefix("app");
        self.buffer.extend_from_slice(b"{\"arg\":");
        self.hash_text(&a);
        self.buffer.extend_from_slice(b",\"fn\":");
        self.hash_text(&f);
        self.buffer.push(b'}');
        let hash = self.finish_hash();
        Self::put(&mut self.exprs, i, Expression { hash, deps })
    }
    pub(crate) fn simple_declaration(
        &mut self,
        kind: &str,
        name: u32,
        ty: u32,
        value: u32,
        uparams: &[u32],
        all: &[u32],
        hint: Option<crate::env::ReducibilityHint>,
    ) -> Result<()> {
        self.begin()?;
        let mut object = json!({"name":name,"type":ty,"value":value,"levelParams":uparams,"all":all});
        if let Some(h) = hint {
            object["safety"] = json!("safe");
            object["hints"] = match h {
                crate::env::ReducibilityHint::Regular(n) => json!({"regular":n}),
                crate::env::ReducibilityHint::Abbrev => json!("abbrev"),
                crate::env::ReducibilityHint::Opaque => json!("opaque"),
            };
        }
        self.declaration(kind, &object)
    }
    fn fields(value: &Value, required: &[&str]) -> Result<()> {
        let Some(object) = value.as_object() else {
            return failure("unsupported fields: expected object");
        };
        if object.len() != required.len() || required.iter().any(|k| !object.contains_key(*k)) {
            return failure("unsupported fields");
        }
        Ok(())
    }
    fn uint(value: &Value) -> Result<u32> {
        value.as_u64().and_then(|v| u32::try_from(v).ok()).ok_or_else(|| "invalid DAG reference".into())
    }
    fn normalize(&self, k: &str, v: &Value, deps: &mut BTreeSet<Fingerprint>) -> Result<Value> {
        Ok(match k {
            "name" | "induct" | "ctor" => {
                let h = self.name(Self::uint(v)?)?.hash;
                deps.insert(h);
                json!(["name", hex(h)])
            }
            "levelParams" | "all" | "ctors" => {
                let vals = v
                    .as_array()
                    .ok_or("name array required")?
                    .iter()
                    .map(|v| self.name(Self::uint(v)?).map(|n| n.hash))
                    .collect::<Result<Vec<_>>>()?;
                if k != "levelParams" {
                    deps.extend(vals.iter().copied());
                }
                json!(["names", vals.into_iter().map(hex).collect::<Vec<_>>()])
            }
            "type" | "value" | "rhs" => {
                let e = self.expr(Self::uint(v)?)?;
                for i in e.deps.iter() {
                    deps.insert(self.name(*i)?.hash);
                }
                json!(["expr", hex(e.hash)])
            }
            "rules" => {
                let mut out = Vec::new();
                for r in v.as_array().ok_or("rules array required")? {
                    Self::fields(r, &["ctor", "nfields", "rhs"])?;
                    let mut m = serde_json::Map::new();
                    for (a, b) in r.as_object().unwrap() {
                        m.insert(a.clone(), self.normalize(a, b, deps)?);
                    }
                    out.push(Value::Object(m));
                }
                Value::Array(out)
            }
            _ => v.clone(),
        })
    }
    fn declaration(&mut self, kind: &str, obj: &Value) -> Result<()> {
        let required: &[&str] = match kind {
            "axiom" => &["name", "levelParams", "type", "isUnsafe"],
            "def" => &["name", "levelParams", "type", "value", "hints", "safety", "all"],
            "thm" => &["name", "levelParams", "type", "value", "all"],
            "opaque" => &["name", "levelParams", "type", "value", "isUnsafe", "all"],
            "quot" => &["name", "levelParams", "type", "kind"],
            "itype" => &[
                "name",
                "levelParams",
                "type",
                "numParams",
                "numIndices",
                "all",
                "ctors",
                "numNested",
                "isRec",
                "isUnsafe",
                "isReflexive",
            ],
            "ctor" => &["name", "levelParams", "type", "induct", "cidx", "numParams", "numFields", "isUnsafe"],
            "rec" => &[
                "name",
                "levelParams",
                "type",
                "all",
                "numParams",
                "numIndices",
                "numMotives",
                "numMinors",
                "rules",
                "k",
                "isUnsafe",
            ],
            _ => return failure("unsupported declaration"),
        };
        Self::fields(obj, required)?;
        if obj.get("isUnsafe").is_some_and(|v| v != &Value::Bool(false))
            || obj.get("safety").is_some_and(|v| v != &Value::String("safe".to_owned()))
        {
            return failure("unsafe or partial declaration is unsupported");
        }
        let mut deps = BTreeSet::new();
        let mut canonical = serde_json::Map::new();
        for (k, v) in obj.as_object().unwrap() {
            canonical.insert(k.clone(), self.normalize(k, v, &mut deps)?);
        }
        let n = self.name(Self::uint(&obj["name"])?)?.clone();
        deps.remove(&n.hash);
        if self.seen.insert(n.hash, ()).is_some() {
            return failure("duplicate declaration");
        }
        if kind == "axiom" && !["propext", "Classical.choice", "Quot.sound"].contains(&n.display.as_str()) {
            return failure(format!("nonstandard axiom forbidden: {}", n.display));
        }
        self.declarations.push(Declaration {
            key: n.hash,
            name: n.display,
            kind: kind.to_owned(),
            own: digest_value(&json!([kind, canonical])),
            deps: deps.into_iter().collect(),
        });
        Ok(())
    }
    pub(crate) fn observe_general(&mut self, line: &str) -> Result<()> {
        let StrictValue(row) = serde_json::from_str(line)?;
        let row = row.as_object().ok_or("export row is not an object")?;
        let tags = row.keys().filter(|k| !matches!(k.as_str(), "in" | "il" | "ie")).collect::<Vec<_>>();
        if tags.len() != 1 {
            return failure("ambiguous export row");
        }
        let tag = tags[0].as_str();
        let value = &row[tag];
        if tag == "meta" {
            if self.meta.is_some() || self.rows != 0 || row.len() != 1 {
                return failure("metadata must be unique and first");
            }
            if value["format"]["version"] != "3.1.0" {
                return failure("unsupported export format");
            }
            self.meta = Some(value.clone());
            self.rows += 1;
            return Ok(());
        }
        let index = |kind: &str| -> Result<u32> {
            if row.len() != 2 || !row.contains_key(kind) {
                return failure("duplicate, invalid or ambiguous DAG index");
            }
            Self::uint(&row[kind])
        };
        match tag {
            "str" => {
                Self::fields(value, &["pre", "str"])?;
                self.name_str(
                    index("in")?,
                    Self::uint(&value["pre"])?,
                    value["str"].as_str().ok_or("ill-typed name component")?,
                )
            }
            "num" => {
                Self::fields(value, &["pre", "i"])?;
                self.name_num(
                    index("in")?,
                    Self::uint(&value["pre"])?,
                    value["i"].as_u64().ok_or("ill-typed name component")?,
                )
            }
            "succ" | "param" => self.level_node(tag, index("il")?, Self::uint(value)?, None),
            "max" | "imax" => {
                let a = value.as_array().ok_or("level pair required")?;
                if a.len() != 2 {
                    return failure("level pair required");
                }
                self.level_node(tag, index("il")?, Self::uint(&a[0])?, Some(Self::uint(&a[1])?))
            }
            "bvar" => self.atom(tag, index("ie")?, &value.to_string(), true),
            "natVal" | "strVal" => {
                self.atom(tag, index("ie")?, value.as_str().ok_or("literal string required")?, false)
            }
            "sort" => self.sort(index("ie")?, Self::uint(value)?),
            "const" => {
                Self::fields(value, &["name", "us"])?;
                let us = value["us"]
                    .as_array()
                    .ok_or("universe array required")?
                    .iter()
                    .map(Self::uint)
                    .collect::<Result<Vec<_>>>()?;
                self.constant(index("ie")?, Self::uint(&value["name"])?, &us)
            }
            "app" => {
                Self::fields(value, &["fn", "arg"])?;
                self.app(index("ie")?, Self::uint(&value["fn"])?, Self::uint(&value["arg"])?)
            }
            "lam" | "forallE" | "letE" | "proj" => {
                let required: &[&str] = match tag {
                    "lam" | "forallE" => &["name", "type", "body", "binderInfo"],
                    "letE" => &["name", "type", "value", "body", "nondep"],
                    _ => &["typeName", "idx", "struct"],
                };
                Self::fields(value, required)?;
                self.begin()?;
                let mut deps = Vec::new();
                let mut normalized = serde_json::Map::new();
                let mut extra = None;
                for (k, v) in value.as_object().unwrap() {
                    let v = match k.as_str() {
                        "type" | "body" | "value" | "struct" => {
                            let e = Self::uint(v)?;
                            deps.push(e);
                            json!(hex(self.expr(e)?.hash))
                        }
                        "name" | "typeName" => {
                            let n = Self::uint(v)?;
                            if k == "typeName" {
                                extra = Some(n);
                            }
                            json!(hex(self.name(n)?.hash))
                        }
                        _ => v.clone(),
                    };
                    normalized.insert(k.clone(), v);
                }
                let deps = self.merged(&deps, extra)?;
                let hash = digest_value(&json!([tag, normalized]));
                Self::put(&mut self.exprs, index("ie")?, Expression { hash, deps })
            }
            "axiom" | "def" | "thm" | "opaque" | "quot" => {
                if row.len() != 1 {
                    return failure("index attached to declaration");
                }
                self.begin()?;
                self.declaration(tag, value)
            }
            "inductive" => {
                if row.len() != 1 {
                    return failure("index attached to inductive");
                }
                Self::fields(value, &["types", "ctors", "recs"])?;
                self.begin()?;
                let start = self.declarations.len();
                for (field, kind) in [("types", "itype"), ("ctors", "ctor"), ("recs", "rec")] {
                    for d in value[field].as_array().ok_or("inductive array required")? {
                        self.declaration(kind, d)?;
                    }
                }
                self.blocks.push((start, self.declarations.len() - start));
                Ok(())
            }
            _ => failure(format!("unsupported export item: {tag}")),
        }
    }
    /// Apply one baseline-anchored update. On any error the session is poisoned;
    /// callers must terminate it rather than consume possibly partial state.
    /// All rows still require the ordinary full selected checker downstream.
    pub fn apply_delta(&mut self, input: &str) -> Result<IdentityDelta> {
        if self.delta_attempted { return failure("identity session permits only one delta attempt"); }
        self.delta_attempted = true;
        let mut rows_processed = 0;
        let mut dag_rows = 0;
        let mut replaced_names = Vec::new();
        let mut replaced_positions = Vec::new();
        let mut added_names = false;
        let mut replaced = BTreeSet::new();
        for line in input.lines() {
            let StrictValue(row) = serde_json::from_str(line)?;
            let row = row.as_object().ok_or("export row is not an object")?;
            let tags = row.keys().filter(|k| !matches!(k.as_str(), "in" | "il" | "ie")).collect::<Vec<_>>();
            if tags.len() != 1 { return failure("ambiguous export row"); }
            let tag = tags[0].as_str();
            if simple(tag) {
                if row.len() != 1 { return failure("index attached to declaration"); }
                let key = self.name(Self::uint(&row[tag]["name"])?)?.hash;
                let Some(position) = self.declarations.iter().position(|d| d.key == key) else {
                    return failure("delta cannot introduce a declaration");
                };
                if self.declarations[position].kind != tag { return failure("delta cannot change declaration kind"); }
                if !replaced.insert(key) { return failure("duplicate declaration replacement"); }
                self.seen.remove(&key);
                self.observe_general(line)?;
                let replacement = self.declarations.pop().ok_or("replacement missing")?;
                replaced_names.push(replacement.name.clone());
                self.declarations[position] = replacement;
                replaced_positions.push(position);
            } else {
                if matches!(tag, "str" | "num") { added_names = true; }
                if !matches!(tag, "str" | "num" | "succ" | "max" | "imax" | "param" | "bvar" | "sort" | "const" | "app" | "lam" | "forallE" | "letE" | "proj" | "natVal" | "strVal") {
                    return failure("delta metadata and complex declarations are unsupported");
                }
                self.observe_general(line)?;
                dag_rows += 1;
            }
            rows_processed += 1;
        }
        let (index, retained_graph_used, recomputed_sccs) =
            self.finish_delta(&replaced_positions, added_names)?;
        Ok(IdentityDelta { index, rows_processed, dag_rows, replaced_names,
                           retained_graph_used, recomputed_sccs })
    }
    /// Cold-only admission of the original complete index and retained SCC DAG.
    pub fn prepare_retained(&mut self) -> Result<ExportIdentityIndex> {
        let baseline = self.finish()?;
        self.retained = Some(RetainedClosure::capture(baseline.clone())?);
        Ok(baseline)
    }
    fn finish_delta(&self, positions: &[usize], added_names: bool)
        -> Result<(ExportIdentityIndex, bool, usize)>
    {
        if let Some(cache) = &self.retained {
            let topology_changed = positions.iter().any(|&i| {
                let Some(old) = cache.baseline.declarations.get(i) else { return true; };
                let Some(new) = self.declarations.get(i) else { return true; };
                old.key.0 != new.key || old.kind != new.kind ||
                old.deps.len() != new.deps.len() ||
                old.deps.iter().zip(&new.deps).any(|(a, b)| a.0 != *b)
            });
            // Added name entries may change implicit builtin lookup roots.
            if !added_names && !topology_changed {
                let (index, recomputed) = cache.update(&self.declarations, positions)?;
                return Ok((index, true, recomputed));
            }
        }
        Ok((self.finish()?, false, 0))
    }
    pub fn finish(&self) -> Result<ExportIdentityIndex> {
        let mut by_key: FxHashMap<Fingerprint, usize> = new_fx_hash_map();
        for (i, d) in self.declarations.iter().enumerate() {
            by_key.insert(d.key, i);
        }
        let adjacency = self
            .declarations
            .iter()
            .map(|d| d.deps.iter().filter_map(|k| by_key.get(k).copied()).collect::<Vec<_>>())
            .collect::<Vec<_>>();
        let n = adjacency.len();
        let mut reverse = vec![Vec::new(); n];
        for (i, edges) in adjacency.iter().enumerate() {
            for j in edges {
                reverse[*j].push(i);
            }
        }
        let (mut visited, mut order) = (vec![false; n], Vec::with_capacity(n));
        for start in 0..n {
            if visited[start] {
                continue;
            }
            let mut stack = vec![(start, false)];
            while let Some((k, done)) = stack.pop() {
                if done {
                    order.push(k);
                } else if !visited[k] {
                    visited[k] = true;
                    stack.push((k, true));
                    for v in &adjacency[k] {
                        if !visited[*v] {
                            stack.push((*v, false));
                        }
                    }
                }
            }
        }
        let (mut components, mut comp) = (Vec::<Vec<usize>>::new(), vec![usize::MAX; n]);
        for start in order.into_iter().rev() {
            if comp[start] != usize::MAX {
                continue;
            }
            let number = components.len();
            let mut members = Vec::new();
            let mut stack = vec![start];
            comp[start] = number;
            while let Some(k) = stack.pop() {
                members.push(k);
                for v in &reverse[k] {
                    if comp[*v] == usize::MAX {
                        comp[*v] = number;
                        stack.push(*v);
                    }
                }
            }
            components.push(members);
        }
        let mut roots = vec![[0; 32]; components.len()];
        for number in (0..components.len()).rev() {
            let members = &components[number];
            let mut outgoing = BTreeSet::new();
            let mut negatives = BTreeSet::new();
            let mut contents = Vec::new();
            for k in members {
                let d = &self.declarations[*k];
                contents.push((hex(d.key), hex(d.own)));
                for v in &adjacency[*k] {
                    if comp[*v] != number {
                        outgoing.insert(comp[*v]);
                    }
                }
                for v in &d.deps {
                    if !by_key.contains_key(v) {
                        negatives.insert(hex(*v));
                    }
                }
            }
            contents.sort_unstable();
            let mut dependencies = outgoing.into_iter().map(|c| hex(roots[c])).collect::<Vec<_>>();
            dependencies.sort_unstable();
            roots[number] = digest_value(&json!(["scc", contents, dependencies, negatives]));
        }
        let mut builtin_ids = FxHashMap::default();
        for name in self.names.iter().flatten() {
            if BUILTINS.split_whitespace().any(|b| b == name.display) {
                if builtin_ids.insert(name.display.clone(), name.hash).is_some() {
                    return failure("ambiguous builtin name");
                }
            }
        }
        let mut builtin = BTreeMap::new();
        for b in BUILTINS.split_whitespace() {
            builtin.insert(
                b.to_owned(),
                match builtin_ids.get(b) {
                    Some(k) => (Some(HexFingerprint(*k)), by_key.get(k).map(|i| HexFingerprint(roots[comp[*i]]))),
                    None => (None, None),
                },
            );
        }
        let complex = digest_value(&json!([
            self.blocks,
            self.declarations.iter().filter(|d| !simple(&d.kind)).map(|d| (hex(d.key), hex(d.own))).collect::<Vec<_>>()
        ]));
        let schedule = digest_value(&json!(self.declarations.iter().map(|d| hex(d.key)).collect::<Vec<_>>()));
        let declarations = self
            .declarations
            .iter()
            .enumerate()
            .map(|(i, d)| ExportDeclaration {
                key: HexFingerprint(d.key),
                name: d.name.clone(),
                kind: d.kind.clone(),
                own: HexFingerprint(d.own),
                deps: d.deps.iter().copied().map(HexFingerprint).collect(),
                index: i,
                closure: HexFingerprint(roots[comp[i]]),
            })
            .collect();
        Ok(ExportIdentityIndex {
            meta: self.meta.clone().ok_or("metadata missing")?,
            declarations,
            count: n,
            builtins: builtin,
            complex: HexFingerprint(complex),
            schedule: HexFingerprint(schedule),
        })
    }
}

#[cfg(test)]
mod session_tests {
    use super::*;
    fn meta() -> &'static str { r#"{"meta":{"lean":{"version":"4.35.0","githash":"test"},"exporter":{"name":"lean4export","version":"test"},"format":{"version":"3.1.0"}}}"# }
    fn baseline() -> String {
        [meta(), r#"{"in":1,"str":{"pre":0,"str":"a"}}"#, r#"{"in":2,"str":{"pre":0,"str":"b"}}"#,
         r#"{"ie":0,"sort":0}"#, r#"{"ie":1,"const":{"name":1,"us":[]}}"#,
         r#"{"def":{"name":1,"levelParams":[],"type":0,"value":0,"hints":"abbrev","safety":"safe","all":[]}}"#,
         r#"{"def":{"name":2,"levelParams":[],"type":0,"value":1,"hints":"abbrev","safety":"safe","all":[]}}"#].join("\n") + "\n"
    }
    fn config() -> crate::util::Config { serde_json::from_value(json!({"use_stdin":true,"num_threads":1})).unwrap() }
    fn builder() -> IdentityBuilder { crate::parser::export_identity_builder(baseline().as_bytes(),config()).unwrap() }
    fn replacement(value:u32) -> String { json!({"def":{"name":1,"levelParams":[],"type":0,"value":value,"hints":"abbrev","safety":"safe","all":[]}}).to_string() }

    fn three_declarations() -> String {
        let mut rows = baseline().lines().map(str::to_owned).collect::<Vec<_>>();
        rows.insert(3, r#"{"in":3,"str":{"pre":0,"str":"c"}}"#.to_owned());
        rows.push(r#"{"def":{"name":3,"levelParams":[],"type":0,"value":0,"hints":"abbrev","safety":"safe","all":[]}}"#.to_owned());
        rows.join("\n") + "\n"
    }
    #[test]
    fn retained_fixed_topology_recloses_affected_sccs_and_matches_fresh_index() {
        let source = three_declarations();
        let mut identity = crate::parser::export_identity_builder(source.as_bytes(), config()).unwrap();
        let before = identity.prepare_retained().unwrap();
        assert_eq!(before.count, 3);
        let additions = "{\"il\":1,\"succ\":0}\n{\"ie\":2,\"sort\":1}\n";
        let delta = identity.apply_delta(&(additions.to_owned() + &replacement(2) + "\n")).unwrap();
        assert!(delta.retained_graph_used);
        assert_eq!(delta.recomputed_sccs, 2, "changed a and dependent b; untouched c");
        let mut rows = source.lines().map(str::to_owned).collect::<Vec<_>>();
        let at = rows.iter().position(|s| s.contains("\"def\":{\"name\":1")).unwrap();
        rows.splice(at..=at, [r#"{"il":1,"succ":0}"#.to_owned(),
                              r#"{"ie":2,"sort":1}"#.to_owned(), replacement(2)]);
        let full = crate::parser::export_identity((rows.join("\n")+"\n").as_bytes(), config()).unwrap();
        assert_eq!(serde_json::to_value(delta.index).unwrap(), serde_json::to_value(full).unwrap());
        let mut noop = crate::parser::export_identity_builder(source.as_bytes(), config()).unwrap();
        let baseline_index = noop.prepare_retained().unwrap();
        let zero = noop.apply_delta("").unwrap();
        assert!(zero.retained_graph_used);
        assert_eq!(zero.recomputed_sccs, 0);
        assert_eq!(serde_json::to_value(zero.index).unwrap(),
                   serde_json::to_value(baseline_index).unwrap());
    }
    #[test]
    fn retained_graph_edge_changes_and_new_cycles_fall_back_to_full_index() {
        for (dag, replacement_row) in [
            ("", replacement(0).replace("\"name\":1", "\"name\":2")),
            ("{\"ie\":2,\"const\":{\"name\":2,\"us\":[]}}\n", replacement(2)),
        ] {
            let mut identity = builder();
            identity.prepare_retained().unwrap();
            let delta = identity.apply_delta(&(dag.to_owned()+&replacement_row+"\n")).unwrap();
            assert!(!delta.retained_graph_used, "dependency topology changed");
            let mut rows = baseline().lines().map(str::to_owned).collect::<Vec<_>>();
            let target = if dag.is_empty() { 2 } else { 1 };
            let at = rows.iter().position(|s| s.contains(&format!("\"def\":{{\"name\":{target}"))).unwrap();
            let mut replacement_rows = dag.lines().map(str::to_owned).collect::<Vec<_>>();
            replacement_rows.push(replacement_row);
            rows.splice(at..=at, replacement_rows);
            let oracle = crate::parser::export_identity((rows.join("\n")+"\n").as_bytes(), config()).unwrap();
            assert_eq!(serde_json::to_value(delta.index).unwrap(), serde_json::to_value(oracle).unwrap());
        }
    }
    #[test]
    fn retained_added_names_require_full_builtin_identity_scan() {
        let mut identity = builder();
        identity.prepare_retained().unwrap();
        let delta = identity.apply_delta("{\"in\":3,\"str\":{\"pre\":0,\"str\":\"Nat\"}}\n").unwrap();
        assert!(!delta.retained_graph_used);
    }
    #[test]
    fn session_replacement_matches_fresh_genuine_parser_and_preserves_dependency_schedule() {
        let mut retained=builder();
        let old=serde_json::to_value(retained.finish().unwrap()).unwrap();
        assert_eq!(old,serde_json::to_value(crate::parser::export_identity(baseline().as_bytes(),config()).unwrap()).unwrap());
        let additions="{\"il\":1,\"succ\":0}\n{\"ie\":2,\"sort\":1}\n";
        let delta=retained.apply_delta(&(additions.to_owned()+&replacement(2)+"\n")).unwrap();
        let mut rows=baseline().lines().map(str::to_owned).collect::<Vec<_>>();
        rows[5]=replacement(2);rows.insert(5,"{\"ie\":2,\"sort\":1}".into());rows.insert(5,"{\"il\":1,\"succ\":0}".into());
        let fresh=crate::parser::export_identity((rows.join("\n")+"\n").as_bytes(),config()).unwrap();
        let actual=serde_json::to_value(&delta.index).unwrap();
        assert_eq!(actual,serde_json::to_value(fresh).unwrap());
        assert_eq!(actual["schedule"],old["schedule"]);
        assert_ne!(actual["declarations"][1]["closure"],old["declarations"][1]["closure"]);
        assert_eq!((delta.rows_processed,delta.dag_rows),(3,2));assert_eq!(delta.replaced_names,vec!["a"]);
        assert!(retained.apply_delta(&replacement(0)).is_err(),"one baseline-anchored update only");
    }
    #[test]
    fn session_empty_and_unused_dag_updates_preserve_index_but_require_downstream_parser() {
        let mut unchanged=builder();
        let old=serde_json::to_value(unchanged.finish().unwrap()).unwrap();
        let update=unchanged.apply_delta("").unwrap();
        assert_eq!(serde_json::to_value(update.index).unwrap(),old);
        assert_eq!((update.rows_processed,update.dag_rows),(0,0));
        assert!(update.replaced_names.is_empty());
        let mut retained=builder();
        let malformed="{\"ie\":2,\"bvar\":\"not-an-integer\"}\n";
        let update=retained.apply_delta(malformed).unwrap();
        assert_eq!(serde_json::to_value(update.index).unwrap(),old);
        assert_eq!((update.rows_processed,update.dag_rows),(1,1));
        assert!(update.replaced_names.is_empty());
        let composite=baseline()+malformed;
        let downstream=std::panic::catch_unwind(|| {
            let arena=stumpalo::Arena::new();
            let rejected=crate::parser::parse_export_mapped(arena.as_arena_ref(),composite.as_bytes(),config()).is_err();
            rejected
        });
        assert!(downstream.is_err() || downstream.unwrap(),"actual downstream kernel parser must reject malformed unused DAG rows");
    }
    #[test]
    fn session_refuses_duplicate_missing_new_metadata_complex_and_changed_kind() {
        let cases=vec![
          "{\"ie\":0,\"sort\":0}".to_owned(),
          "{\"ie\":4,\"sort\":999}".to_owned(),
          replacement(999),
          "{\"in\":3,\"str\":{\"pre\":0,\"str\":\"new\"}}\n{\"thm\":{\"name\":3,\"levelParams\":[],\"type\":0,\"value\":0,\"all\":[]}}".to_owned(),
          meta().to_owned(),
          "{\"inductive\":{\"types\":[],\"ctors\":[],\"recs\":[]}}".to_owned(),
          "{\"thm\":{\"name\":1,\"levelParams\":[],\"type\":0,\"value\":0,\"all\":[]}}".to_owned(),
          "{\"ie\":3,\"sort\":0,\"sort\":0}".to_owned(),
          "{\"in\":3,\"str\":{\"pre\":0,\"str\":\"bad\u{0001}\"}}".to_owned(),
          replacement(0)+"\n"+&replacement(0),
        ];
        for delta in cases { let mut retained=builder();assert!(retained.apply_delta(&delta).is_err(),"accepted {delta}");assert!(retained.apply_delta(&replacement(0)).is_err(),"failure must poison session"); }
    }
}
