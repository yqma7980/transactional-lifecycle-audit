from __future__ import annotations

import hashlib
import importlib
import pathlib
import platform
from typing import Any


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_environment(run_id: str) -> dict[str, Any]:
    import basix
    import dolfinx
    import mpi4py
    import petsc4py
    import ufl
    from petsc4py import PETSc

    packages = {
        "dolfinx": dolfinx.__version__,
        "petsc4py": petsc4py.__version__,
        "PETSc": ".".join(str(value) for value in PETSc.Sys.getVersion()),
        "basix": basix.__version__,
        "ufl": ufl.__version__,
        "mpi4py": mpi4py.__version__,
    }
    modules = {}
    for name in ("dolfinx", "petsc4py", "basix", "ufl", "mpi4py"):
        module = importlib.import_module(name)
        path = pathlib.Path(module.__file__).resolve()
        modules[name] = {"path": str(path), "sha256": _sha256(path)}
    return {
        "schema_version": "CMAME-P4D1-ENVIRONMENT-1.0",
        "preflight_id": "P4D1-ENV-01",
        "run_id": run_id,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
        "module_files": modules,
        "mpi_rank": PETSc.COMM_WORLD.getRank(),
        "mpi_size": PETSc.COMM_WORLD.getSize(),
    }
