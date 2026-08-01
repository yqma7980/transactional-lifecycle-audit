# L2-D3.0b implementation-contract erratum

## Status

- Design version: L2-D3.0 (unchanged)
- Implementation revision: L2-D3.0b
- Corrected host version: L2-HOST-D3.0b
- Scope: L2-TG-02 classification and committed-transition validation only
- Formal corrected execution: not performed

## Affected evidence

The preserved L2-TG-02/run_1 result is classified as
FAIL_IMPLEMENTATION_CONTRACT. It is not a failed analytical tangent-path
benchmark. The run produced the frozen 3 / 4 exact/lagged evaluation counts
and accepted fields that agree within the frozen absolute and relative
tolerances of 1E-12. Its accepted-state fingerprints differ because the two
floating-point paths end at slightly different, tolerance-equivalent values.

The preserved run must not be rewritten. A read-only in-memory reclassification
under this corrected contract may be reported only as
CORRECTIVE_REPLAY_EXPECTED_PASS.

## Contract defects

The original implementation imposed two gates that are not present in the
frozen TG-02 design:

1. It required exact cross-path accepted-fingerprint equality. That exact gate
   belongs to TG-01 same-track repeatability, not TG-02 tolerance-based accepted
   parity.
2. It treated equality of the two committed-after fingerprints as part of
   committed-transition validity. Each path must instead be validated against
   its own accepted state.

## Corrected TG-02 contract

Accepted-field parity is evaluated separately for u, sigma, epsilon_p, kappa,
and force using math.isclose with rel_tol=1E-12 and abs_tol=1E-12. Exact
accepted-fingerprint equality remains informational and is not a TG-02 gate.

Each path is independently valid only when its committed-before fingerprint is
authoritative, its committed-after fingerprint matches the state reconstructed
from its own accepted epsilon_p and kappa at accepted_version=1, its accepted
candidate was committed, and rejected candidates cannot reach accepted output.

The corrected classification requires accepted-field parity, counts 3 / 4,
unequal iteration counts, both valid transitions, unreachable candidates, and
finite values.

## Unchanged contracts and boundary

TG-01 still requires exact packet and accepted-fingerprint parity. TG-03,
the model, operators, paths, Fraction oracle, lifecycle, tolerances, and frozen
files are unchanged. This erratum is not formal TG-02, Abaqus, production,
performance, conservation, or coupled-physics evidence.
