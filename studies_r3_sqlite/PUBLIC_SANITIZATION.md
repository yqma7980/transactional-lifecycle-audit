# Public mirror sanitization

The public mirror removes downloaded SQLite executables and archives,
temporary databases, Python bytecode, caches, and pilot outputs. It also
replaces the host-local Python executable path in
`config/source_freeze_manifest.json` with an explicit placeholder.

No source file indexed by the original R3 freeze, frozen configuration,
runtime version, or retained scientific result was changed. The original
private manifest SHA-256 is
`64040F58B7DD8562607A1183EE2EEB55E896B7DCB4DFC511F4A224F59AC2170D`.
The public manifest has a different SHA-256 because of the explicit path
normalization and is indexed by the v6.0.0 release manifest.
