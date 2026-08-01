# L2-D0 execution boundary

**Current authorization:** design documents only.

## Authorized in D0

- define the minimal host problem;
- define case families and negative controls;
- define ledger, checkpoint and decision schemas;
- define analytical, lifecycle, parity and reproducibility gates;
- identify unresolved choices required for D1.

## Not authorized in D0

- create or adapt a UEL or other host callback;
- copy any production source into the NCS workspace;
- compile or link user code;
- run datacheck or host preprocessing;
- start Abaqus Standard or another host solve;
- run restart, thread, cutback or parity experiments;
- modify the production project;
- claim an L2 pass or failure;
- infer conservation, coupled accuracy, performance or application validity.

## Requirements for a later D1 authorization request

The request must state:

1. exact host and version;
2. exact independent source root;
3. model and oracle;
4. case subset to implement first;
5. forced-retry mechanism;
6. frozen tolerances and repetition count;
7. expected runtime and license use;
8. stop conditions;
9. file and commit boundary;
10. explicit prohibition on automatic L3-L6 follow-on work.

## Recommended first D1 slice

If separately approved, implement only:

- L2-REF-01 and L2-REF-02 analytical references;
- L2-RT-01 safe-local forced retry;
- L2-RT-02 safe-transactional forced retry;
- L2-RT-03 unsafe negative control.

Do not implement tangent, output, checkpoint or scheduling families until this
first slice passes static, oracle and forced-retry gates.

## Claim boundary

