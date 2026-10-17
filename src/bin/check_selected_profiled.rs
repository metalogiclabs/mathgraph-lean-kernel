//! Separate diagnostic replica of check-selected.
//! This is NOT an acceptance receipt or new parser. Every invocation still
//! parses the ENTIRE exact export and invokes the genuine selected kernel.
use serde_json::json;
use sokonanoda::util::Config;
use std::error::Error;
use std::path::Path;
use std::time::Instant;
use stumpalo::Arena;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

fn run() -> Result<(), Box<dyn Error>> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    let [config_path, indices_file] = args.as_slice() else {
        return Err("usage: check-selected-profiled CONFIG INDICES_FILE".into());
    };
    let total_started = Instant::now();
    let indices: Vec<usize> = serde_json::from_reader(std::fs::File::open(indices_file)?)?;
    let config = Config::try_from(Path::new(config_path))?;
    if config.parse_only {
        return Err("selected checks require parse_only=false".into());
    }
    let setup_seconds = total_started.elapsed().as_secs_f64();
    let arena = Arena::new();
    let parse_started = Instant::now();
    let (export, skipped_axioms) = config.to_export_file(arena.as_arena_ref())?;
    let parse_seconds = parse_started.elapsed().as_secs_f64();
    if !skipped_axioms.is_empty() {
        return Err("selected checks cannot use an export with skipped axioms".into());
    }
    // A zero-obligation selection does not permit bypassing parsing. The
    // protected negative fixtures exercise unused malformed DAG records.
    let check_started = Instant::now();
    let checked = export.check_selected_declars(&indices)?;
    let selected_check_seconds = check_started.elapsed().as_secs_f64();
    println!("{}", json!({
        "checked": checked,
        "total_declarations": export.declaration_count(),
        "scope": "selected_obligations_under_caller_trusted_environment",
        "profiling_scope": "diagnostic_exact_full_parser_and_actual_selected_kernel",
        "setup_seconds": setup_seconds,
        "parse_seconds": parse_seconds,
        "selected_check_seconds": selected_check_seconds,
        "total_seconds": total_started.elapsed().as_secs_f64()
    }));
    Ok(())
}

fn main() {
    match std::panic::catch_unwind(run) {
        Ok(Ok(())) => {}
        Ok(Err(error)) => {
            let declined = error.downcast_ref::<sokonanoda::util::Decline>().is_some();
            eprintln!("{error}");
            std::process::exit(if declined { 2 } else { 1 });
        }
        Err(_) => std::process::exit(1),
    }
}
