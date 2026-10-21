//! One-shot or opt-in predecessor-chain retained genuine Rust parser, *not* an independent acceptance
//! certificate. The caller must independently HMAC-authenticate the exact
//! original Lean/Std baseline, source-owned delta, applicable dependency cone
//! and issuer policy. This process checks byte hashes and every changed node,
//! replaces only same-kind simple declarations in their existing ordered slots,
//! then uses the unmodified Rust selected checker against the parsed state.
use serde::Deserialize;
use serde_json::json;
use sha2::{Digest, Sha256};
use sokonanoda::parser::Parser;
use sokonanoda::util::Config;
use std::error::Error;
use std::fmt::Write as FmtWrite;
use std::io::{self, Write};
use std::path::Path;
use std::time::Instant;
use stumpalo::Arena;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    delta_path: String,
    delta_sha256: String,
    selected_indices_path: String,
    expected_changed_names: Vec<String>,
}

fn sha256(bytes: &[u8]) -> String {
    let mut s = String::with_capacity(64);
    for byte in Sha256::digest(bytes) {
        write!(&mut s, "{byte:02x}").expect("ASCII hex formatting");
    }
    s
}
fn validate_hex_id(s: &str) -> Result<(), Box<dyn Error>> {
    if s.len() != 64 ||
       !s.as_bytes().iter().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(b)) {
        return Err("invalid trusted hash input".into());
    }
    Ok(())
}
fn emit(value: &impl serde::Serialize) -> Result<(), Box<dyn Error>> {
    let mut stdout = io::stdout().lock();
    serde_json::to_writer(&mut stdout, value)?;
    stdout.write_all(b"\n")?;
    stdout.flush()?;
    Ok(())
}
fn run() -> Result<(), Box<dyn Error>> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    let revision_chain = args.last().is_some_and(|arg| arg == "--revision-chain");
    let arguments = if revision_chain { &args[..args.len()-1] } else { args.as_slice() };
    let [config_file, authenticated_baseline_sha256] = arguments else {
        return Err("usage: check-selected-retained-session CONFIG AUTHENTICATED_BASE_SHA256".into());
    };
    validate_hex_id(authenticated_baseline_sha256)?;
    let config = Config::try_from(Path::new(config_file))?;
    if config.parse_only || config.use_stdin {
        return Err("retained selected kernel requires full parse and export path".into());
    }
    let input = config.export_file_path.as_ref()
        .ok_or("retained source session requires baseline export file")?;
    let file = std::fs::File::open(input)?;
    let map = unsafe { memmap2::Mmap::map(&file) }?;
    if sha256(&map) != *authenticated_baseline_sha256 {
        return Err("retained parser baseline bytes differ from authenticated source".into());
    }
    let arena = Arena::new();
    let mut parser = Parser::with_input_len(
        arena.as_arena_ref(), std::io::empty(), config, map.len());
    let started = Instant::now();
    let total = parser.run_retained_baseline(&map)?;
    let baseline_parse_seconds = started.elapsed().as_secs_f64();
    drop(map);
    let mut ready = json!({
        "status": "ready",
        "total_declarations": total,
        "baseline_sha256": authenticated_baseline_sha256,
        "baseline_parse_seconds": baseline_parse_seconds,
        "scope": "retained_parser_low_level_witness_not_acceptance_authority"
    });
    if revision_chain {
        ready["chain_mode"] = json!(true);
        ready["revision"] = json!(0);
    }
    emit(&ready)?;

    // The default still consumes exactly one baseline-anchored parser. Chain
    // mode retains each checked predecessor; any error terminates the process.
    let mut parser = Some(parser);
    let mut revision = 0u64;
    loop {
        let mut request_bytes = String::new();
        if io::stdin().read_line(&mut request_bytes)? == 0 {
            if revision_chain { break; }
            return Err("retained parser missing authenticated delta request".into());
        }
        let request: Request = serde_json::from_str(&request_bytes)?;
        validate_hex_id(&request.delta_sha256)?;
        let delta = std::fs::read(request.delta_path)?;
        if sha256(&delta) != request.delta_sha256 {
            return Err("retained parser changed bytes failed attested hash check".into());
        }
        let indices: Vec<usize> = serde_json::from_reader(
            std::fs::File::open(request.selected_indices_path)?)?;
        let next_revision = revision.checked_add(1).ok_or("retained parser revision counter exhausted")?;
        let (checked, total_again, parse_and_finish_seconds, selected_check_seconds) =
            if revision_chain {
                parser.as_mut().ok_or("missing retained predecessor")?
                    .check_retained_simple_chained_delta(&delta, &request.expected_changed_names, &indices)?
            } else {
                parser.take().ok_or("missing retained baseline")?
                    .check_retained_simple_delta(&delta, &request.expected_changed_names, &indices)?
            };
        if total_again != total || checked != indices.len() {
            return Err("retained parser obligation count or fixed declaration schedule changed".into());
        }
        let mut response = json!({
            "status": "checked",
            "code": 0,
            "checked": checked,
            "total_declarations": total_again,
            "scope": "selected_obligations_under_caller_trusted_environment",
            "kernel": "sokonanoda_real_selected_declaration_check",
            "delta_parse_and_finish_seconds": parse_and_finish_seconds,
            "selected_check_seconds": selected_check_seconds
        });
        if revision_chain {
            response["chain_mode"] = json!(true);
            response["revision"] = json!(next_revision);
        }
        emit(&response)?;
        if !revision_chain { break; }
        revision = next_revision;
    }
    Ok(())
}
fn main() {
    let r = std::panic::catch_unwind(run);
    let error = match r {
        Ok(Ok(())) => return,
        Ok(Err(e)) => e.to_string(),
        Err(p) => p.downcast_ref::<String>()
            .cloned()
            .or_else(|| p.downcast_ref::<&str>().map(|s| (*s).to_owned()))
            .unwrap_or_else(|| "retained genuine Rust parser or kernel panicked".to_owned())
    };
    let _ = emit(&json!({
        "status": "rejected", "code": 1,
        "reason": error,
        "scope": "retained_parser_low_level_refusal_not_issuer_acceptance"
    }));
    std::process::exit(1);
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn sha_guard_refuses_uppercase_short_and_non_hex() {
        let uppercase = "F".repeat(64);
        let non_hex = "g".repeat(64);
        for s in ["short", uppercase.as_str(), non_hex.as_str()] {
            assert!(validate_hex_id(s).is_err());
        }
        assert!(validate_hex_id(&"a".repeat(64)).is_ok());
    }
    #[test]
    fn request_decoder_refuses_unknown_duplicate_and_missing_fields() {
        for s in [
            r#"{"delta_path":"a","delta_sha256":"b","selected_indices_path":"c","expected_changed_names":[],"authority":"forged"}"#,
            r#"{"delta_path":"a","delta_path":"b","delta_sha256":"c","selected_indices_path":"d","expected_changed_names":[]}"#,
            r#"{"delta_path":"a"}"#,
        ] {
            assert!(serde_json::from_str::<Request>(s).is_err());
        }
    }
}
