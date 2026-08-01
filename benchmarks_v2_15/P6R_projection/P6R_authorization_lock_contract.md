# P6R authorization-lock contract

The formal projection runner is installed but remains unauthorized and unexecuted.

Formal execution requires both independent locks before evidence loading or output-path creation:

1. command-line flag `--execute-authorized`;
2. environment variable `P6R_EXECUTION_AUTHORIZED=YES`.

It also requires `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, and `MKL_NUM_THREADS=1`. The caller must provide one case, one repetition, an execution tag beginning with `P6R_FORMAL_`, and a results root below the implementation package's `results` directory. Existing output directories are never overwritten.

The negative lock smoke test exited with code 1 before evidence loading and left `results` absent. This is a preflight result, not a formal projection result.

