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
mod retained;
pub use retained::FinishStats;
use retained::RetainedGraph;

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
    by_key: FxHashMap<Fingerprint, usize>,
    retained: Option<RetainedGraph>,
    retained_topology: Option<Arc<retained::RetainedTopology>>,
}
#[derive(Serialize)]
pub struct IdentityDelta {
    pub index: ExportIdentityIndex,
    pub rows_processed: usize,
    pub dag_rows: usize,
    pub replaced_names: Vec<String>,
    pub finish_stats: FinishStats,
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
            by_key: new_fx_hash_map(),
            retained: None,
            retained_topology: None,
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
        self.by_key.insert(n.hash, self.declarations.len());
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
    pub fn prepare_retained(&mut self) -> Result<ExportIdentityIndex> {
        if self.delta_attempted { return failure("cannot prepare an attempted identity session"); }
        if self.retained.is_none() {
            self.by_key = self.declarations.iter().enumerate().map(|(i, d)| (d.key, i)).collect();
            let prepared = RetainedGraph::prepare(self, self.finish()?)?;
            self.retained_topology = Some(prepared.topology());
            self.retained = Some(prepared);
        }
        Ok(self.retained.as_ref().unwrap().baseline())
    }
    pub fn apply_delta(&mut self, input: &str) -> Result<IdentityDelta> {
        self.apply_delta_mode(input, false)
    }
    pub fn apply_delta_full(&mut self, input: &str) -> Result<IdentityDelta> {
        self.apply_delta_mode(input, true)
    }
    fn apply_delta_mode(&mut self, input: &str, force_full: bool) -> Result<IdentityDelta> {
        if self.delta_attempted { return failure("identity session permits only one delta attempt"); }
        if !force_full && self.retained.is_none() {
            if let Err(error) = self.prepare_retained() { self.delta_attempted = true; return Err(error); }
        }
        self.delta_attempted = true;
        let prepared = self.retained.take();
        let mut changed_positions = Vec::new();
        let mut positions = Vec::new();
        let mut builtin_name_inserted = false;
        let mut rows_processed = 0;
        let mut dag_rows = 0;
        let mut replaced_names = Vec::new();
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
                let Some(position) = self.by_key.get(&key).copied() else {
                    return failure("delta cannot introduce a declaration");
                };
                if self.declarations[position].kind != tag { return failure("delta cannot change declaration kind"); }
                if !replaced.insert(key) { return failure("duplicate declaration replacement"); }
                self.seen.remove(&key);
                self.observe_general(line)?;
                let replacement = self.declarations.pop().ok_or("replacement missing")?;
                if replacement.own != self.declarations[position].own { changed_positions.push(position); }
                replaced_names.push(replacement.name.clone());
                self.declarations[position] = replacement;
                self.by_key.insert(key, position);
                positions.push(position);
            } else {
                if !matches!(tag, "str" | "num" | "succ" | "max" | "imax" | "param" | "bvar" | "sort" | "const" | "app" | "lam" | "forallE" | "letE" | "proj" | "natVal" | "strVal") {
                    return failure("delta metadata and complex declarations are unsupported");
                }
                self.observe_general(line)?;
                if matches!(tag, "str" | "num") {
                    let name = self.name(Self::uint(&row["in"])?)?;
                    builtin_name_inserted |= BUILTINS.split_whitespace().any(|b| b == name.display);
                }
                dag_rows += 1;
            }
            rows_processed += 1;
        }
        let finish_clock = retained::Clock::start();
        let (index, mut finish_stats) = if force_full {
            drop(prepared);
            retained::full_finish(self, &changed_positions, "forced_full_finish")?
        } else { prepared.ok_or("retained baseline missing")?.finish(self, &positions, builtin_name_inserted)? };
        (finish_stats.finish_wall_seconds, finish_stats.finish_cpu_seconds) = finish_clock.elapsed();
        Ok(IdentityDelta { index, rows_processed, dag_rows, replaced_names, finish_stats })
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

#[cfg(test)]
mod retained_contract_tests {
    use super::*;

