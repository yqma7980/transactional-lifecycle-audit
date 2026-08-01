# L2-D6.0 static and directed-unit QA

Status: `IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED`.

The frozen D1 host is explicitly serial. Its `thread_count` field is event
metadata; no executor, thread pool or parallel material/element backend is
present. The D6 implementation therefore audits the support envelope, runs one
serial analytical health reference and declines to create synthetic
concurrency. Eight directed tests passed. The runner denied an unauthorized
probe before creating a result root and requires both a CLI and environment
lock.

The expected formal outcome is
`NOT_SUPPORTED_NO_PARALLEL_EXECUTION_PATH` under the D0
`PASS_SCHEDULING_ENVELOPE_OR_NOT_SUPPORTED` gate. This is not a thread-safety,
scheduling-invariance, performance, Abaqus or production result. Two independent
formal repetitions are still required.
