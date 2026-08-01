# L2-D3.0b static and targeted-unit QA

## Verdict

Status:
CORRECTED_IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED

This is implementation-contract QA, not a formal TG-02 benchmark result.

## Root cause and correction

The original TG-02 implementation applied TG-01's exact accepted-fingerprint
gate to a design that freezes tolerance-based accepted-field parity. It also
required cross-path committed-after hashes to match instead of validating each
path's own accepted transition.

The D3.0b layer keeps exact fingerprint equality as information, compares u,
sigma, epsilon_p, kappa and force with abs_tol=rel_tol=1E-12, and reconstructs
the expected committed-after fingerprint independently for each path.

## Static implementation QA

- Original D3 source, runner, tests, freeze and results were not modified.
- D3.0 remains the design version; D3.0b is an implementation revision.
- The corrected module reuses original D3 paths and D1 state serialization.
- No material, residual, tangent, lifecycle, tolerance or Fraction-oracle value
  was changed.
- The new runner accepts only L2-TG-02.
- Both --execute-authorized and L2_D3B_EXECUTION_AUTHORIZED=YES are checked
  before any output directory is created.
- Future outputs are isolated under results/L2_D3b_tangent_path.
- Python AST parsing and JSON parsing passed.

## Targeted tests

The authorized test file ran in one process and one thread with bytecode
generation disabled. Result: 11 tests run, 11 passed.

Coverage included:

- preserved TG-02 run_1 hashes and missing run_2/TG-03 directories;
- all five accepted deltas within the frozen tolerance;
- passing parity with unequal accepted fingerprints;
- failure when any accepted field exceeds tolerance;
- exact 3 / 4 evaluation counts and unequal iteration counts;
- independent left and right committed-transition validity;
- failure for an invalid transition or reachable rejected candidate;
- unchanged TG-01 exact-fingerprint requirement;
- rejection of unauthorized TG-03 through the D3b API; and
- no result directory or bytecode-cache creation.

## Corrective replay

The preserved TG-02 run_1 was loaded read-only and reclassified in memory:

- classification: CORRECTIVE_REPLAY_EXPECTED_PASS
- accepted_field_equal: true
- accepted_fingerprint_equal: false
- left_committed_transition_valid: true
- right_committed_transition_valid: true
- cross_path_committed_fingerprint_equal: false
- evaluation counts: 3 / 4

This replay is an expected corrected verdict only. It is not
OBSERVED-L2-D3 PASS, not FORMAL TG-02 PASS, and not production evidence.

## Preserved failure evidence

The original formal run remains classified as
FAIL_IMPLEMENTATION_CONTRACT and its four files are unchanged. The failed
case_result SHA-256 remains
536dab4abc7a7b710f5f1da0a17e1addbcc0af963b994e0d6982efdfc45749ee.

## Evidence boundary

- TG-01: OBSERVED PASS from its preserved formal repetitions.
- TG-02 D3.0 run_1: INVALIDATED_BY_IMPLEMENTATION_CONTRACT.
- TG-02: OPEN pending two corrected formal repetitions.
- TG-03: OPEN and not run.
- Claim Matrix v0.5, manuscript v0.5 and Figures 1-5 remain unchanged.
- Remaining L2, L3-L6, Abaqus, production, performance, conservation and
  coupled physics remain OPEN.

Implementation manifest SHA-256:
0dee1eaee881a568764bc3b64849e13455beb7a1e9573cfffbfb6170ab873f8f.
