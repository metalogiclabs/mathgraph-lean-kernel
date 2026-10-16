//! Adapter primitive, not a standalone certificate for a full export.
//! Omitted declarations must be supplied by a caller-validated accepted environment.

use sokonanoda::util::Config;
use std::error::Error;
use std::path::Path;
use stumpalo::Arena;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

fn run() -> Result<(), Box<dyn Error>> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    let [config_path, indices_file] = args.as_slice() else {
        return Err("usage: check-selected CONFIG INDICES_FILE".into());
    };
    let indices: Vec<usize> = serde_json::from_reader(std::fs::File::open(indices_file)?)?;
    let config = Config::try_from(Path::new(config_path))?;
    if config.parse_only {
        return Err("selected checks require parse_only=false".into());
    }
    let arena = Arena::new();
    let (export, skipped_axioms) = config.to_export_file(arena.as_arena_ref())?;
    if !skipped_axioms.is_empty() {
        return Err("selected checks cannot use an export with skipped axioms".into());
    }
    let checked = export.check_selected_declars(&indices)?;
    println!(
        "{}",
        serde_json::json!({
            "checked": checked,
            "total_declarations": export.declaration_count(),
            "scope": "selected_obligations_under_caller_trusted_environment"
        })
    );
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
