# P5C localization v2 final report

Status: PASS_P5C_LOCALIZATION_V2

The frozen study executed 12 cases in 24 fresh single-process, single-thread
runs: nine development cases were frozen before activation of three held-out
cases. Both B3 and B6 emitted complete ordered permutations over the same
eight-candidate ontology for every case, and duplicate semantic gates passed.

B3 localized the frozen ground-truth candidate at Top-1 in 6/12 cases and at
Top-3 in 12/12. B6 localized it at Top-1 and Top-3 in 12/12. Mean reciprocal
rank was 0.6944 for B3 and 1.0 for B6; mean EXAM was 0.2292 and 0.125,
respectively. The primary suspicious-set-reduction median was 0.1667 with a
predeclared 10,000-resample 95% bootstrap interval of [0, 0.5]. The exact
sign-flip p-value was 0.03125 and the paired rank-biserial effect was 1.0.

These endpoints describe the 12 frozen cases only. They do not estimate
population localization accuracy, prevalence, sensitivity, or superiority on
unseen software systems.