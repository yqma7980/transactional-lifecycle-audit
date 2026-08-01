# P6R acceptance gates

1. **Protected evidence:** all P3/P5/prior P6-entry hashes remain exact.
2. **Raw bundles:** ten run directories contain exactly seven files; all 70 hashes and case manifests match.
3. **Applicability:** M1/M4/M5/M6 are applicable; M2/M3 remain not applicable with no fallback.
4. **Fair processing:** ten independent single-process, single-thread projection jobs read the bound bundles; no FE code is invoked.
5. **Null control:** every applicable method remains quiet within the P5 null envelope.
6. **F05:** M1/M4 quiet; M5 detects equal-input replay drift; M6 localizes rejected-source reachability.
7. **F07:** M1/M4 quiet; M5 detects callback-history replay drift; M6 localizes persistent restoration failure.
8. **Repetition:** each case/method classification and localization agree across the two raw fresh-process repetitions after removing run/path fields.
9. **Interpretation:** no full-P6, population-detection, checkpoint, M3, Abaqus or production claim.

This static freeze is not an observed result. A future run may end only in a frozen PASS/FAIL or named BLOCKED/NOT_APPLICABLE state.
