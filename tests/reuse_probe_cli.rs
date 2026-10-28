#[cfg(feature = "reuse-probe")]
#[test]
fn instrumented_real_export_emits_unqualified_census_without_changing_acceptance() {
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_sokonanoda"))
        .arg("test_resources/ProofIrrelUnderBVar/config.json")
        .output()
        .expect("run source-owned proof-irrelevance export");
    assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
    let stderr = String::from_utf8_lossy(&output.stderr);
    let record = stderr
        .lines()
        .find_map(|line| line.strip_prefix("MG_REUSE_PROBE="))
        .expect("feature-gated checker must emit a read-only census");
    let report: serde_json::Value = serde_json::from_str(record).expect("valid report JSON");
    assert_eq!(report["qualification"], "CANDIDATE_IDENTITY_ONLY");
    assert_eq!(report["speedup_measured"], false);
    assert_eq!(report["sample_denominator"], 256);
    assert!(report["counts"]["cache_resets"].as_u64().unwrap_or(0) >= 1);
}

#[cfg(feature = "reuse-probe")]
#[test]
fn full_mathlib_workflow_config_uses_the_native_stdin_interface() {
    let fixture = std::fs::File::open("test_resources/ProofIrrelUnderBVar/export")
        .expect("source-owned proof-irrelevance export");
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_sokonanoda"))
        .arg("experiments/semantic_reuse_full_mathlib_config.json")
        .stdin(fixture)
        .output()
        .expect("run native JSON config, not upstream CLI flags");
    assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
    assert!(String::from_utf8_lossy(&output.stdout).contains("Checked 7 declarations with no errors"));
    assert!(String::from_utf8_lossy(&output.stderr).contains("MG_REUSE_PROBE="));
}
