# FEH-D0 preflight QA

The design documents were written before the implementation.  The implementation uses scikit-fem 12.0.2 for the quadrilateral mesh, basis, quadrature fields, residual assembly and tangent assembly.  Six targeted unit tests passed.  All eight frozen cases passed an in-memory preflight, including exact safe replay, finite trial-cache and output-feedback drift, and pre-correction operator-version rejection.

The preflight is not formal evidence.  Formal evidence requires two fresh single-process, single-thread runs per case in immutable run directories.  No acceptance threshold, material constant, mesh, history, mutation strength or hold-out rule was changed in response to a formal result.
