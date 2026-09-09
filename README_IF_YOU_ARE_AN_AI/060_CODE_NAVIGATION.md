# Code Navigation Guide for AI Systems

> **Secondary guide (2026-06-13).** Start with `../CLAUDE.md` for the
> authority map, `../ARCHITECTURE.md` for the human repository overview, and
> `../Code/HA-Models/README.md` for the authoritative computational pipeline,
> runtimes, outputs, and exhibit provenance. This file is only a compact
> navigation aid; owner docs win on conflict.

## First Reads

Read these before recommending work:

- `../CLAUDE.md` — AI-facing fact ownership, QE freeze, current methodology defaults, and known speedup caveats.
- `../ARCHITECTURE.md` — high-level directory and entry-point map.
- `../Code/HA-Models/README.md` — canonical five-step pipeline, runtimes, outputs, and paper table/figure provenance.
- `../Code/HA-Models/docs/ENV_FLAGS.md` — authoritative registry for all live `HAFISCAL_*` flags.
- `../Code/HA-Models/docs/FILE_FAMILIES.md` — production vs diagnostic vs archived file-family map.
- `../plans/INDEX.md` — plan status ledger; it wins over stale in-file status lines.

## Current Entry Points

Use `../reproduce.sh` for normal workflows. It wraps document builds,
environment checks, data reproduction, and computational reproduction.

For computational work, `Code/HA-Models/do_all.py` orchestrates the five-step
pipeline. Prefer `HAFISCAL_RUN_STEP_{1,2,3,4,5}` and
`HAFISCAL_RUN_STEP_5B` over editing Python booleans in place.

Step 5 is split:

- Step 5a multipliers: `Code/HA-Models/FromPandemicCode/AggFiscalMAIN_reduced.py --baseline`
- Step 5b welfare-6: `Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py --baseline`

The old monolithic `AggFiscalMAIN.py` entry point was retired in 2026-04. Do
not recommend it for current Step-5 work.

## Directory Map

```text
Code/
├── Empirical/                     # SCF 2004 processing and empirical moments
└── HA-Models/                     # Heterogeneous-agent model pipeline
    ├── do_all.py                  # Five-step orchestrator
    ├── README.md                  # Pipeline owner doc
    ├── docs/                      # Env flags, file families, comment audit
    ├── Target_AggMPCX_LiquWealth/ # Step 1 splurge estimation
    └── FromPandemicCode/          # Steps 2-5 model, simulation, outputs
```

## Pipeline Skeleton

The authoritative version is in `../Code/HA-Models/README.md`; this is only a
mnemonic.

- Step 1: splurge factor estimation in `Target_AggMPCX_LiquWealth/`.
- Step 2: discount-factor distributions in `FromPandemicCode/EstimAggFiscalMAIN.py`.
- Step 3: Splurge=0 robustness, off by default.
- Step 4: HANK-SAM robustness via `HA-Fiscal-HANK-SAM.py` and `HA-Fiscal-HANK-SAM-to-python.py`.
- Step 5a: TM multipliers via `AggFiscalMAIN_reduced.py --baseline`.
- Step 5b: MC welfare-6 via `run_welfare6_parallel.py --baseline`.

## Model Files

Core current files:

- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` — `AggFiscalType` and `AggregateDemandEconomy`.
- `Code/HA-Models/FromPandemicCode/Parameters.py` — calibration assembly and Markov arrays.
- `Code/HA-Models/FromPandemicCode/EstimParameters.py` — estimation parameters and canonical default env block.
- `Code/HA-Models/FromPandemicCode/Simulate.py` — policy simulation orchestration.
- `Code/HA-Models/FromPandemicCode/tm_methods.py` — transition-matrix methods.
- `Code/HA-Models/FromPandemicCode/Welfare.py` — welfare calculations.
- `Code/HA-Models/FromPandemicCode/Output_Results.py` — figure/table output generation.

The current hierarchy uses HARK's Markov-consumer path:
`AggFiscalType` extends `AggIndMrkvConsumerType`, which extends HARK's
`MarkovConsumerType`. Follow the local `mrkv` naming convention for new Python
variable/function/dict names.

## Flags And Guardrails

Never invent undocumented `HAFISCAL_*` flags. Check
`../Code/HA-Models/docs/ENV_FLAGS.md` first and preserve any
`Needs-owner-review` item as an open question unless code evidence settles it.

Do not recommend these without an explicit decision-history pass:

- Production welfare via importance sampling, hybrid TM/MC welfare, or TM
  welfare control variates.
- Plain non-stratified shuffle.
- JAX solver work as an immediate wall-time speedup.
- Default re-estimation as routine cleanup.
- Changing `T_sim`.
- Editing QE-frozen tables/figures directly instead of using the
  candidate/promote workflow.

## Output Ownership

Paper-rendered generated tables/figures are QE-frozen. Generators write
candidate siblings unless explicitly promoted via the documented unlock
workflow. See `../Code/HA-Models/README.md` and `../LOCKED_TABLES.manifest`.

For file-family questions, do not infer from names alone. Use
`../Code/HA-Models/docs/FILE_FAMILIES.md` before moving, archiving, or
recommending deletion of diagnostic files.

## Missing Model-Semantics Layer

The YAML household stage deliberately excludes the orchestrator layer:
splurge accounting, AD fixed point, 21-cohort assembly, demographics, measure
choice, and output aggregation. Use `../HAFiscal-doloplus-orchestrator.md`
alongside `../HAFiscal-doloplus-draft.yaml` and
`../HAFiscal-bellman-for-matsya.md` when making model-level recommendations.

