# L1 benchmark specification

Status: frozen design `L1-D1.0`; not implemented or executed

## 1. Research question

At identical declared material or element inputs, can a discarded path-dependent evaluation change a later stress, residual or tangent only because trial history escaped the declared transaction? Can pure-local and explicitly transactional reference implementations reject that seeded defect without false positives?

L1 adds constitutive history and element assembly to L0. It intentionally excludes a global equilibrium solve so that lifecycle causality is not confounded by Newton trajectory differences.

## 2. Reference constitutive model

Use one-dimensional small-strain elastoplasticity with linear isotropic hardening:

```text
E       = 100
sigma_y = 1
H       = 10
```

The accepted physical history is

```text
C_n = (epsilon_p_n, kappa_n, accepted_version_n).
```

For declared trial strain `epsilon`, reconstruct from `C_n`:

```text
sigma_trial = E * (epsilon - epsilon_p_n)
f_trial     = abs(sigma_trial) - (sigma_y + H*kappa_n)
```

If `f_trial <= 0`, return

```text
sigma               = sigma_trial
E_alg               = E
epsilon_p_candidate = epsilon_p_n
kappa_candidate     = kappa_n.
```

If `f_trial > 0`, return

```text
delta_gamma         = f_trial / (E + H)
s                    = sign(sigma_trial)
sigma               = sigma_trial - E*delta_gamma*s
epsilon_p_candidate = epsilon_p_n + delta_gamma*s
kappa_candidate     = kappa_n + delta_gamma
E_alg                = E*H / (E + H).
```

The evaluator returns stress, algorithmic tangent and a disposable candidate. It may not update `C_n`. Only `Accept(candidate_id)` may promote a candidate, exactly once.

## 3. Analytical reference values

All fractions below are part of the frozen design.

### 3.1 Virgin elastic replay

For `C_0=(0,0)` and `epsilon_q=0.005=1/200`:

```text
sigma_q = 1/2 = 0.5
E_alg   = 100
candidate = C_0.
```

### 3.2 Virgin plastic trial

For `epsilon_d=0.03=3/100`:

```text
delta_gamma         = 1/55
epsilon_p_candidate = 1/55
kappa_candidate     = 1/55
sigma               = 13/11
E_alg               = 100/11.
```

### 3.3 Seeded unsafe replay

The required unsafe seed overwrites hidden physical state with the disposable candidate from `epsilon_d`. Replaying `epsilon_q` from the same declared `C_0` then gives:

```text
sigma_unsafe = -289/242
sigma_safe   = 1/2
Delta sigma  = sigma_unsafe - sigma_safe = -205/121
abs(Delta sigma) = 1.6942148760330578.
```

All values are finite. This is the primary L1-MP negative-control oracle.

## 4. One-element operator

Use a two-node axial bar with one integration point:

```text
A = 1
L = 1
u_1 = 0
u = u_2
epsilon = u/L
```

At prescribed `u` and external force `F`, return

```text
R(u;C_n) = A*sigma(u/L;C_n) - F
K(u;C_n) = A*E_alg(u/L;C_n)/L.
```

No equilibrium iteration is run in L1. The element evaluator only assembles the operator at declared packets.

Frozen reference packets:

| Packet | `u` | `F` | Expected `R` | Expected `K` |
|---|---:|---:|---:|---:|
| elastic equilibrium | `0.005` | `0.5` | `0` | `100` |
| monotonic plastic equilibrium | `0.021` | `1.1` | `0` | `100/11` |
| virgin plastic operator | `0.03` | `13/11` | `0` | `100/11` |

The `u=0.021` reference follows from

```text
epsilon = sigma/E + (sigma-sigma_y)/H = 21/1000.
```

## 5. Implementations

### 5.1 Required safe controls

`safe_local`

- evaluation is a pure function of the complete packet and immutable material data;
- candidate history is returned by value;
- no candidate registry or persistent physical mirror exists.

`safe_transactional`

- candidates are stored by `candidate_id` under an explicit attempt;
- reject invalidates the candidate;
- accept promotes exactly one candidate and increments `accepted_version` once;
- terminal/output calls are read-only with respect to physical state.

### 5.2 Required seeded unsafe control

`unsafe_trial_cache`

- every constitutive evaluation writes its candidate `(epsilon_p,kappa)` into an unprotected persistent cache;
- later evaluations read that cache as physical history;
- reject restores only the declared packet and does not restore the cache.

This seed is deliberately incorrect and must fail lifecycle replay while remaining finite.

### 5.3 Secondary seeded unsafe control

`unsafe_output_feedback`

- an output or terminal evaluation overwrites a persistent physical mirror;
- the next constitutive evaluation reads the mirror as history.

This variant is required for terminal/output provenance cases but must remain separate from `unsafe_trial_cache` so the source of detection is unambiguous.

## 6. Replay controls

Every lifecycle comparison must hold constant:

```text
material constants,
declared committed state and accepted version,
trial strain or element displacement,
external force,
event type requested for the replay,
configuration and implementation hash.
```

Only the disposable call history and the deliberately seeded hidden state may differ. If any declared field differs, the case is invalid rather than passed or failed.

## 7. Boundary with L2

L1 evaluates material and element operators at prescribed packets. It does not claim:

- global Newton convergence;
- line-search or cutback behavior;
- accepted displacement-field parity;
- mesh objectivity or spatial stability;
- conservation or coupled-flow accuracy.

Those require L2 or higher.
