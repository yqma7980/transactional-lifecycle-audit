# P5 operator-extraction erratum (2026-07-31)

Execution tag `P5_formal_20260731_fullFE_v1b` retained the corrected FE solve
path but stopped while constructing the replay operator packet for the first
scaled F01 process. The preserved process-log SHA-256 is
`d1b9b27378bfe050a5fe03a23163c11d1735fb6594f79f0c428ff0ccc7e0395b`.
No scaled `case_result.json` was produced.

The remaining failure was the metric-extraction analogue of the previously
identified FE activation defect: `build_element_contributions` still rejected
nonidentical integration-point packets instead of integrating them. Revision
`CMAME-P5.2c-FE-GP-INTEGRATION` applies the same frozen equal-weight reduction
to both FE coefficient activation and replay residual/tangent extraction.

Four directed tests pass, including an explicit cross-check of the metric
extraction reduction. An in-memory end-to-end F01 smoke completed both safe and
faulty histories, retained the expected lifecycle violation, kept both histories
conventionally quiet, and produced finite replay metrics.

No frozen scientific setting was changed. The replacement execution tag is
`P5_formal_20260731_fullFE_v1c`; all earlier tags and logs remain immutable.
