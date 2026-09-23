// Link-only definitions for parser/output entry points reached by unused object
// paths in the minimal build. Trial, commit, and revert behavior is provided
// exclusively by the unmodified OpenSees Concrete01 implementation.
class OPS_Stream;
OPS_Stream* opserrPtr = nullptr;

extern "C" int OPS_GetNumRemainingInputArgs() { return 0; }
extern "C" int ops_getintinput_(int*, int*) { return -1; }
extern "C" int ops_getdoubleinput_(int*, double*) { return -1; }
