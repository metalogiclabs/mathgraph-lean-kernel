//! One baseline-anchored retained identity update. Cache witnesses only;
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
    let [config_path] = args.as_slice() else {
        return Err("usage: index-session CONFIG".into());
    };
    let config = Config::try_from(Path::new(config_path))?;
    let path = config.export_file_path.as_ref().ok_or("index-session requires baseline export_file_path")?;
    let file = std::fs::File::open(path)?;
    let map = unsafe { memmap2::Mmap::map(&file) }?;
    let mut identity = sokonanoda::parser::export_identity_builder(&map, config)?;
    drop(map);
    emit(&json!({"status":"ready", "index":identity.prepare_retained()?}))?;
    for line in std::io::stdin().lock().lines() {
        // Struct deserialization rejects duplicate fields, unknown fields,
        // malformed JSON and unescaped controls before any DAG mutation.
        let request: Request = serde_json::from_str(&line?)?;
        let delta = std::fs::read_to_string(request.delta_path)?;
        let update = identity.apply_delta(&delta)?;
        emit(&json!({"status":"indexed", "index":update.index,
            "rows_processed":update.rows_processed, "dag_rows":update.dag_rows,
            "replaced_names":update.replaced_names,
            "retained_graph_used":update.retained_graph_used,
            "recomputed_sccs":update.recomputed_sccs}))?;
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
