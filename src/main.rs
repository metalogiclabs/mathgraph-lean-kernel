use sokonanoda::result_protocol::{rejection_from_panic, write_result, ResultOutcome};
use sokonanoda::util::{Config, Decline};
use std::error::Error;
use std::path::{Path, PathBuf};
use stumpalo::Arena;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

const EXIT_REJECT: i32 = 1;
const EXIT_DECLINE: i32 = 2;
const EXIT_INTERNAL: i32 = 3;

enum Invocation {
    Help,
    Run { config: PathBuf, result: Option<PathBuf> },
}

fn parse_args() -> Result<Invocation, String> {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    match args.as_slice() {
        [arg] if arg == "-h" || arg == "--help" => Ok(Invocation::Help),
        [config] => Ok(Invocation::Run { config: config.into(), result: None }),
        [flag, result, config] if flag == "--result-file" =>
            Ok(Invocation::Run { config: config.into(), result: Some(result.into()) }),
        _ => Err("expected CONFIG or --result-file RESULT CONFIG".to_string()),
    }
}

fn main() {
    let invocation = match parse_args() {
        Ok(Invocation::Help) => {
            println!("{}", HELP_LONG);
            return
        }
        Ok(run @ Invocation::Run { .. }) => run,
        Err(error) => {
            eprintln!("{:?}", MainError(Box::from(error)));
            std::process::exit(EXIT_REJECT)
        }
    };
    let Invocation::Run { config, result } = invocation else { unreachable!() };
    if let Some(result_path) = result {
        run_structured(&config, &result_path)
    } else {
        run_legacy(&config)
    }
}

fn run_legacy(config: &Path) {
    let out = match std::panic::catch_unwind(|| use_config(config)) {
        Ok(result) => result,
        Err(_) => std::process::exit(EXIT_REJECT),
    };
    match out {
        Ok(RunSuccess { message: Some(msg), .. }) => println!("{}", msg),
        Ok(RunSuccess { message: None, .. }) => {}
        Err(error) => {
            let declined = error.downcast_ref::<Decline>().is_some();
            eprintln!("{:?}", MainError(error));
            std::process::exit(if declined { EXIT_DECLINE } else { EXIT_REJECT })
        }
    }
}

fn run_structured(config: &Path, result_path: &Path) -> ! {
    let execution = std::panic::catch_unwind(|| use_config(config));
    let (outcome, exit, message) = match execution {
        Ok(Ok(RunSuccess { message, checked: true })) => (ResultOutcome::Accepted, 0, message),
        Ok(Ok(RunSuccess { checked: false, .. })) =>
            (ResultOutcome::InternalFailure, EXIT_INTERNAL, Some("structured results require a full check".to_string())),
        Ok(Err(error)) if error.downcast_ref::<Decline>().is_some() =>
            (ResultOutcome::Declined, EXIT_DECLINE, Some(error.to_string())),
        Ok(Err(error)) => (ResultOutcome::InternalFailure, EXIT_INTERNAL, Some(error.to_string())),
        Err(payload) => match rejection_from_panic(payload.as_ref()) {
            Some(code) => (ResultOutcome::Rejected(code), EXIT_REJECT, None),
            None => (ResultOutcome::InternalFailure, EXIT_INTERNAL, None),
        },
    };
    if let Err(error) = write_result(result_path, outcome) {
        eprintln!("failed to publish structured result: {error}");
        std::process::exit(EXIT_INTERNAL)
    }
    if let Some(message) = message {
        if exit == 0 {
            println!("{message}")
        } else {
            eprintln!("{message}")
        }
    }
    std::process::exit(exit)
}

struct RunSuccess {
    message: Option<String>,
    checked: bool,
}

fn use_config(config_path: &Path) -> Result<RunSuccess, Box<dyn Error>> {
    let cfg = Config::try_from(config_path)?;
    // Make sure the target pretty printer destination is accessible before doing any real work.
    let mut pp_destination = cfg.get_pp_destination()?;
    let global_arena = Arena::new();
    let (export_file, skipped_axioms) = cfg.to_export_file(global_arena.as_arena_ref())?;
    if export_file.config.parse_only {
        return Ok(RunSuccess {
            message: Some(format!("Parsed {} declarations", export_file.declars.len())),
            checked: false,
        })
    }
    // Check the environment
    export_file.check_all_declars();
    // Pretty print as necessary
    let pp_errs = export_file.pp_selected_declars(pp_destination.as_mut());
    if export_file.config.print_success_message {
        if pp_errs.is_empty() {
            if skipped_axioms.is_empty() {
                Ok(RunSuccess {
                    message: Some(format!("Checked {} declarations with no errors", export_file.declars.len())),
                    checked: true,
                })
            } else {
                Ok(RunSuccess {
                    message: Some(format!(
                        "Checked {} declarations with no errors, skipping exported but unpermitted axioms {:?}",
                        export_file.declars.len(),
                        skipped_axioms
                    )),
                    checked: true,
                })
            }
        } else {
            Ok(RunSuccess {
                message: Some(format!(
                    "Checked {} declarations with no typechecker errors, {} pretty printer errors: {:#?}",
                    export_file.declars.len(),
                    pp_errs.len(),
                    pp_errs
                )),
                checked: true,
            })
        }
    } else if skipped_axioms.is_empty() {
        Ok(RunSuccess { message: None, checked: true })
    } else {
        Ok(RunSuccess {
            message: Some(format!("Skipped exported but unpermitted axioms {:?}", skipped_axioms)),
            checked: true,
        })
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
    "get more help at ",
    env!("CARGO_PKG_REPOSITORY"),
    "\n\n",
    include_str!("../README.md")
);
