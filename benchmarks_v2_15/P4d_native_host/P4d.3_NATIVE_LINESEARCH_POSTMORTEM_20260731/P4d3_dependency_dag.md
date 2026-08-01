# P4d.3 branch dependency DAG

## Static dependency proposal

REF -> CONST -> DIR

DIR -> native line-search branch

DIR -> driver-retry branch

DIR checkpoint -> restart branch

driver-retry -> cache/output negative controls

CONST -> version-guard branch

## Decision rule

A NOT_SUPPORTED result in one branch does not automatically block a logically independent branch. Prerequisites within each branch remain mandatory. The complete P4d matrix cannot be labeled PASS while any required branch is NOT_SUPPORTED, failed, or unexecuted.

## Current application

The native line-search branch remains NOT_SUPPORTED_BY_FROZEN_HISTORY. This static DAG does not authorize any downstream execution and does not retroactively change P4d.2 results.
