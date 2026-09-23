# OpenSees Native-Lifecycle Study Environment

- Study date: 2026-08-15
- Host OS: Microsoft Windows, x86-64
- OpenSees tag: `v3.8.0`
- OpenSees commit: `6e55293513192aa05c7e1205e66a5a1a1ed088c4`
- Upstream class: `Concrete01`
- Upstream source SHA-256: `C627F6C0BFAF2408FC321B46EBE63C5D3F4D53DE53C6BC4A14757695BE2DBD25`
- Interface tier: `TIER_A_NATIVE_MATERIAL_API`
- Native operations: `setTrialStrain`, `commitState`, `revertToLastCommit`, `revertToStart`
- Registered repeats: three fresh processes per case
- Registered cases: eight
- Numerical drift gate: `1e-12`
- Preregistration SHA-256: `DF47113565DB18DB58DAD662B17B5A8F65BB4E3ADD21A96D719C58092161C21D`
- Smoke executable SHA-256: `B9D268C881AF6EFADF8C239CE8F20F7BBC1895455C592DF725BCC26DA4DEE654`

The exact compiler/build metadata and study executable fingerprint are retained in the feasibility and preregistration manifests. OpenSeesPy was inspected but not used for the registered lifecycle study because it does not expose the required material commit/revert operations independently.
