#include <OPS_Stream.h>

// These symbols belong to parser/output paths that the lifecycle smoke test
// never calls. They are link-only stubs; all trial, commit, and revert behavior
// is provided by the unmodified OpenSees Concrete01 implementation.
OPS_Stream *opserrPtr = nullptr;

extern "C" int OPS_GetNumRemainingInputArgs() { return 0; }
extern "C" int ops_getintinput_(int *, int *) { return -1; }
extern "C" int ops_getdoubleinput_(int *, double *) { return -1; }
