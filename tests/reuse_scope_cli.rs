#![cfg(feature = "reuse-scope-probe")]

#[test]
fn native_checker_emits_read_only_source_scope_record_without_changing_acceptance() {
    let fixture = std::fs::File::open("test_resources/ProofIrrelUnderBVar/export")
        .expect("source-owned Lean export");
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_sokonanoda"))
        .arg("experiments/semantic_reuse_full_mathlib_config.json")
        .stdin(fixture)
        .output()
        .expect("run native checker with source-owned input");
    assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "Checked 7 declarations with no errors");
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("MG_REUSE_PROBE="), "V1 identity census must remain intact");
    let raw = stderr
        .lines()
        .find_map(|line| line.strip_prefix("MG_REUSE_SCOPE="))
        .unwrap_or_else(|| panic!("V2 source-context diagnostic record missing; binary={}, stderr={stderr}", env!("CARGO_BIN_EXE_sokonanoda")));
    let report: serde_json::Value = serde_json::from_str(raw).expect("machine-readable scope report");
    assert_eq!(report["qualification"], "CANDIDATE_CONTEXT_DIAGNOSTIC_ONLY");
    assert_eq!(report["source_support_limit_nodes"], 8192);
    assert_eq!(report["sound_persistent_reuse_implemented"], false);
    assert_eq!(report["speedup_measured"], false);
    assert!(report["counts"]["strict_same_cutoff"].is_number());
    assert!(report["counts"]["advanced_visible_direct_support"].is_number());
}
