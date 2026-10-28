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
