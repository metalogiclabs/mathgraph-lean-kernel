# Independent real-input replay

The preserved actual replay passed **40 full-kernel commands and eight zero-selected parser commands** on ten case roles. Each profile has one accepted early-definition input and four rejected fault-injection controls. Two unused-node controls per profile have identical complete bytes despite different delta recipes. These are eight distinct complete input hashes across ten case roles.

`as-run/summary.json` and `as-run/replay.py` preserve the actual executed report and helper byte for byte. The current and independently preserved qualified449 Rust full kernels, and pinned normal/paranoid C++ kernels, each processed all ten complete inputs. Current and449 selected-checker parsers each rejected the four malformed-unused roles with an empty selected list. Fresh complete positive indexes agree among current native, qualified449 native, qualified449 Python, and the pinned ordinary source export, with counts3436 and11653. The original helper does not execute producer_delta, the incremental verifier, or retained index.

`ci-input-parity.json` compares those locally full-replayed bytes to successful clean-source CI run38961520032 at source `ef434eb2477fb64d7fd90fdf23f55bd0b35a0243`. It passed exact reported SHA256/size identity for12 accepted early samples (five warm and one cold per profile), all eight invalid control roles, and30 early-definition snapshots across the retained matrix's three arms. CI reports rejection/no new persisted acceptance for the invalid controls, including parser rejection at zero scheduled declarations for the unused-node controls. The comparator revalidated all48 preserved local raw stdout/stderr hashes.

The compact CI archive identifies live CI inputs by their reported hashes; it omits live memfds, caches, and issuer secrets. This is an input identity comparison under SHA256 collision resistance, not remote-machine attestation or a fresh CI economic measurement. Executable parity is recorded separately per tool, without treating different builds as byte-identical.

## Preserved diagnostics and source attribution

The local current qualification report was initially recorded at dirty1e20, and the current expanded positive came from a one-repetition smoke that was incomplete for economic qualification. Expanded negative inputs came from the earlier f397 qualification. These original metadata remain unchanged. Measured source-file hashes from the current local reports independently match ef434 and the CI source manifest; that does not retroactively make the local runs clean-source CI qualifications.

An initial preflight refused to run because three current native executable hashes differed from the older binaries pinned by the input reports. `as-run/preflight-refusal.json` and `as-run/replay-preflight-v1.py` preserve that refusal. The final replay captures its actual current binaries separately, and still uses independently preserved qualified449 binaries. No old report tool hash was rewritten.

An attempted relocation of the single normal C++ executable exited127 because its relative `libLake_shared.so` was unavailable. `as-run/failed-cpp-relocation/` preserves the real failed attempt, including the two Rust commands that ran before it. This loader failure is not counted as kernel rejection. The final successful C++ commands execute the pinned binaries in their release locations so their shared libraries resolve normally. There is no acceptance claim for synthetic cyclic identity fixtures in this package.

## Package contents and integrity

`as-run-file-map.json` lists every preserved as-run file, its original size/hash, and packaged size/hash. Large index stdout and Python index JSON are gzip-compressed without changing decoded bytes; `gzip -dc FILE.gz` recovers the original raw output. `excluded-regenerable-files.json` gives the sizes and hashes of complete NDJSON inputs and executable binaries deliberately omitted to keep this package compact. No private issuer key is included. `recipes.json`, `deltas/`, and six `application-source/` files identify the source and exact reconstruction recipes. Negative controls are signed-producer fault injections into export rows; they are not claimed to arise from valid Lean proof source.

Check package bytes from this directory:

```sh
sha256sum -c SHA256SUMS
```

## Portable reconstruction and replay

The new portable helpers use paths supplied at invocation. Absolute paths inside as-run files remain historical diagnostic metadata. Python must run normally, without `-O`. First regenerate ordinary and expanded workloads using the pinned repository source and toolchains (Linux x86_64):

```sh
git worktree add --detach /path/qualified ef434eb2477fb64d7fd90fdf23f55bd0b35a0243
cd /path/qualified
bash experiments/incremental/setup.sh
bash experiments/incremental/build_delta_producer.sh /path/scratch/producer
python experiments/incremental/build_workloads.py --out /path/scratch/original
python experiments/incremental/build_delta_workloads.py \
  --workloads /path/scratch/original --out /path/scratch/expanded \
  --producer /path/scratch/producer/delta-producer
```

The builders check their pinned export hashes. From this evidence package directory reconstruct the exact tested inputs independently, without invoking the incremental consumer:

```sh
python reconstruct-inputs.py \
  --original-baseline /path/scratch/original/baseline/export.ndjson \
  --expanded-baseline /path/scratch/expanded/baseline/export.ndjson \
  --out /path/scratch/reconstructed
```

`--hash-only` performs the same byte reconstruction/hashing without writing the large complete inputs. This mode was actually rerun against both baseline files when packaging; all ten roles passed, recorded in `portable-hash-validation/reconstruction.json`.

Prepare a separate checkout of qualified source `4496042c75368f6c35675a9b131c960080afa518` and build its standalone Rust bins with the pinned toolchain for an independent449 oracle. Copy `tools.example.json` to a local file and fill all eight executable paths. Run C++ binaries at their normal release paths with their matching shared libraries. Then:

```sh
python replay-kernels.py --inputs /path/scratch/reconstructed \
  --tools /path/local-tools.json \
  --original-source-export /path/scratch/original/early-definition/export.ndjson \
  --expanded-source-export /path/scratch/expanded/early-definition/export.ndjson \
  --out /path/scratch/fresh-independent-replay
```

Default mode requires exact historically observed executable hashes. Rebuilding may produce different executable bytes; `--allow-new-builds` explicitly records a fresh-build correctness replay with per-tool hash differences instead of claiming historical executable parity. All input and index pins remain enforced. The portable kernel wrapper was syntax/CLI checked during packaging; its48-command body was not rerun during packaging. The original48-command observation remains independently preserved in `as-run/`.

To repeat the compact CI comparison:

```sh
python compare-ci-inputs.py --zip /path/retained-index-summaries.zip \
  --out /path/scratch/ci-input-parity.json
```

The observed ZIP SHA256 is `685bb4892c3ceb71a0b23da6159712d72885bc76fbfd13907310b5c41ea7cb13`. The actual comparison was rerun while packaging. These helpers verify correctness and recorded byte identity; their diagnostic elapsed times are not benchmark observations.
