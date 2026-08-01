# L6-D1 evidence-sync QA

Date: 2026-07-22  
Status: PASS  
Evidence label: `OBSERVED-EXTERNAL-HOST`

## Formal evidence

- Five frozen cases, ten independent single-process, single-thread formal runs.
- All formal `pass_flag` values are true and all execution values are finite.
- Expected classifications:
  - `L6-EH-RT-01`: `PASS_SAFE_EXTERNAL_HOST_RETRY`.
  - `L6-EH-OP-01`: `PASS_EXTERNAL_HOST_OUTPUT_PROVENANCE`.
  - `L6-EH-CO-01`: `PASS_EXTERNAL_HOST_CALLBACK_ORDER_PARITY`.
  - `L6-EH-RT-02`: `DETECT_EXTERNAL_HOST_FINITE_DRIFT`.
  - `L6-EH-TV-01`: `REJECT_VERSION_MISMATCH_BEFORE_HOST_CORRECTION`.
- Duplicate runs are exact after run-ID normalization.
- Raw file count: 50.
- Raw aggregate SHA-256: `ebc625b31b5371503e4ac028491e838488611091eda59651b18b0138ce1f722f`.
- Per-run output hashes declared by all ten case manifests match disk.

## Derived evidence

- `l6_d1_duplicate_run_comparison.json`: `06c884dbe254f29bd8ea2f1376a96d0ab8ee74afcf391f8e835a4ed4962c0106`.
- `l6_d1_final_summary.json`: `e3e972907a9916eff1b9c8cf1269423092f950738eb1f15c538de3cbf3bb8ddd`.
- `l6_d1_pre_execution_erratum_trace.json`: `107322ec9e199a9c2831dce70cbc68dffaa59cffb9e9acf0791a0c2f75abf573`.
- `l6_d1_result_report.md`: `a335ffa89dfaaf028e88a6f9b68e94254898ab84748fbbd1d2f61378a465e50d`.
- `l6_d1_execution_manifest.json`: `0b5b0d86879ecb3a05917a85d1a2ef8fe65ca995d4ddbc9e0b77dca767278632`.
- Figure/source rows: 10 case rows, 490 host-event rows and 5 case-summary rows.
- `L6_D1_source_manifest.json` row-count metadata was corrected from null to 10/490/5 for the three CSV artifacts; raw inputs and source CSV hashes did not change.
- Corrected source-manifest SHA-256: `9a090d0620a95e65241d4a289af6325ecd7b9858cf9d38d9fa0adfdceab4efdc`.

## Writing and governance

- Versioned intermediate Claim Matrix: `01_claim_evidence_matrix_v2_0_l5_l6_intermediate.md`.
- Intermediate Claim SHA-256: `e7d1cb0b442e691061c0ef3fa25eb723528a6409487b1fbe805099136f0403ff`.
- Claims C39-C42 each occur exactly once.
- Governance synchronized in `STATUS.md`, `03_benchmark_protocol.md`, `04_figure_storyboard.md`, `05_results_registry.md`, `06_reproducibility_and_data.md`, `07_global_roadmap.md` and `08_execution_backlog.md`.
- Manuscript v2.0 was not changed.
- Claim Matrix v2.0 was not changed.

## Protected boundaries

- Claim Matrix v2.0 SHA-256: `d1c24526c55729b720e16efd57782031601919e7ccb19736db3879024d6b011b`.
- Manuscript v2.0 SHA-256: `145deaa450c982992c7c50bf3e98f0b4862054d4e8cd30d2238c48e9bd33923d`.
- Production Git status entries: 53.
- Production status SHA-256: `4def4e7d6c4b5369caa9c0582324f6d2470861f5b07ce57b51e9fd08e18c6e7f`.
- Production tracked/staged changes: zero.
- Abaqus/Standard/pre/utility and COMSOL processes: zero.
- No Git add, commit, push, clean or reset was executed.

## Evidence boundary

This QA authorizes only a bounded `OBSERVED-EXTERNAL-HOST` claim for the five frozen SciPy 1.17.1 TRF lifecycle cases. It does not establish external restart, performance, thread safety, Abaqus, production, two-way coupling, fault-zone or CO2 application validity. The next scientific gate is a separately frozen output-equivalent cost/performance protocol.