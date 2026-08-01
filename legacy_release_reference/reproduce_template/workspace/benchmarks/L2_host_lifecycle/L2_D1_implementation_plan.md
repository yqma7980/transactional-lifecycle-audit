# L2-D1 minimal host-lifecycle implementation freeze

**Design version:** L2-D1.0  
**Host version:** L2-HOST-D1.0  
**Status:** FROZEN FOR IMPLEMENTATION / NOT EXECUTED  
**Date:** 2026-07-21

## Frozen purpose

The D1 slice tests only whether one standalone global Newton host preserves a
declared committed state across one deliberately injected rejected attempt.
It does not test Abaqus, a production UEL, restart, thread scaling, coupled
flow-mechanics, conservation or performance.

## Host and runtime

The frozen host is a pure-standard-library CPython 3.12.10 implementation on
64-bit Windows NT 10.0.26200.0. The host version is 'L2-HOST-D1.0'.

Execution is single process and single thread. 'PYTHONHASHSEED',
'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS' and
'NUMEXPR_NUM_THREADS' are frozen to '0/1/1/1/1'. The implementation imports no
NumPy, BLAS, Abaqus or production-project source.

## Forced-retry mechanism

The retry is not inferred from nonconvergence. It is injected deterministically:

1. start from the virgin accepted base;
2. begin a parent attempt targeting force '11/10';
3. evaluate exactly one finite plastic trial at displacement '3/100';
4. form and register its candidate;
5. reject the attempt with
   'INJECTED_AFTER_CANDIDATE_FORMATION';
6. verify that committed state is byte-identical and, for the transactional
   control, that the candidate is unreachable;
7. continue through accepted targets '11/20' and '11/10'.

The direct comparison uses the same accepted targets without the discarded
parent attempt. Thus the accepted physical path and accepted-version count are
identical; only rejected call history differs.

A common read-only replay probe at '(u,F)=(1/200,1/2)' is evaluated before the
accepted sequence. Safe variants must reproduce it exactly. The seeded
'unsafe_trial_cache' must show finite nonzero drift of at least '1e-8'.

## Frozen Newton controls

- residual equation: 'R=A*sigma-F';
- tangent: 'K=A*E_alg/L';
- initial guess: last accepted displacement;
- maximum iterations: 12;
- convergence: 'abs(R)<=1e-12';
- tangent floor: '1e-14';
- no line search;
- no automatic retry beyond the one frozen injection.

## Tolerances

Analytical absolute and relative tolerances are '1e-12', inherited from the
already accepted L1 design. Safe retry parity is exact within the same
implementation and serialized physical checkpoint. Unsafe finite drift must
be at least '1e-8'. Any absolute value above '1e100' or any NaN/Inf is a hard
stop.

Tolerances are frozen before any L2 execution and may not be relaxed after
observing a result.

## Repetition and threading

Each formal case requires two independent process executions under the same
environment. Deterministic CSV/JSON artifacts must be byte-identical. Runtime
is reporting-only.

Only one thread is authorized. The scheduling case remains open and is not
part of D1.

## Implemented case subset

- 'L2-REF-01': elastic analytical equilibrium;
- 'L2-REF-02': plastic analytical equilibrium;
- 'L2-RT-01': safe-local direct versus forced retry;
- 'L2-RT-02': safe-transactional direct versus forced retry;
- 'L2-RT-03': deliberately unsafe hidden trial cache.

No other D0 case is implemented or authorized.

## Execution boundary

This document freezes implementation inputs but does not authorize a run.
The runner must refuse to execute unless a future command supplies the explicit
authorization flag. Static source inspection is allowed; producing case
results, accepted checkpoints or a PASS/FAIL classification is not.
