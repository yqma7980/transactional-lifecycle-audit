
# P4d.5 independent-branch resumption static freeze

Design version: `P4d.0`  
Protocol revision: `P4d.5`  
Status: `FROZEN_STATIC_NOT_IMPLEMENTED`

P4d.5 preserves the raw P4d.2 line-search contract failure and the final P4d.4 `NOT_SUPPORTED_BY_DIAGNOSTIC_ENVELOPE` adjudication. No additional line-search target or held-out run is allowed.

Three formal prerequisites are inherited without rerun: reference, constitutive oracle and direct safe path, each with two fresh-process passes. Five independent branch cases are frozen for future implementation: driver retry, fresh-process restart, cache negative control, output-provenance negative control and operator-version guard. Each future case requires two fresh-process, single-thread repetitions.

The new dependency DAG is branch local. Retry failure skips only its two dependent negative controls; restart and version branches remain independently auditable. The older P4d.2 prerequisite metadata is retained as historical evidence but is not authoritative for P4d.5.

No case, test, runner, Docker container or FE solve was executed. No results directory was created. P4d.0-P4d.4, manuscript, Claim Matrix, figures, production files, GitHub, Zenodo and DOI were not modified.
