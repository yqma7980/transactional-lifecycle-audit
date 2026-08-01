# L5-D2 evidence synchronization QA

**Date:** 2026-07-22  
**Status:** PASS  
**Evidence status:** OBSERVED-L5  
**Scope:** Governance and derived-evidence synchronization only; no formal case was rerun during this synchronization.

## Raw-evidence gates

- Formal cases/processes: 8 / 16.
- Raw file count: 80.
- Raw aggregate SHA-256: `137caed1286b92dd2774aab73b7a9047d3116991461e180de322e02fda730478`.
- Per-run manifest/output hash checks: 16/16 PASS.
- Formal `pass_flag`: 16/16 true.
- Duplicate-run normalization gates: 8/8 PASS.
- Source-data rows: case 16; convergence 40; summary 8.
- Minimum five-level regression order: `0.8085946692617711`.
- Maximum normalized step/cumulative phase-mass defects: `6.657001339060997E-17` / `8.881784197001252E-16`.

## Version-protection gates

- Claim Matrix v2.0 remains `d1c24526c55729b720e16efd57782031601919e7ccb19736db3879024d6b011b`.
- Manuscript v2.0 remains `145deaa450c982992c7c50bf3e98f0b4862054d4e8cd30d2238c48e9bd33923d`.
- Intermediate Claim Matrix SHA-256: `5ddc1b1ab0de6079282cd8da90df34cfd6c0c22ce4e7ecd8e9fa2a095d4f4b08`.
- L5-D1 remains a preserved `PRECHECK-FAIL-L5-D1` record.
- L5-D2 discloses prior diagnostic exposure of `N=640/1280`; it is not described as blind out-of-sample evidence.

## Boundary gates

`OBSERVED-L5` is limited to the frozen one-dimensional incompressible, immiscible, zero-capillarity problem and its two declared independent implementations. It does not establish external-host lifecycle behavior, performance, thread safety, Abaqus, two-way poromechanics, fault-zone behavior, production readiness or CO2 application predictions.

## Production and process gates

- Production tracked/staged changes: 0 / 0.
- Production status entries: 53; individual untracked files: 245.
- Production status SHA-256: `4def4e7d6c4b5369caa9c0582324f6d2470861f5b07ce57b51e9fd08e18c6e7f`.
- Abaqus/COMSOL solver processes: 0.
- Existing Python `__pycache__` directories in the NCS workspace: 3. They were not treated as evidence and were not deleted or modified; the later release-candidate stage must exclude bytecode caches.

## Synchronized-file hashes

| File | SHA-256 |
|---|---|
| `STATUS.md` | `9a78d277e3dc447ecc6d2f833773c3a2d6d497f81cce64f23ef77af511f32b08` |
| `03_benchmark_protocol.md` | `3abdb3381cbc020d6563bba842d64349977d63c302723fa4f108e2b8d6fe5343` |
| `04_figure_storyboard.md` | `bba8f2e2d62fad83773ca89a8704e9065ecc1c2aff7b918707eed0c475585b10` |
| `05_results_registry.md` | `89b3bb4c30f6e639cb617ddc1179122b6cee7a54d166fc4e6b94f0e3b3063ee3` |
| `06_reproducibility_and_data.md` | `21a6efcfa5e58a8da096c4f09ebe754e991aaa22e7e81060cef12f1f667b455b` |
| `07_global_roadmap.md` | `78e683d96c5e327b49134f58accc194e414a9003b2f3cdb7c30573246fc7a989` |
| `08_execution_backlog.md` | `cb228e0fbd0b1a8f87f25a2e043509e26d72bf8b49fef742d606e36e92a56fee` |
| `01_claim_evidence_matrix_v2_0_l5_intermediate.md` | `5ddc1b1ab0de6079282cd8da90df34cfd6c0c22ce4e7ecd8e9fa2a095d4f4b08` |
| `figures/L5_D2_case_source.csv` | `88c19893ba65613bbfe004183bc05abdf5be1a0d4eacd311b3ba32422f5dc0f3` |
| `figures/L5_D2_convergence_source.csv` | `1d147e716ac2093c8d1fe4019083ba0e949c359c02b14f14b5f01718ba7b94df` |
| `figures/L5_D2_summary_source.csv` | `8ac75c43eb7c491e900babadbd21109e29a99fa19b8b371c6b8f873de9460400` |
| `figures/L5_D2_source_manifest.json` | `cd78752503afdf545c8e6269ea512802f79e02dca780360ab0a18713c79163a6` |
| `figures/L5_D2_evidence_contract.md` | `aced9764448f7c5ef9de19d6577b9d7779d7d7442a1c726bd16fae9733a2791d` |

## Next gate

Freeze L6 only if an already installed third-party nonlinear host provides genuine trial evaluations and a distinguishable accepted-state callback. A capability probe confirmed that SciPy 1.17.1 `least_squares(method="trf")` performs residual evaluations at nonaccepted trust-region trial states and reports accepted iterates through its callback. This observation authorizes a static L6 design, not a formal L6 claim.