# Transactional Lifecycle Audit OpenSees Extension v4.0.0

This versioned artifact extends, but does not overwrite, the immutable v3.0.0
parent releases with a separately preregistered OpenSees native-material-
lifecycle study.

## Scientific boundary

- The achieved OpenSees tier is `TIER_A_NATIVE_MATERIAL_API`.
- The caller invokes the unmodified native `Concrete01` trial, commit, and
  revert operations.
- The study is not a solver-managed rejected-step trajectory and does not
  claim Tier-B coverage.
- Controlled integration variants are not defects attributed to upstream
  OpenSees.
- Eight cases and three fresh processes per case were frozen before execution.
- Results are reported separately from the parent 17/20/12/180 evidence and do
  not estimate population reliability, field-defect frequency, or industrial
  reliability.

## Frozen result summary

- Eight semantic case records matched their preregistered outcomes across 24
  fresh processes.
- Four controlled fault cases were ranked Top-1 in the bounded localization
  study.
- `OS-F03` has zero normalized replay drift while the lifecycle violation is
  detected. This is retained as an adverse-to-replay result, not reclassified.

## Parent releases remain immutable

- Data v3.0.0: https://doi.org/10.5281/zenodo.21887646
- Software v3.0.0: https://doi.org/10.5281/zenodo.21887530
- GitHub v3.0.0: https://github.com/yqma7980/transactional-lifecycle-audit/releases/tag/v3.0.0

The version-specific DOI for this extension is assigned in the associated
Zenodo record metadata. The GitHub release target is:
https://github.com/yqma7980/transactional-lifecycle-audit/releases/tag/v4.0.0

## Contents

- `feasibility/`: Tier-A audit, smoke source, output, and manifest.
- `preregistration/`: frozen YAML, SHA record, implementation manifest, and
  study source.
- `results/`: raw process records, case outcomes, localization, validation,
  and report.
- `licenses/`: upstream OpenSees copyright and attribution.
- `environment/`: software, compiler, platform, and evidence-tier record.
- `SHA256_MANIFEST.csv`: relative path, byte size, and SHA-256 for every
  archived file except the manifest itself.

## Reproduction note

The archive preserves the exact study source and recorded executable hash.
Rebuilding requires a compatible C++ toolchain and an OpenSees v3.8.0 source
checkout at commit `6e55293513192aa05c7e1205e66a5a1a1ed088c4`.
The upstream source tree is not redistributed.

## Licensing

Project-authored source and scripts are provided under BSD-3-Clause; see
`LICENSE`. The linked OpenSees implementation and executable remain subject to
the upstream terms reproduced in `licenses/OpenSees_COPYRIGHT.txt`. Numerical
records and documentation are released under CC BY 4.0 unless a bundled file
states otherwise.