    fn graph(deps: &[Vec<usize>]) -> IdentityBuilder {
        let mut builder = IdentityBuilder::new(0);
        builder.observe_general(r#"{"meta":{"format":{"version":"3.1.0"}}}"#).unwrap();
        for i in 0..deps.len() {
            builder.name_str(i as u32 + 1, 0, &format!("node{i}")).unwrap();
        }
        for (i, edges) in deps.iter().enumerate() {
            builder.declarations.push(Declaration {
                key: builder.name(i as u32 + 1).unwrap().hash,
                name: format!("node{i}"), kind: "def".into(), own: digest_bytes(&[i as u8]),
                deps: edges.iter().map(|j| builder.name(*j as u32 + 1).unwrap().hash).collect(),
            });
        }
        builder
    }

    #[test]
    fn retained_fixed_edges_reclose_only_reverse_cone_and_match_full() {
        let mut builder = graph(&[vec![], vec![0], vec![1], vec![]]);
        let baseline = serde_json::to_value(builder.prepare_retained().unwrap()).unwrap();
        let prepared = builder.retained.take().unwrap();
        builder.declarations[0].own = digest_bytes(b"changed");
        let (actual, stats) = prepared.finish(&builder, &[0], false).unwrap();
        assert_eq!(serde_json::to_value(&actual).unwrap(), serde_json::to_value(builder.finish().unwrap()).unwrap());
        assert_eq!(stats.mode, "retained");
        assert_eq!((stats.changed_sccs, stats.affected_sccs, stats.affected_declarations), (1, 3, 3));
        assert_eq!((stats.closure_hashes, stats.total_declarations), (3, 4));
        assert_eq!(serde_json::to_value(&actual).unwrap()["declarations"][3], baseline["declarations"][3]);
    }

    fn equal_full(builder: &IdentityBuilder, actual: &ExportIdentityIndex) {
        assert_eq!(serde_json::to_value(actual).unwrap(), serde_json::to_value(builder.finish().unwrap()).unwrap());
    }
    #[test]
    fn retained_cycles_multiple_changes_nonsimple_members_and_reverse_cone() {
        let mut builder = graph(&[vec![1], vec![0], vec![0], vec![2], vec![]]);
        builder.declarations[1].kind = "ctor".into();
        let old = builder.prepare_retained().unwrap();
        let prepared = builder.retained.take().unwrap();
        builder.declarations[0].own = digest_bytes(b"changed-member");
        let (actual, stats) = prepared.finish(&builder, &[0], false).unwrap();
        equal_full(&builder, &actual);
        assert_eq!((stats.changed_sccs, stats.affected_sccs, stats.affected_declarations), (1, 3, 4));
        assert_eq!(actual.complex.0, old.complex.0);
        assert_ne!(actual.declarations[1].closure.0, old.declarations[1].closure.0);
        assert_eq!(actual.declarations[4].closure.0, old.declarations[4].closure.0);

        let mut builder = graph(&[vec![1], vec![0], vec![0], vec![2], vec![]]);
        builder.prepare_retained().unwrap();
        let prepared = builder.retained.take().unwrap();
        builder.declarations[0].own = digest_bytes(b"first");
        builder.declarations[1].own = digest_bytes(b"second");
        let (actual, stats) = prepared.finish(&builder, &[1, 0], false).unwrap();
        equal_full(&builder, &actual);
        assert_eq!((stats.changed_declarations, stats.changed_sccs, stats.affected_declarations), (2, 1, 4));
    }
    #[test]
    fn retained_two_changed_components_dependency_first_and_restoration() {
        let mut builder = graph(&[vec![], vec![0], vec![1], vec![]]);
        let original = builder.prepare_retained().unwrap();
        let original_own = builder.declarations[0].own;
        let prepared = builder.retained.take().unwrap();
        builder.declarations[0].own = digest_bytes(b"first");
        builder.declarations[1].own = digest_bytes(b"second");
        let (actual, stats) = prepared.finish(&builder, &[1, 0], false).unwrap();
        equal_full(&builder, &actual);
        assert_eq!((stats.changed_sccs, stats.affected_sccs), (2, 3));
        assert!(stats.recomputed_sccs.windows(2).all(|w| w[0] > w[1]));
        // Restoration is a new owned baseline, never a second production update.
        let mut restored = graph(&[vec![], vec![0], vec![1], vec![]]);
        restored.declarations[0].own = digest_bytes(b"first");
        restored.prepare_retained().unwrap();
        let prepared = restored.retained.take().unwrap();
        restored.declarations[0].own = original_own;
        let (actual, _) = prepared.finish(&restored, &[0], false).unwrap();
        assert_eq!(serde_json::to_value(actual).unwrap(), serde_json::to_value(original).unwrap());
    }
    #[test]
    fn retained_noop_keeps_all_roots_and_does_zero_hash_work() {
        let mut builder = graph(&[vec![], vec![0]]);
        let original = builder.prepare_retained().unwrap();
        let prepared = builder.retained.take().unwrap();
        let (actual, stats) = prepared.finish(&builder, &[0], false).unwrap();
        assert_eq!(serde_json::to_value(actual).unwrap(), serde_json::to_value(original).unwrap());
        assert_eq!((stats.changed_declarations, stats.affected_sccs, stats.closure_hashes), (0, 0, 0));
        assert!(stats.affected_keys.is_empty());
    }
    #[test]
    fn retained_cycle_split_and_retarget_and_negative_change_fall_back() {
        for (deps, position, next) in [
            (vec![vec![1], vec![0]], 1, vec![]),
            (vec![vec![1], vec![], vec![]], 0, vec![2]),
        ] {
            let mut builder = graph(&deps);
            builder.prepare_retained().unwrap();
            let prepared = builder.retained.take().unwrap();
            builder.declarations[position].own = digest_bytes(b"edge-change");
            builder.declarations[position].deps = next.into_iter().map(|i| builder.declarations[i].key).collect();
            let (actual, stats) = prepared.finish(&builder, &[position], false).unwrap();
            equal_full(&builder, &actual);
            assert_eq!(stats.reason.as_deref(), Some("dependency_edges_changed"));
        }
        let mut builder = graph(&[vec![]]);
        builder.declarations[0].deps = vec![digest_bytes(b"missing-x")];
        builder.prepare_retained().unwrap();
        let prepared = builder.retained.take().unwrap();
        builder.declarations[0].deps = vec![digest_bytes(b"missing-y")];
        let (actual, stats) = prepared.finish(&builder, &[0], false).unwrap();
        equal_full(&builder, &actual);
        assert_eq!(stats.reason.as_deref(), Some("dependency_edges_changed"));
    }
    #[test]
    fn retained_refreshes_builtin_helper_closure_and_falls_back_on_global_own() {
        let mut builder = graph(&[vec![], vec![0]]);
        builder.name_str(3, 0, "String").unwrap();
        builder.name_str(4, 3, "ofList").unwrap();
        builder.declarations[1].name = "String.ofList".into();
        builder.declarations[1].key = builder.name(4).unwrap().hash;
        let original = builder.prepare_retained().unwrap();
        let prepared = builder.retained.take().unwrap();
        builder.declarations[0].own = digest_bytes(b"helper");
        let (actual, _) = prepared.finish(&builder, &[0], false).unwrap();
        equal_full(&builder, &actual);
        assert_ne!(actual.builtins["String.ofList"].1.unwrap().0, original.builtins["String.ofList"].1.unwrap().0);
        for axiom in [true, false] {
            let mut builder = graph(&[vec![]]);
            if axiom { builder.declarations[0].kind = "axiom".into(); }
            else {
                builder.name_str(2, 0, "Nat").unwrap();
                builder.declarations[0].key = builder.name(2).unwrap().hash;
                builder.declarations[0].name = "Nat".into();
            }
            builder.prepare_retained().unwrap();
            let prepared = builder.retained.take().unwrap();
            builder.declarations[0].own = digest_bytes(b"global");
            let (actual, stats) = prepared.finish(&builder, &[0], false).unwrap();
            equal_full(&builder, &actual);
            assert_eq!(stats.reason.as_deref(), Some(if axiom {"axiom_assumption_changed"} else {"builtin_declaration_changed"}));
        }
    }
    #[test]
    fn retained_sparse_name_holes_builtin_presence_and_ambiguity() {
        let mut builder = graph(&[vec![]]);
        builder.name_str(100, 0, "sparse").unwrap();
        builder.prepare_retained().unwrap();
        let delta = r#"{"in":2,"str":{"pre":0,"str":"Nat"}}"#;
        let update = builder.apply_delta(delta).unwrap();
        assert_eq!(update.finish_stats.reason.as_deref(), Some("builtin_name_inventory_changed"));
        assert!(update.index.builtins["Nat"].0.is_some());
        equal_full(&builder, &update.index);
        for same_key in [true, false] {
            let mut builder = graph(&[vec![]]);
            builder.name_str(2, 0, "Nat.add").unwrap();
            builder.name_str(100, 0, "Nat").unwrap();
            builder.prepare_retained().unwrap();
            let delta = if same_key {r#"{"in":3,"str":{"pre":0,"str":"Nat.add"}}"#}
                else {r#"{"in":3,"str":{"pre":100,"str":"add"}}"#};
            assert!(builder.apply_delta(delta).is_err());
            assert!(builder.apply_delta("").is_err());
        }
    }

    #[test]
    fn retained_edge_change_and_unresolved_dependency_change_use_full_oracle() {
        for negative in [false, true] {
            let mut builder = graph(&[vec![], vec![0], vec![]]);
            builder.prepare_retained().unwrap();
            let prepared = builder.retained.take().unwrap();
            builder.declarations[0].own = digest_bytes(b"changed");
            builder.declarations[0].deps = vec![if negative { digest_bytes(b"missing-name") } else {builder.declarations[1].key}];
            let (actual, stats) = prepared.finish(&builder, &[0], false).unwrap();
            assert_eq!(stats.mode, "full");
            assert_eq!(stats.reason.as_deref(), Some("dependency_edges_changed"));
            assert_eq!(serde_json::to_value(actual).unwrap(), serde_json::to_value(builder.finish().unwrap()).unwrap());
        }
    }
    /// Parse and mutate exactly once. Repetition setup clones only the private baseline
    /// graph outside measurement; no checker, parser, serialization, or IPC is timed.
    #[test]
    #[ignore = "set RETAINED_BENCH_EXPORT and RETAINED_BENCH_DELTA to genuine workload files"]
    fn benchmark_retained_finish_same_parsed_mutation() {
        let export = std::env::var("RETAINED_BENCH_EXPORT").expect("RETAINED_BENCH_EXPORT");
        let delta = std::env::var("RETAINED_BENCH_DELTA").expect("RETAINED_BENCH_DELTA");
        let repetitions = std::env::var("RETAINED_BENCH_REPETITIONS").ok().map(|s| s.parse::<usize>().unwrap()).unwrap_or(7);
        assert!(repetitions >= 5);
        let config = serde_json::from_value(json!({"use_stdin":true,"num_threads":1,
            "permitted_axioms":["propext","Classical.choice","Quot.sound"],
            "nat_extension":true,"string_extension":true})).unwrap();
        let input = std::fs::read(export).unwrap();
        let mut builder = crate::parser::export_identity_builder(&input, config).unwrap();
        let prepare_clock = retained::Clock::start();
        builder.prepare_retained().unwrap();
        let (prepare_wall, prepare_cpu) = prepare_clock.elapsed();
        let prepared = builder.retained.take().unwrap();
        builder.retained = Some(prepared.clone());
        let update = builder.apply_delta(&std::fs::read_to_string(delta).unwrap()).unwrap();
        assert_eq!(update.finish_stats.mode, "retained", "benchmark requires edge-preserving input");
        let baseline = prepared.baseline();
        let positions = builder.declarations.iter().enumerate().filter(|(i, d)|
            d.own != baseline.declarations[*i].own.0).map(|(i, _)| i).collect::<Vec<_>>();
        let expected = serde_json::to_value(&update.index).unwrap();
        let mut samples = Vec::new();
        for repetition in 0..repetitions {
            let candidate = prepared.clone(); // explicit cold/reset work, never inside timer
            let measure_retained = |candidate: RetainedGraph| {
                let call = retained::Clock::start();
                let (index, mut stats) = candidate.finish(&builder, &positions, false).unwrap();
                (stats.finish_wall_seconds, stats.finish_cpu_seconds) = call.elapsed();
                (index, stats)
            };
            let measure_full = || {
                let call = retained::Clock::start();
                let (index, mut stats) = retained::full_finish(&builder, &positions, "benchmark_full_finish").unwrap();
                (stats.finish_wall_seconds, stats.finish_cpu_seconds) = call.elapsed();
                (index, stats)
            };
            let ((retained, stats), (full, full_stats)) = if repetition % 2 == 0 {
                let left = measure_retained(candidate);
                (left, measure_full())
            } else {
                let right = measure_full();
                (measure_retained(candidate), right)
            };
            assert_eq!(serde_json::to_value(&retained).unwrap(), expected);
            assert_eq!(serde_json::to_value(full).unwrap(), expected);
            samples.push(json!({"repetition":repetition,"parity":true,"retained":stats,
                "full_compute_wall_seconds":full_stats.compute_wall_seconds,
                "full_compute_cpu_seconds":full_stats.compute_cpu_seconds,
                "full_finish_wall_seconds":full_stats.finish_wall_seconds,
                "full_finish_cpu_seconds":full_stats.finish_cpu_seconds}));
        }
        println!("RETAINED_BENCH {}", json!({"schema":"mathgraph.retained-finish-microbenchmark.v1",
            "scope":"same parsed mutation; baseline graph clones outside timers; complete output parity",
            "repetitions":repetitions,"prepare_wall_seconds":prepare_wall,"prepare_cpu_seconds":prepare_cpu,
            "samples":samples}));
    }

    #[test]
    fn retained_topology_lives_until_the_owning_session_is_dropped() {
        let mut builder = graph(&[vec![], vec![0], vec![1], vec![]]);
        builder.prepare_retained().unwrap();
        let weak = Arc::downgrade(builder.retained_topology.as_ref().unwrap());
        assert_eq!(weak.strong_count(), 2);
        let prepared = builder.retained.take().unwrap();
        builder.declarations[0].own = digest_bytes(b"changed");
        let (index, stats) = prepared.finish(&builder, &[0], false).unwrap();
        equal_full(&builder, &index);
        assert_eq!(stats.touched_declarations, 3);
        // No per-declaration topology destruction happens before the response is emitted.
        assert_eq!(weak.strong_count(), 1);
        assert!(weak.upgrade().is_some());
        drop(builder);
        assert!(weak.upgrade().is_none());
    }

}
