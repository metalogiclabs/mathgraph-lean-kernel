use sokonanoda::util::Config;
use std::error::Error;
use std::path::Path;
use std::time::{Duration, Instant};
use stumpalo::Arena;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

const EXIT_REJECT: i32 = 1;
const EXIT_DECLINE: i32 = 2;

fn main() {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    let out = match args.as_slice() {
        [] => Err(Box::from("This program expects a path to a configuration file.".to_string())),
        [p] if p == "-h" || p == "--help" => {
            println!("{}", HELP_LONG);
            return
        }
        [p] => run_caught(|| use_config(Path::new(p))),
        [flag, n, p] if flag == "--repeat" || flag == "--profile-repeat" => {
            let repeats = match n.parse::<usize>() {
                Ok(0) | Err(_) => {
                    eprintln!("{} expects a positive integer", flag);
                    std::process::exit(EXIT_REJECT)
                }
                Ok(n) => n,
            };
            if flag == "--profile-repeat" {
                run_caught(|| use_config_profiled(Path::new(p), repeats))
            } else {
                run_caught(|| use_config_repeated(Path::new(p), repeats))
            }
        }
        _ => Err(Box::from("Expected CONFIG, --repeat N CONFIG, or --profile-repeat N CONFIG.".to_string())),
    };
    match out {
        Ok(Some(msg)) => println!("{}", msg),
        Ok(None) => {}
        Err(e) => {
            let declined = e.downcast_ref::<sokonanoda::util::Decline>().is_some();
            eprintln!("{:?}", MainError(e));
            std::process::exit(if declined { EXIT_DECLINE } else { EXIT_REJECT })
        }
    }
}

fn run_caught<F>(f: F) -> Result<Option<String>, Box<dyn Error>>
where
    F: FnOnce() -> Result<Option<String>, Box<dyn Error>> + std::panic::UnwindSafe,
{
    match std::panic::catch_unwind(f) {
        Ok(r) => r,
        Err(_) => std::process::exit(EXIT_REJECT),
    }
}

// Benchmark/AI-loop probe: parse the config once, then execute the exact verifier
// repeatedly in one OS process. Each repetition still gets a fresh arena, parser,
// environment, and typecheck, so this changes no verification semantics. It only
// removes process/config startup from the measured loop.
fn use_config_repeated(config_path: &Path, repeats: usize) -> Result<Option<String>, Box<dyn Error>> {
    let cfg = Config::try_from(config_path)?;
    if cfg.use_stdin {
        return Err(Box::from("--repeat requires export_file_path; stdin cannot be replayed safely".to_string()));
    }
    let mut last = None;
    for _ in 0..repeats {
        last = use_config_value(cfg.clone())?;
    }
    Ok(last)
}

// Same verification semantics as --repeat, but measures the two dominant kernel
// phases from inside the live process: export parsing/environment construction and
// declaration typechecking. This is deliberately diagnostic-only.
fn use_config_profiled(config_path: &Path, repeats: usize) -> Result<Option<String>, Box<dyn Error>> {
    let cfg = Config::try_from(config_path)?;
    if cfg.use_stdin {
        return Err(Box::from("--profile-repeat requires export_file_path".to_string()));
    }
    let mut parse_total = Duration::ZERO;
    let mut check_total = Duration::ZERO;
    let mut declarations = 0usize;
    for _ in 0..repeats {
        let global_arena = Arena::new();
        let t_parse = Instant::now();
        let (export_file, _skipped_axioms) = cfg.clone().to_export_file(global_arena.as_arena_ref())?;
        parse_total += t_parse.elapsed();
        declarations = export_file.declars.len();
        if !export_file.config.parse_only {
            let t_check = Instant::now();
            export_file.check_all_declars();
            check_total += t_check.elapsed();
        }
    }
    let parse_ns = parse_total.as_nanos() / repeats as u128;
    let check_ns = check_total.as_nanos() / repeats as u128;
    Ok(Some(format!(
        "PROFILE repeats={} declarations={} parse_ns_per={} check_ns_per={} total_ns_per={}",
        repeats,
        declarations,
        parse_ns,
        check_ns,
        parse_ns + check_ns
    )))
}

// Returns an optional success message.
fn use_config(config_path: &Path) -> Result<Option<String>, Box<dyn Error>> {
    let cfg = Config::try_from(config_path)?;
    use_config_value(cfg)
}

fn use_config_value(cfg: Config) -> Result<Option<String>, Box<dyn Error>> {
    // Make sure the target pretty printer destination is accessible before doing any real work.
    let mut pp_destination = cfg.get_pp_destination()?;
    let global_arena = Arena::new();
    let (export_file, skipped_axioms) = cfg.to_export_file(global_arena.as_arena_ref())?;
    if export_file.config.parse_only {
        return Ok(Some(format!("Parsed {} declarations", export_file.declars.len())))
    }
    export_file.check_all_declars();
    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());
    if export_file.config.print_success_message {
        if pp_errs.is_empty() {
            if skipped_axioms.is_empty() {
                Ok(Some(format!("Checked {} declarations with no errors", export_file.declars.len())))
            } else {
                Ok(Some(format!("Checked {} declarations with no errors, skipping exported but unpermitted axioms {:?}", export_file.declars.len(), skipped_axioms)))
            }
        } else {
            Ok(Some(format!("Checked {} declarations with no typechecker errors, {} pretty printer errors: {:#?}", export_file.declars.len(), pp_errs.len(), pp_errs)))
        }
    } else if skipped_axioms.is_empty() {
        Ok(None)
    } else {
        Ok(Some(format!("Skipped exported but unpermitted axioms {:?}", skipped_axioms)))
    }
}

struct MainError(Box<dyn Error>);

impl std::fmt::Debug for MainError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result { write!(f, "{}\n\n{}", self.0, HELP_SHORT) }
}

const HELP_SHORT: &str = "run with `-h` or `--help` for help";
const HELP_LONG: &str = concat!(
    "sokonanoda",
    " ",
    env!("CARGO_PKG_VERSION"),
    "\n\n",
    env!("CARGO_PKG_DESCRIPTION"),
    "\n\n",
    "Usage: sokonanoda CONFIG | sokonanoda --repeat N CONFIG | sokonanoda --profile-repeat N CONFIG\n\n",
    "get more help at ",
    env!("CARGO_PKG_REPOSITORY"),
    "\n\n",
    include_str!("../README.md")
);
