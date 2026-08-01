#include <petscsnes.h>

#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct {
  FILE *stream;
  char schema_version[96];
  char build_hash[96];
  char solve_id[96];
  PetscInt line_search_ordinal;
  PetscInt postcheck_ordinal;
  PetscInt accepted_ordinal;
} P4dObserverContext;

static P4dObserverContext observer_context = {0};

static int SafeToken(const char *value)
{
  const unsigned char *cursor = (const unsigned char *)value;
  if (!value || !*value) return 0;
  while (*cursor) {
    const unsigned char c = *cursor++;
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '.' || c == '_' || c == ':' || c == '-')) return 0;
  }
  return 1;
}

static void SetError(char *buffer, size_t size, const char *message)
{
  if (!buffer || size == 0) return;
  (void)snprintf(buffer, size, "%s", message ? message : "unknown error");
}

static PetscErrorCode WriteVec(FILE *stream, Vec vector)
{
  PetscInt size = 0;
  const PetscScalar *values = NULL;
  PetscFunctionBeginUser;
  if (!vector) {
    (void)fputs("null", stream);
    PetscFunctionReturn(PETSC_SUCCESS);
  }
  PetscCall(VecGetLocalSize(vector, &size));
  PetscCall(VecGetArrayRead(vector, &values));
  (void)fputc('[', stream);
  for (PetscInt i = 0; i < size; ++i) {
    if (i) (void)fputc(',', stream);
    (void)fprintf(stream, "\"%a\"", (double)PetscRealPart(values[i]));
  }
  (void)fputc(']', stream);
  PetscCall(VecRestoreArrayRead(vector, &values));
  PetscFunctionReturn(PETSC_SUCCESS);
}

static PetscErrorCode WriteVecSize(FILE *stream, Vec vector)
{
  PetscInt size = 0;
  PetscFunctionBeginUser;
  if (!vector) {
    (void)fputs("null", stream);
    PetscFunctionReturn(PETSC_SUCCESS);
  }
  PetscCall(VecGetLocalSize(vector, &size));
  (void)fprintf(stream, "%" PetscInt_FMT, size);
  PetscFunctionReturn(PETSC_SUCCESS);
}

static PetscErrorCode WriteCommonPrefix(P4dObserverContext *context, const char *kind,
                                        PetscInt ordinal, PetscInt iteration,
                                        PetscReal lambda, int reason)
{
  PetscFunctionBeginUser;
  (void)fprintf(context->stream,
    "{\"schema_version\":\"%s\",\"observer_build_hash\":\"%s\","
    "\"solve_id\":\"%s\",\"callback_kind\":\"%s\","
    "\"event_ordinal\":%" PetscInt_FMT ",\"nonlinear_iteration\":%" PetscInt_FMT ","
    "\"lambda_hex\":\"%a\",\"line_search_reason\":%d",
    context->schema_version, context->build_hash, context->solve_id, kind,
    ordinal, iteration, (double)lambda, reason);
  PetscFunctionReturn(PETSC_SUCCESS);
}

static PetscErrorCode WriteLineSearchVectors(P4dObserverContext *context,
                                              Vec x, Vec f, Vec y, Vec w, Vec g)
{
  PetscFunctionBeginUser;
  (void)fputs(",\"X_hex_values\":", context->stream); PetscCall(WriteVec(context->stream, x));
  (void)fputs(",\"F_hex_values\":", context->stream); PetscCall(WriteVec(context->stream, f));
  (void)fputs(",\"Y_hex_values\":", context->stream); PetscCall(WriteVec(context->stream, y));
  (void)fputs(",\"W_hex_values\":", context->stream); PetscCall(WriteVec(context->stream, w));
  (void)fputs(",\"G_hex_values\":", context->stream); PetscCall(WriteVec(context->stream, g));
  (void)fputs(",\"vector_sizes\":{\"X\":", context->stream); PetscCall(WriteVecSize(context->stream, x));
  (void)fputs(",\"F\":", context->stream); PetscCall(WriteVecSize(context->stream, f));
  (void)fputs(",\"Y\":", context->stream); PetscCall(WriteVecSize(context->stream, y));
  (void)fputs(",\"W\":", context->stream); PetscCall(WriteVecSize(context->stream, w));
  (void)fputs(",\"G\":", context->stream); PetscCall(WriteVecSize(context->stream, g));
  (void)fputs("}}\n", context->stream);
  (void)fflush(context->stream);
  PetscFunctionReturn(PETSC_SUCCESS);
}

static PetscErrorCode LineSearchMonitor(SNESLineSearch line_search, void *raw_context)
{
  P4dObserverContext *context = (P4dObserverContext *)raw_context;
  SNES snes;
  SNESLineSearchReason reason;
  PetscReal lambda;
  PetscInt iteration;
  Vec x, f, y, w, g;
  PetscFunctionBeginUser;
  PetscCall(SNESLineSearchGetSNES(line_search, &snes));
  PetscCall(SNESGetIterationNumber(snes, &iteration));
  PetscCall(SNESLineSearchGetReason(line_search, &reason));
  PetscCall(SNESLineSearchGetLambda(line_search, &lambda));
  PetscCall(SNESLineSearchGetVecs(line_search, &x, &f, &y, &w, &g));
  context->line_search_ordinal++;
  PetscCall(WriteCommonPrefix(context, "LINE_SEARCH_CANDIDATE", context->line_search_ordinal,
                              iteration, lambda, (int)reason));
  PetscCall(WriteLineSearchVectors(context, x, f, y, w, g));
  PetscFunctionReturn(PETSC_SUCCESS);
}

