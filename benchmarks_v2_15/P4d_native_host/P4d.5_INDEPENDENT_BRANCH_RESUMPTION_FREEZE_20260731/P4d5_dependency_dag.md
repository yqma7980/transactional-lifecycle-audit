
# P4d.5 independent-branch dependency DAG

Protocol revision: `P4d.5`  
Status: `FROZEN_STATIC_NOT_IMPLEMENTED`

## Preserved prior branch

`P4D-SAFE-LS-01` remains `P4D-SAFE-LS-01_CONTRACT_FAIL` in its raw P4d.2 record and is scientifically adjudicated as `NOT_SUPPORTED_BY_DIAGNOSTIC_ENVELOPE` after the complete P4d.4 diagnostic envelope. It is not rerun, replaced or converted to a pass.

## Inherited prerequisite chain

```text
P4D-REF-01 (two-run PASS)
  -> P4D-CONST-01 (two-run PASS)
       -> P4D-SAFE-DIR-01 (two-run PASS)
```

## Resumed independent branches

```text
P4D-SAFE-DIR-01
  -> B-RETRY:   P4D-SAFE-RT-01
                  -> P4D-NC-CACHE-01
                  -> P4D-NC-OUTPUT-01

P4D-SAFE-DIR-01 accepted checkpoint at 0.12
  -> B-RESTART: P4D-SAFE-RS-01

P4D-CONST-01
  -> B-VERSION: P4D-VER-01
```

## Branch-local stop rule

A failed, unsupported or invalid result stops only descendants in the same branch. In particular, failure of `P4D-SAFE-RT-01` skips the two retry-dependent negative controls but does not suppress restart or version-guard evidence. Every outcome is preserved.

## Authority boundary

This DAG was proposed in P4d.3 before the P4d.4 diagnostics. The P4d.5 case matrix is the authority for future branch dependencies. P4d.2 numerical case code may later be used only as a hash-protected implementation dependency; its older prerequisite metadata is not the P4d.5 dependency authority.

No implementation or execution is authorized by this document.
