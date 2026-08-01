from __future__ import annotations

import subprocess

import run_p5_matrix as frozen


def _run_case(
    results_root,
    case_id: str,
    run_id: str,
    thresholds=None,
    selection=None,
) -> None:
    evidence_target = f"/{frozen.WORKING.name}"
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--platform",
        "linux/amd64",
        "-e",
        "OMP_NUM_THREADS=1",
        "-e",
        "OPENBLAS_NUM_THREADS=1",
        "-e",
        "MKL_NUM_THREADS=1",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "P5_EXECUTION_AUTHORIZED=YES",
        "--mount",
        f"type=bind,source={frozen.WORKING.resolve()},target=/working",
        "--mount",
        (
            f"type=bind,source={frozen.WORKING.resolve()},"
            f"target={evidence_target},readonly"
        ),
        "-w",
        frozen._container_path(frozen.ROOT),
        frozen.IMAGE,
        "python3",
        "run_p5_gpfix_v2.py",
        "--case-id",
        case_id,
        "--run-id",
        run_id,
        "--results-root",
        frozen._container_path(results_root),
        "--execute-authorized",
    ]
    if thresholds is not None:
        command.extend(
            ["--thresholds-file", frozen._container_path(thresholds)]
        )
    if selection is not None:
        command.extend(["--selection-file", frozen._container_path(selection)])
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
    )
    log_path = results_root / "process_logs" / case_id / f"{run_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"P5 process failed: {case_id}/{run_id}; see {log_path}"
        )


def main(argv=None) -> int:
    frozen._run_case = _run_case
    return frozen.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
