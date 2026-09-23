# Pre-formal transport clarification

No new native G4 observations have been collected at this clarification.
The prose specification's ordered missing-path list did not fix a serialized
path representation. Canonical comparison output now uses dot-joined strings,
for example `context.protocol_id`, in the already-fixed traversal order. All
registered path components are literal strings without dots. This lossless
presentation normalization belongs to the LCMA transport wrapper, not its frozen
core or scientific contract. The independently authored rich baseline already
uses this representation. Neither arm gains observations or a stronger oracle.

The wrapper recognizes only plain integer cases 79 and 94. All evaluator
exceptions normalize to `{verdict:ERROR,failed:[]}` in both arms. Such transport
errors are not detections. A recursive non-JSON object may cause a core exception;
normalizing that exception is not evidence of native input support or a new
algorithm. No source/history labels are admitted by this clarification.
