#!/usr/bin/env bash
set -euo pipefail

root=/p4d2
build_dir="$root/preflight_evidence/bridge_build"
source_file="$root/src/p4d_observer_bridge.c"
library_file="$build_dir/libp4d_observer.so"

mkdir -p "$build_dir"
export PKG_CONFIG_PATH="/usr/local/petsc/${PETSC_ARCH}/lib/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"

printf 'PETSC_DIR=%s\n' "$PETSC_DIR"
printf 'PETSC_ARCH=%s\n' "$PETSC_ARCH"
printf 'MPICC=%s\n' "$(command -v mpicc)"
pkg-config --modversion PETSc
mpicc -shared -fPIC \
  $(pkg-config --cflags PETSc) \
  "$source_file" \
  $(pkg-config --libs PETSc) \
  -o "$library_file"
sha256sum "$source_file" "$library_file"
