use serde::Serialize;
use std::any::Any;
use std::ffi::OsString;
use std::fs::{self, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

pub const PROTOCOL: &str = "sokonanoda_result_v1";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProofRejectionCode {
    DuplicateUniverseParameters,
    TheoremTypeNotProp,
    DeclarationTypeMismatch,
}

impl ProofRejectionCode {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::DuplicateUniverseParameters => "duplicate_universe_parameters",
            Self::TheoremTypeNotProp => "theorem_type_not_prop",
            Self::DeclarationTypeMismatch => "declaration_type_mismatch",
        }
    }
}

/// A deliberately typed checker rejection.
///
/// Only validation failures that are known to be properties of the checked
/// export may use this payload. Unexpected assertions and panics must remain
/// untyped so callers classify them as internal failures.
#[derive(Debug)]
pub struct ProofRejected {
    code: ProofRejectionCode,
}

impl ProofRejected {
    pub const fn code(&self) -> ProofRejectionCode { self.code }
}

pub(crate) fn reject_proof(code: ProofRejectionCode) -> ! { std::panic::panic_any(ProofRejected { code }) }

pub fn rejection_from_panic(payload: &(dyn Any + Send)) -> Option<ProofRejectionCode> {
    payload.downcast_ref::<ProofRejected>().map(ProofRejected::code)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResultOutcome {
    Accepted,
    Rejected(ProofRejectionCode),
    Declined,
    InternalFailure,
}

impl ResultOutcome {
    const fn fields(self) -> (&'static str, &'static str) {
        match self {
            Self::Accepted => ("accepted", "checked"),
            Self::Rejected(code) => ("rejected", code.as_str()),
            Self::Declined => ("declined", "unsupported_input"),
            Self::InternalFailure => ("internal_failure", "checker_error"),
        }
    }
}

#[derive(Serialize)]
struct ResultRecord {
    schema_version: u8,
    protocol: &'static str,
    outcome: &'static str,
    reason_code: &'static str,
}

static TEMP_COUNTER: AtomicU64 = AtomicU64::new(0);

fn temp_path(path: &Path) -> io::Result<PathBuf> {
    let name =
        path.file_name().ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "result path has no file name"))?;
    let serial = TEMP_COUNTER.fetch_add(1, Ordering::Relaxed);
    let mut temp_name = OsString::from(".");
    temp_name.push(name);
    temp_name.push(format!(".tmp.{}.{}", std::process::id(), serial));
    Ok(path.with_file_name(temp_name))
}

