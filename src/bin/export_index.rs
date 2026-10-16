//! Cache identity producer using the same parser as ordinary verification.
use sokonanoda::util::Config;
use std::error::Error;
use std::io::{Read, Write};
use std::path::Path;
#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;
fn run() -> Result<sokonanoda::identity::ExportIdentityIndex, Box<dyn Error>> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    let [config_path] = args.as_slice() else {
        return Err("usage: export-index CONFIG".into());
    };
    let config = Config::try_from(Path::new(config_path))?;
    if let Some(path) = config.export_file_path.as_ref() {
        let file = std::fs::File::open(path)?;
        let map = unsafe { memmap2::Mmap::map(&file) }?;
        sokonanoda::parser::export_identity(&map, config)
    } else {
        let mut input = Vec::new();
        std::io::stdin().read_to_end(&mut input)?;
        sokonanoda::parser::export_identity(&input, config)
    }
}
fn main() {
    match std::panic::catch_unwind(run) {
        Ok(Ok(index)) => {
            let mut bytes = serde_json::to_vec(&index).unwrap();
            bytes.push(b'\n');
            std::io::stdout().lock().write_all(&bytes).unwrap();
        }
        result => {
            let (error, stage, declined) = match result {
                Ok(Err(e)) => {
                    let stage = if e.downcast_ref::<sokonanoda::parser::IdentityError>().is_some() {
                        "identity"
                    } else {
                        "kernel_parse"
                    };
                    let declined = stage == "identity" || e.downcast_ref::<sokonanoda::util::Decline>().is_some();
                    (e.to_string(), stage, declined)
                }
                Err(p) => {
                    let message = if let Some(s) = p.downcast_ref::<String>() {
                        s.clone()
                    } else if let Some(s) = p.downcast_ref::<&str>() {
                        (*s).to_owned()
                    } else {
                        "kernel parser panicked".to_owned()
                    };
                    (message, "kernel_parse", false)
                }
                _ => unreachable!(),
            };
            serde_json::to_writer(
                std::io::stdout().lock(),
                &serde_json::json!({"status":"error","error":error,"stage":stage,"declined":declined}),
            )
            .unwrap();
            std::io::stdout().flush().unwrap();
            std::process::exit(if declined { 2 } else { 1 });
        }
    }
}
