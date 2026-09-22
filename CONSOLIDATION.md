# MathGraph Lean Kernel — Consolidated Current State

This branch is a **non-destructive consolidation** of the repository's 470 current branches.

## Rule

Do not merge experiments merely because they exist. The executable base is the newest fully qualified checker implementation, while divergent positive/negative research results are carried as evidence and provenance. No rejected experiment is promoted into runtime code.

## Executable base

- **Flash-2 Infer-Pi + two-thread candidate**
- Commit: `78c7502bac8a5ba000057b3f083bc0595ac65750`
- Qualification run: **35596011019**
- Artifact: **10638422729**
- Artifact digest: `sha256:e2a3937548d4eb4afaa3c4cf5311f8a61901de397a5d61f58bc4fce3f77b3949`
- Full exported semantic parity: **409/409**
- Its causal predecessor reduced Callgrind IR from **799,576,300,513** to **774,967,898,927** (**3.0777%**) and returned `BANK_COMPOUND`.

The consolidation branch starts exactly from that commit. The consolidation commits add only documentation/evidence.

## Developmental-transfer evidence retained

The MSI/Nebula line remains a separate scientific lineage rather than being merged blindly into the checker implementation:

- V41R1: `BOUNDED_POSITIVE` — three-generation sustained ignition.
- V42: `NO_TRANSFER` — preserved negative result; the preregistered source-line witness failed.
- V43: `BOUNDED_POSITIVE` — semantic witness `Rigid/Rigid`, byte-identical Mathlib/Cedar semantics, causal K3-vs-sham separation, held-out nonreversal.

V43 force-all counts:

| corpus | cold | warm12 | warm123 | sham123 |
|---|---:|---:|---:|---:|
| Mathlib | 259,834,108 | 185,536,895 | 45,131,829 | 185,539,308 |
| Cedar | 39,541,239 | 24,536,961 | 4,604,446 | 24,535,265 |

## Not yet promoted

**App-obligation direct-map** is promising but not yet authority. The `dm2048` screen reduced CPU by **2.9248%** and wall time by **1.8350%**, with `PROMOTE_TO_INSTRUCTION_PROXY`. It stays pending until full instruction/semantic qualification.

The universe-cost branch is a census, not an implementation promotion.

## What was consolidated

The 469 branch refs are frozen in `evidence/consolidation/all-branches.tsv`. The machine-readable decision record is `evidence/consolidation/manifest.json`.

Major families are treated as follows:

- **Flash/QCKN** → active performance ancestry; only qualified descendant retained as executable base.
- **MSI/Nebula** → retained scientific evidence and developmental-transfer law.
- **MSI-kernel V0–V27** → retained research/prototype lineage, not runtime authority.
- **R1/R2/R3** → retained optimization/diagnostic provenance; not merged over the newer Flash-2 base.
- **high-V experiment/controller branches** → retained diagnostics; failed leaves are negative evidence.
- **all remaining branches** → indexed, not silently discarded.

This is deliberately a thin consolidation: **one executable spine, many auditable historical/evidence lines**.