/// Publish one complete result record without replacing an existing path.
///
/// A hard link makes the fully written temporary inode visible at `path` in a
/// single operation. This is intentionally fail-closed: existing result files,
/// malformed paths, and filesystems without hard-link support are errors.
pub fn write_result(path: &Path, outcome: ResultOutcome) -> io::Result<()> {
    let (outcome, reason_code) = outcome.fields();
    let record = ResultRecord { schema_version: 1, protocol: PROTOCOL, outcome, reason_code };
    let mut bytes = serde_json::to_vec(&record).expect("serializing a static result record cannot fail");
    bytes.push(b'\n');

    let temp = temp_path(path)?;
    let mut file = OpenOptions::new().write(true).create_new(true).open(&temp)?;
    let result = (|| {
        file.write_all(&bytes)?;
        file.sync_all()?;
        drop(file);
        fs::hard_link(&temp, path)?;
        Ok(())
    })();
    match result {
        Err(error) => {
            let _ = fs::remove_file(&temp);
            Err(error)
        }
        Ok(()) => {
            if let Err(error) = fs::remove_file(&temp) {
                eprintln!("warning: failed to remove result temporary file {}: {error}", temp.display());
            }
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn unique_path(label: &str) -> PathBuf {
        let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        std::env::temp_dir().join(format!("sokonanoda-{label}-{}-{stamp}.json", std::process::id()))
    }

    #[test]
    fn canonical_records_are_closed_and_stable() {
        let cases = [
            (
                ResultOutcome::Accepted,
                "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"accepted\",\"reason_code\":\"checked\"}\n",
            ),
            (
                ResultOutcome::Rejected(ProofRejectionCode::DeclarationTypeMismatch),
                "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"rejected\",\"reason_code\":\"declaration_type_mismatch\"}\n",
            ),
            (
                ResultOutcome::Declined,
                "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"declined\",\"reason_code\":\"unsupported_input\"}\n",
            ),
            (
                ResultOutcome::InternalFailure,
                "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"internal_failure\",\"reason_code\":\"checker_error\"}\n",
            ),
        ];
        for (outcome, expected) in cases {
            let path = unique_path("canonical");
            write_result(&path, outcome).unwrap();
            assert_eq!(fs::read_to_string(&path).unwrap(), expected);
            fs::remove_file(path).unwrap();
        }
    }

    #[test]
    fn result_publication_refuses_to_replace_a_file() {
        let path = unique_path("no-replace");
        fs::write(&path, b"reserved\n").unwrap();
        let error = write_result(&path, ResultOutcome::Accepted).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::AlreadyExists);
        assert_eq!(fs::read(&path).unwrap(), b"reserved\n");
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn result_publication_leaves_no_temporary_file() {
        let directory = unique_path("cleanup-directory");
        fs::create_dir(&directory).unwrap();
        let path = directory.join("result.json");
        write_result(&path, ResultOutcome::Accepted).unwrap();
        assert_eq!(fs::read_dir(&directory).unwrap().count(), 1);
        fs::remove_file(path).unwrap();
        fs::remove_dir(directory).unwrap();
    }

    #[test]
    fn concurrent_publication_has_exactly_one_winner() {
        use std::sync::{Arc, Barrier};

        let directory = unique_path("concurrent-directory");
        fs::create_dir(&directory).unwrap();
        let path = directory.join("result.json");
        let barrier = Arc::new(Barrier::new(2));
        let handles: Vec<_> = [ResultOutcome::Accepted, ResultOutcome::InternalFailure]
            .into_iter()
            .map(|outcome| {
                let path = path.clone();
                let barrier = Arc::clone(&barrier);
                std::thread::spawn(move || {
                    barrier.wait();
                    write_result(&path, outcome)
                })
            })
            .collect();
        let results: Vec<_> = handles.into_iter().map(|handle| handle.join().unwrap()).collect();
        assert_eq!(results.iter().filter(|result| result.is_ok()).count(), 1);
        assert_eq!(
            results
                .iter()
                .filter_map(|result| result.as_ref().err())
                .filter(|error| error.kind() == io::ErrorKind::AlreadyExists)
                .count(),
            1
        );
        let record = fs::read_to_string(&path).unwrap();
        assert!(
            record
                == "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"accepted\",\"reason_code\":\"checked\"}\n"
                || record
                    == "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"internal_failure\",\"reason_code\":\"checker_error\"}\n"
        );
        assert_eq!(fs::read_dir(&directory).unwrap().count(), 1);
        fs::remove_file(path).unwrap();
        fs::remove_dir(directory).unwrap();
    }

    #[test]
    fn only_typed_rejections_are_recognized() {
        let typed = std::panic::catch_unwind(|| reject_proof(ProofRejectionCode::TheoremTypeNotProp)).unwrap_err();
        assert_eq!(rejection_from_panic(typed.as_ref()), Some(ProofRejectionCode::TheoremTypeNotProp));
        let untyped = std::panic::catch_unwind(|| panic!("not a proof rejection")).unwrap_err();
        assert_eq!(rejection_from_panic(untyped.as_ref()), None);
    }

    #[derive(Deserialize)]
    struct VectorSet {
        protocol: String,
        vectors: Vec<Vector>,
    }

    #[derive(Deserialize)]
    struct Vector {
        name: String,
        exit_code: i32,
        record_utf8: String,
    }

    #[test]
    fn language_neutral_vectors_match_the_producer() {
        let vectors: VectorSet =
            serde_json::from_str(include_str!("../protocol/sokonanoda-result-v1-vectors.json")).unwrap();
        assert_eq!(vectors.protocol, PROTOCOL);
        let expected = [
            ("accepted", 0, ResultOutcome::Accepted),
            (
                "rejected_duplicate_universe_parameters",
                1,
                ResultOutcome::Rejected(ProofRejectionCode::DuplicateUniverseParameters),
            ),
            ("rejected_theorem_type_not_prop", 1, ResultOutcome::Rejected(ProofRejectionCode::TheoremTypeNotProp)),
            (
                "rejected_declaration_type_mismatch",
                1,
                ResultOutcome::Rejected(ProofRejectionCode::DeclarationTypeMismatch),
            ),
            ("declined", 2, ResultOutcome::Declined),
            ("internal_failure", 3, ResultOutcome::InternalFailure),
        ];
        assert_eq!(vectors.vectors.len(), expected.len());
        for (vector, (name, exit, outcome)) in vectors.vectors.iter().zip(expected) {
            assert_eq!(vector.name, name);
            assert_eq!(vector.exit_code, exit);
            let path = unique_path("vector");
            write_result(&path, outcome).unwrap();
            assert_eq!(fs::read_to_string(&path).unwrap(), vector.record_utf8);
            fs::remove_file(path).unwrap();
        }
    }
}
