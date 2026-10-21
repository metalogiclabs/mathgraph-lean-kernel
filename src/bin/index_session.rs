//! Baseline-anchored, or opt-in predecessor-chain, retained identity updates. Cache witnesses only;
//! authenticated producer admission and complete selected checking are external.
use serde::Deserialize;
use serde_json::json;
use sokonanoda::util::Config;
use std::error::Error;
use std::io::{BufRead, Write};
use std::path::Path;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    delta_path: String,
}

fn emit(value: &impl serde::Serialize) -> Result<(), Box<dyn Error>> {
    let mut out = std::io::stdout().lock();
    serde_json::to_writer(&mut out, value)?;
    out.write_all(b"\n")?;
    out.flush()?;
    Ok(())
}

fn run() -> Result<(), Box<dyn Error>> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    let config_path = args.first().ok_or("usage: index-session CONFIG [--full-index|--sparse-response]")?;
    let flags = &args[1..];
    let revision_chain = flags.iter().any(|f| f == "--revision-chain");
    let valid_flags = if revision_chain {
        flags.len() <= 2 && flags.iter().all(|f|
            f == "--full-index" || f == "--sparse-response" || f == "--revision-chain") &&
            flags.iter().filter(|f| *f == "--revision-chain").count() == 1
    } else {
        flags.len() <= 1 && flags.iter().all(|f| f == "--full-index" || f == "--sparse-response")
    };
    if !valid_flags {
        return Err("unsupported or duplicated index-session flags".into());
    }
    let full_index = flags.iter().any(|f| f == "--full-index");
    let sparse_response = flags.iter().any(|f| f == "--sparse-response");
    if full_index && sparse_response {
        return Err("sparse response requires retained SCC baseline".into());
    }
    let config = Config::try_from(Path::new(config_path))?;
    let path = config.export_file_path.as_ref().ok_or("index-session requires baseline export_file_path")?;
    let file = std::fs::File::open(path)?;
    let map = unsafe { memmap2::Mmap::map(&file) }?;
    let mut identity = sokonanoda::parser::export_identity_builder(&map, config)?;
    drop(map);
    // A/B control: same parser and binary; only the identity finish algorithm
    // differs. Both return the same canonical full index and require the same
    // source attestation plus independent selected checker downstream.
    let initial_index = if full_index { identity.finish()? } else { identity.prepare_retained()? };
    let mut ready = json!({"status":"ready", "index":&initial_index});
    if revision_chain {
        ready["chain_mode"] = json!(true);
        ready["revision"] = json!(0);
    }
    emit(&ready)?;
    let mut previous_index = initial_index;
    let mut revision = 0u64;
    for line in std::io::stdin().lock().lines() {
        // Struct deserialization rejects duplicate fields, unknown fields,
        // malformed JSON and unescaped controls before any DAG mutation.
        let request: Request = serde_json::from_str(&line?)?;
        let delta = std::fs::read_to_string(request.delta_path)?;
        let next_revision = revision.checked_add(1).ok_or("identity revision counter exhausted")?;
        let update = if revision_chain { identity.apply_chained_delta(&delta)? }
            else { identity.apply_delta(&delta)? };
        let metadata = json!({
            "status":"indexed",
            "rows_processed":update.rows_processed, "dag_rows":update.dag_rows,
            "replaced_names":update.replaced_names,
            "retained_graph_used":update.retained_graph_used,
            "recomputed_sccs":update.recomputed_sccs,
            "finish_nanos":update.finish_nanos,
            "finish_mode":if full_index {"full"} else {"retained"},
        });
        let mut response = metadata;
        if revision_chain {
            response["chain_mode"] = json!(true);
            response["revision"] = json!(next_revision);
        }
        if sparse_response && update.retained_graph_used {
            if let Some(patch) = update.index.sparse_patch_against(&previous_index)? {
                response["index_wire"] = json!("baseline_patch_v1");
                response["index_patch"] = patch;
            } else {
                response["index_wire"] = json!("full_index_v1");
                response["index"] = serde_json::to_value(&update.index)?;
            }
        } else {
            response["index_wire"] = json!("full_index_v1");
            response["index"] = serde_json::to_value(&update.index)?;
        }
        emit(&response)?;
        if revision_chain {
            previous_index = update.index;
            revision = next_revision;
        }
    }
    Ok(())
}

fn main() {
    let result = std::panic::catch_unwind(run);
    let error = match result {
        Ok(Ok(())) => return,
        Ok(Err(error)) => error.to_string(),
        Err(payload) => payload
            .downcast_ref::<String>()
            .cloned()
            .or_else(|| payload.downcast_ref::<&str>().map(|s| (*s).to_owned()))
            .unwrap_or_else(|| "identity session panicked".to_owned()),
    };
    let _ = emit(&json!({"status":"error", "error":error,
        "scope":"identity_cache_witness_only_session_terminated"}));
    std::process::exit(1);
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn request_decoder_refuses_duplicates_unknown_fields_and_controls() {
        for raw in [
            r#"{"delta_path":"a","delta_path":"b"}"#,
            r#"{"delta_path":"a","authority":"trusted"}"#,
            "{\"delta_path\":\"bad\u{0001}\"}",
            r#"{}"#,
        ] {
            assert!(serde_json::from_str::<Request>(raw).is_err());
        }
    }
}