static PetscErrorCode PostCheck(SNESLineSearch line_search, Vec x, Vec direction, Vec work,
                                PetscBool *changed_direction, PetscBool *changed_work,
                                void *raw_context)
{
  P4dObserverContext *context = (P4dObserverContext *)raw_context;
  SNES snes;
  SNESLineSearchReason reason;
  PetscReal lambda;
  PetscInt iteration;
  Vec ls_x, ls_f, ls_y, ls_w, ls_g;
  PetscFunctionBeginUser;
  (void)x;
  (void)direction;
  (void)work;
  *changed_direction = PETSC_FALSE;
  *changed_work = PETSC_FALSE;
  PetscCall(SNESLineSearchGetSNES(line_search, &snes));
  PetscCall(SNESGetIterationNumber(snes, &iteration));
  PetscCall(SNESLineSearchGetReason(line_search, &reason));
  PetscCall(SNESLineSearchGetLambda(line_search, &lambda));
  PetscCall(SNESLineSearchGetVecs(line_search, &ls_x, &ls_f, &ls_y, &ls_w, &ls_g));
  context->postcheck_ordinal++;
  PetscCall(WriteCommonPrefix(context, "LINE_SEARCH_SELECTED", context->postcheck_ordinal,
                              iteration, lambda, (int)reason));
  PetscCall(WriteLineSearchVectors(context, ls_x, ls_f, ls_y, ls_w, ls_g));
  PetscFunctionReturn(PETSC_SUCCESS);
}

static PetscErrorCode AcceptedMonitor(SNES snes, PetscInt iteration, PetscReal function_norm,
                                      void *raw_context)
{
  P4dObserverContext *context = (P4dObserverContext *)raw_context;
  Vec solution;
  PetscFunctionBeginUser;
  PetscCall(SNESGetSolution(snes, &solution));
  context->accepted_ordinal++;
  PetscCall(WriteCommonPrefix(context, "SNES_ITERATION_STATE", context->accepted_ordinal,
                              iteration, 0.0, 0));
  (void)fprintf(context->stream, ",\"function_norm_hex\":\"%a\",\"X_hex_values\":",
                (double)function_norm);
  PetscCall(WriteVec(context->stream, solution));
  (void)fputs(",\"vector_sizes\":{\"X\":", context->stream);
  PetscCall(WriteVecSize(context->stream, solution));
  (void)fputs("}}\n", context->stream);
  (void)fflush(context->stream);
  PetscFunctionReturn(PETSC_SUCCESS);
}

int P4dObserverAttach(uintptr_t snes_handle, const char *output_path,
                      const char *schema_version, const char *observer_build_hash,
                      const char *solve_id, char *error_buffer, size_t error_buffer_size)
{
  SNES snes = (SNES)snes_handle;
  SNESLineSearch line_search;
  PetscClassId class_id = 0;
  const char *snes_type = NULL;
  PetscErrorCode ierr;

  if (!snes_handle || !output_path || !SafeToken(schema_version) ||
      !SafeToken(observer_build_hash) || !SafeToken(solve_id)) {
    SetError(error_buffer, error_buffer_size, "invalid attachment arguments");
    return -1;
  }
  if (observer_context.stream) {
    SetError(error_buffer, error_buffer_size, "observer already attached in this process");
    return -2;
  }
  ierr = PetscObjectGetClassId((PetscObject)snes, &class_id);
  if (ierr || class_id != SNES_CLASSID) {
    SetError(error_buffer, error_buffer_size, "handle is not a same-process PETSc SNES");
    return ierr ? (int)ierr : -3;
  }
  ierr = SNESGetType(snes, &snes_type);
  if (ierr || !snes_type) {
    SetError(error_buffer, error_buffer_size, "SNES type unavailable");
    return ierr ? (int)ierr : -4;
  }
  ierr = SNESGetLineSearch(snes, &line_search);
  if (ierr || !line_search) {
    SetError(error_buffer, error_buffer_size, "SNES line search unavailable");
    return ierr ? (int)ierr : -5;
  }
  observer_context.stream = fopen(output_path, "wb");
  if (!observer_context.stream) {
    SetError(error_buffer, error_buffer_size, "cannot create observer ledger");
    return -6;
  }
  (void)snprintf(observer_context.schema_version, sizeof(observer_context.schema_version), "%s", schema_version);
  (void)snprintf(observer_context.build_hash, sizeof(observer_context.build_hash), "%s", observer_build_hash);
  (void)snprintf(observer_context.solve_id, sizeof(observer_context.solve_id), "%s", solve_id);
  ierr = SNESLineSearchMonitorSet(line_search, LineSearchMonitor, &observer_context, NULL);
  if (!ierr) ierr = SNESLineSearchSetPostCheck(line_search, PostCheck, &observer_context);
  if (!ierr) ierr = SNESMonitorSet(snes, AcceptedMonitor, &observer_context, NULL);
  if (ierr) {
    (void)fclose(observer_context.stream);
    memset(&observer_context, 0, sizeof(observer_context));
    SetError(error_buffer, error_buffer_size, "PETSc callback registration failed");
    return (int)ierr;
  }
  (void)fprintf(observer_context.stream,
    "{\"schema_version\":\"%s\",\"observer_build_hash\":\"%s\","
    "\"solve_id\":\"%s\",\"callback_kind\":\"ATTACH\","
    "\"snes_type\":\"%s\",\"postcheck_change_flags\":false}\n",
    observer_context.schema_version, observer_context.build_hash,
    observer_context.solve_id, snes_type);
  (void)fflush(observer_context.stream);
  SetError(error_buffer, error_buffer_size, "OK");
  return 0;
}
