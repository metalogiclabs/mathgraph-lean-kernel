use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn unique_path(label: &str) -> PathBuf {
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
    std::env::temp_dir().join(format!("sokonanoda-cli-{label}-{}-{stamp}.json", std::process::id()))
}

fn checker() -> Command { Command::new(env!("CARGO_BIN_EXE_sokonanoda")) }

#[test]
fn structured_success_has_matching_exit_and_record() {
    let result = unique_path("accepted");
    let status = checker()
        .args(["--result-file", result.to_str().unwrap(), "test_resources/LevelIndexOutOfOrder/config.json"])
        .status()
        .unwrap();
    assert_eq!(status.code(), Some(0));
    assert_eq!(
        fs::read_to_string(&result).unwrap(),
        "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"accepted\",\"reason_code\":\"checked\"}\n"
    );
    fs::remove_file(result).unwrap();
}

#[test]
fn typed_proof_rejection_has_matching_exit_and_record() {
    let result = unique_path("rejected");
    let status = checker()
        .args(["--result-file", result.to_str().unwrap(), "test_resources/KReduceDepthAlias/config.json"])
        .status()
        .unwrap();
    assert_eq!(status.code(), Some(1));
    assert_eq!(
        fs::read_to_string(&result).unwrap(),
        "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"rejected\",\"reason_code\":\"declaration_type_mismatch\"}\n"
    );
    fs::remove_file(result).unwrap();
}

#[test]
fn configuration_error_is_internal_not_rejected() {
    let result = unique_path("internal");
    let missing = unique_path("missing-config");
    let status =
        checker().args(["--result-file", result.to_str().unwrap(), missing.to_str().unwrap()]).status().unwrap();
    assert_eq!(status.code(), Some(3));
    assert_eq!(
        fs::read_to_string(&result).unwrap(),
        "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"internal_failure\",\"reason_code\":\"checker_error\"}\n"
    );
    fs::remove_file(result).unwrap();
}

#[test]
fn parse_only_cannot_produce_structured_acceptance() {
    let result = unique_path("parse-only-result");
    let config = unique_path("parse-only-config");
    fs::write(
        &config,
        b"{\"export_file_path\":\"test_resources/LevelIndexOutOfOrder/export\",\"parse_only\":true,\"unsafe_permit_all_axioms\":true,\"unpermitted_axiom_hard_error\":false}\n",
    )
    .unwrap();
    let status =
        checker().args(["--result-file", result.to_str().unwrap(), config.to_str().unwrap()]).status().unwrap();
    assert_eq!(status.code(), Some(3));
    assert_eq!(
        fs::read_to_string(&result).unwrap(),
        "{\"schema_version\":1,\"protocol\":\"sokonanoda_result_v1\",\"outcome\":\"internal_failure\",\"reason_code\":\"checker_error\"}\n"
    );
    fs::remove_file(result).unwrap();
    fs::remove_file(config).unwrap();
}

#[test]
fn structured_mode_never_overwrites_reserved_result_path() {
    let result = unique_path("reserved");
    fs::write(&result, b"reserved\n").unwrap();
    let status = checker()
        .args(["--result-file", result.to_str().unwrap(), "test_resources/LevelIndexOutOfOrder/config.json"])
        .status()
        .unwrap();
    assert_eq!(status.code(), Some(3));
    assert_eq!(fs::read(&result).unwrap(), b"reserved\n");
    fs::remove_file(result).unwrap();
}

#[test]
fn legacy_invocation_remains_available() {
    let status = checker().arg("test_resources/LevelIndexOutOfOrder/config.json").status().unwrap();
    assert_eq!(status.code(), Some(0));
}
