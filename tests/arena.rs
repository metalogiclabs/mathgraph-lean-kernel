use sokonanoda::{AxiomPolicy, CheckError, Config, Rejection};
use std::fs;
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};

const MAX_EXPORT_BYTES: u64 = 64 * 1024 * 1024;

fn arena_root() -> Option<PathBuf> { std::env::var_os("LEAN_KERNEL_ARENA").map(PathBuf::from) }

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum ExpectedOutcome {
    Accept,
    Reject,
    Either,
}

fn expected_outcome(root: &Path, stem: &str) -> Option<ExpectedOutcome> {
    let spec = fs::read_to_string(root.join("tests").join(format!("{stem}.yaml"))).ok()?;
    spec.lines().find_map(|l| l.strip_prefix("outcome:")).map(|v| match v.trim() {
        "accept" => ExpectedOutcome::Accept,
        "reject" => ExpectedOutcome::Reject,
        "either" => ExpectedOutcome::Either,
        other => panic!("bad outcome {other:?} for {stem}"),
    })
}

fn collect_cases(root: &Path, out: &mut Vec<(PathBuf, ExpectedOutcome)>) {
    let Ok(entries) = fs::read_dir(root.join("_build/tests")) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().map(|e| e != "ndjson").unwrap_or(true) {
            continue;
        }
        if fs::metadata(&path).map(|m| m.len() > MAX_EXPORT_BYTES).unwrap_or(true) {
            continue;
        }
        let stem = path.file_stem().unwrap().to_string_lossy().into_owned();
        if let Some(expected) = expected_outcome(root, &stem) {
            out.push((path, expected));
        }
    }
}

enum Outcome {
    Accepted,
    ParseError(String),
    KernelRejected(String),
    UnexpectedPanic(String),
}

fn run_case(export: PathBuf) -> Outcome {
    std::thread::Builder::new()
        .stack_size(64 * 1024 * 1024)
        .spawn(move || run_case_inner(export))
        .expect("spawn case thread")
        .join()
        .unwrap_or_else(|_| Outcome::UnexpectedPanic("thread join failed".to_string()))
}

fn run_case_inner(export: PathBuf) -> Outcome {
    let cfg = Config {
        export_file_path: Some(export),
        use_stdin: false,
        axiom_policy: AxiomPolicy::AllowAll,
        parse_only: false,
        num_threads: 1,
        nat_extension: true,
        string_extension: true,
        ..Config::default()
    };
    let ef = match cfg.to_export_file() {
        Ok(ef) => ef,
        Err(e) if e.downcast_ref::<Rejection>().is_some() => return Outcome::KernelRejected(format!("{e}")),
        Err(e) => return Outcome::ParseError(format!("{e}")),
    };
    let result = panic::catch_unwind(AssertUnwindSafe(|| ef.check_all_declars()));
    match result {
        Ok(Ok(())) => Outcome::Accepted,
        Ok(Err(CheckError::Rejected(e))) => Outcome::KernelRejected(format!("{e}")),
        Ok(Err(e)) => Outcome::UnexpectedPanic(format!("{e}")),
        Err(payload) => {
            let msg = if let Some(s) = payload.downcast_ref::<&str>() {
                (*s).to_string()
            } else if let Some(s) = payload.downcast_ref::<String>() {
                s.clone()
            } else {
                "panic".to_string()
            };
            if msg == "def_eq failed" || msg.starts_with("def_eq") {
                Outcome::KernelRejected(msg)
            } else {
                Outcome::UnexpectedPanic(msg)
            }
        }
    }
}

#[test]
fn retained_source_regressions() {
    for (name, accepted) in [
        ("Empty", true), ("LevelIndexOutOfOrder", true), ("SparseNameIndex", true),
        ("ProofIrrelUnderBVar", true), ("KReduceDepthAlias", false),
        ("ProjFromProp", false), ("RuleDomainMismatch", false), ("UnlistedRecursor", false),
    ] {
        let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("test_resources").join(name).join("export");
        let outcome = run_case(p);
        match (accepted, outcome) {
            (true, Outcome::Accepted) | (false, Outcome::KernelRejected(_)) => {},
            (_, Outcome::ParseError(e) | Outcome::KernelRejected(e) | Outcome::UnexpectedPanic(e)) => panic!("{name}: {e}"),
            (false, Outcome::Accepted) => panic!("{name}: forged input accepted"),
        }
    }
}

#[test]
fn arena_fast_tier() {
    let Some(root) = arena_root() else {
        eprintln!("arena_fast_tier: LEAN_KERNEL_ARENA is not set; skipping");
        return;
    };
    let mut cases = Vec::new();
    collect_cases(&root, &mut cases);
    cases.sort();
    assert!(!cases.is_empty(), "no arena cases found under {}", root.display());

    if std::env::var("LEAN_KERNEL_ARENA_VERBOSE").is_err() {
        panic::set_hook(Box::new(|_| {}));
    }

    let mut failures = Vec::new();
    for (export, expected) in &cases {
        let outcome = run_case(export.clone());
        let (got_accept, detail) = match &outcome {
            Outcome::Accepted => (true, "(accepted)".to_string()),
            Outcome::ParseError(e) => (false, format!("parse: {e}")),
            Outcome::KernelRejected(e) => (false, format!("kernel: {e}")),
            Outcome::UnexpectedPanic(e) => (false, format!("panic: {e}")),
        };
        let mismatch = match expected {
            ExpectedOutcome::Accept => !got_accept || matches!(outcome, Outcome::UnexpectedPanic(_)),
            ExpectedOutcome::Reject => got_accept,
            ExpectedOutcome::Either => false,
        };
        if mismatch {
            let name = export.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
            let expected = match expected {
                ExpectedOutcome::Accept => "accept",
                ExpectedOutcome::Reject => "reject",
                ExpectedOutcome::Either => "either",
            };
            failures.push(format!("{name}: expected {expected}, got accept={got_accept} ({detail})"));
        }
    }

    if !failures.is_empty() {
        panic!("{}/{} arena cases mismatched:\n{}", failures.len(), cases.len(), failures.join("\n"));
    }
}
