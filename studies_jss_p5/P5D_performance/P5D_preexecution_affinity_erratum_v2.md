# P5D pre-execution affinity implementation erratum

The `qualification_v2` batch preserved the subject-specific environment
binding but stopped before S03 execution because the first Windows affinity
bridge used implicit 32-bit `ctypes` function signatures. The host itself
allowed logical CPUs 0--19; the failure was an ABI declaration error, not an
unavailable CPU or a scientific result.

The bridge now declares 64-bit Windows handle, mask and memory-counter
signatures explicitly. The scientific matrix, workload, modes, equivalence
gates, repetitions and statistical rules remain unchanged. No formal timing
had started. Both earlier qualification attempts remain immutable under
`results/qualification` and `results/qualification_v2`.

The replacement batch is tagged `qualification_v3`. It must report affinity
`[0]` in every process before formal timing can be unlocked.
