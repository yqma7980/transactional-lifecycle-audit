# JSS P5C localization study

This package implements the frozen JSS-P5C.0 common-candidate localization
study. B3 and B6 emit complete rankings over the same eight-candidate ontology.
Ground truth is read only by the evaluator after both rankings have been
constructed.

The formal sequence is development implementation QA, nine development cases
with two fresh-process repetitions, development evidence freeze, held-out
activation, and three held-out cases with two fresh-process repetitions.

This package does not use Abaqus and does not modify the production project.
