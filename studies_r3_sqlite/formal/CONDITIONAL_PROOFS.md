# Conditional proof obligations

These statements are mathematical claims about the declared abstraction, not
claims that an adapter observes every dependency of an arbitrary program.

## Definitions

Let `A(s)` be the declared authoritative projection of state `s`, let `Cov(h)`
mean that history `h` exposes every observation required by its case contract,
let `Elig(h1,h2)` mean that the two histories have identical authoritative
entry projections, and let `Viol(h)` be the disjunction of observed O1--O5
violations.  The adjudicator applies the ordered guards:

1. not `Cov` -> `UNSUPPORTED`;
2. `Cov` and not `Elig` -> `INVALID`;
3. `Cov`, `Elig`, and `Viol` -> `DETECTED`;
4. `Cov`, `Elig`, and not `Viol` -> `INVARIANT`.

## Proposition 1: verdict exclusivity and totality

For every well-formed request with Boolean `Cov`, `Elig`, and `Viol`, exactly
one verdict is returned.

**Proof.** The four guards are evaluated in order.  The first true guard
returns.  If the first three are false, then `Cov`, `Elig`, and not `Viol`
hold, so the fourth guard returns.  Each later guard includes the negation of
at least one condition required by an earlier guard, so no two branches can be
selected for the same request.  Therefore the result is total and exclusive.

## Proposition 2: rollback noninterference

Assume that every transition in a non-accepting history preserves `A`, except
for a trial transition whose effects are removed by a restore transition, and
that restore maps the declared projection back to its entry value.  Then every
finite non-accepting history ending in restore has the same authoritative
projection as its entry state.

**Proof.** Induct on the number of trial/restore segments.  The empty history
is immediate.  For the induction step, the prefix has the entry projection by
the hypothesis.  The next trial may change trial state but not accepted state,
and its matching restore returns `A` to the prefix value.  Hence the extended
history has the entry projection.

## Proposition 3: observed-signal soundness

If the adjudicator returns `DETECTED`, then `Cov`, `Elig`, and at least one
declared O1--O5 observation are true.

**Proof.** `DETECTED` is reachable only after the coverage and eligibility
guards have failed to return and the disjunction `Viol` is true.  The claim is
sound with respect to `Viol`; it does not prove that the underlying program
contains a unique source-code defect.

## Proposition 4: conditional completeness for the registered fault class

Let `F_obs` contain only faults that, when activated under a registered case,
guarantee at least one declared O1--O5 signal while coverage and eligibility
hold.  Every activated member of `F_obs` is adjudicated `DETECTED`.

**Proof.** By the definition of `F_obs`, the first two guards do not return and
`Viol` is true.  The third guard therefore returns `DETECTED`.

This is not completeness for hidden dependencies, missing host events,
unregistered faults, concurrency, or arbitrary software.

## Proposition 5: guarded commit/output containment

Assume (i) the guard checks the complete declared projection before an atomic
commit, (ii) uncommitted outputs remain in a private buffer, and (iii) rejected
candidates cannot bypass the guard.  A rejected candidate cannot change the
accepted projection or produce an externally emitted output.

**Proof.** A rejected candidate fails the accepted-candidate predicate, so the
atomic commit transition is disabled.  Its private output buffer is discarded
because emission is enabled only after an accepted commit.  Thus neither an
accepted-state transition nor an external emission is reachable from that
candidate.

The SQLite experiment tests these assumptions for six constructed integration
faults and three benign controls.  It does not establish them for production
deployments or undeclared side channels.

