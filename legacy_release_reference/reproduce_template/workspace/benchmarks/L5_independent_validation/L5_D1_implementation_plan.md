# L5-D1 implementation plan

Status: FROZEN_NOT_IMPLEMENTED

1. Implement new L5 state, binary serializer, MUSCL/Rusanov SSPRK2 solver, Gauss-Legendre oracle, lifecycle controls and output projection without importing L4 code.
2. Add AST independence checks that reject any L4 implementation import and verify the L4 aggregate only in XP-01.
3. Run syntax, unit, oracle, conservation, safe/unsafe and output-provenance preflight tests. Unit tests are not formal evidence.
4. Use a double-locked runner. Every invocation executes one case and one run ID in one process and one thread.
5. Execute the eight cases in frozen order, two independent processes each. Stop after the first failed prerequisite.
6. Freeze raw outputs, verify manifests, compare normalized repetitions and build a bounded final evidence package.
7. If source sharing beyond the independence contract becomes necessary, record L5 NOT_SUPPORTED and stop.

No Abaqus, COMSOL, production UEL, Git operation or network service is permitted.
