param(
    [switch]$ExecuteAuthorized
)

$ErrorActionPreference = 'Stop'
if (-not $ExecuteAuthorized) {
    throw 'P4d.4 exploratory execution requires -ExecuteAuthorized'
}
if ($env:P4D4_DIAGNOSTIC_MATRIX_AUTHORIZED -ne 'YES') {
    throw 'P4d.4 matrix execution requires P4D4_DIAGNOSTIC_MATRIX_AUTHORIZED=YES'
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$P4dRoot = Split-Path -Parent $Root
$P4d2 = Join-Path $P4dRoot 'P4d.2_FULL_IMPLEMENTATION_20260731'
$ResultsRoot = Join-Path $Root 'results\P4d4_exploratory_20260731'
$LogsRoot = Join-Path $Root 'logs'
$Image = 'dolfinx/dolfinx@sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab'
$Cases = @(
    'P4D4-DIAG-LS-01',
    'P4D4-DIAG-LS-02',
    'P4D4-DIAG-LS-03'
)

if (Test-Path -LiteralPath $ResultsRoot) {
    $existing = Get-ChildItem -LiteralPath $ResultsRoot -Force -ErrorAction SilentlyContinue
    if ($existing) {
        throw "Refusing to reuse nonempty results root: $ResultsRoot"
    }
}
New-Item -ItemType Directory -Force -Path $ResultsRoot,$LogsRoot | Out-Null

$records = @()
foreach ($caseId in $Cases) {
    $logPath = Join-Path $LogsRoot "$caseId.log"
    if (Test-Path -LiteralPath $logPath) {
        throw "Refusing to overwrite log: $logPath"
    }
    $arguments = @(
        'run', '--rm',
        '--network', 'none',
        '--platform', 'linux/amd64',
        '-e', 'PYTHONDONTWRITEBYTECODE=1',
        '-e', 'OMP_NUM_THREADS=1',
        '-e', 'OPENBLAS_NUM_THREADS=1',
        '-e', 'MKL_NUM_THREADS=1',
        '-e', 'P4D4_DIAGNOSTIC_EXECUTION_AUTHORIZED=YES',
        '-v', "$($P4d2):/p4d2:ro",
        '-v', "$($Root):/p4d4",
        '-w', '/p4d4',
        $Image,
        'python3', '/p4d4/run_p4d4_diag.py',
        '--case-id', $caseId,
        '--run-id', 'run_1',
        '--results-root', '/p4d4/results/P4d4_exploratory_20260731',
        '--p4d2-root', '/p4d2',
        '--execute-authorized'
    )
    $output = & docker @arguments 2>&1
    $exitCode = $LASTEXITCODE
    $output | Set-Content -LiteralPath $logPath -Encoding utf8
    $records += [ordered]@{
        case_id = $caseId
        run_id = 'run_1'
        container_exit_code = $exitCode
        log_path = "logs/$caseId.log"
        evidence_status = 'EXPLORATORY_NOT_FORMAL_EVIDENCE'
    }
}

$indexPath = Join-Path $Root 'P4d4_matrix_execution_index.json'
if (Test-Path -LiteralPath $indexPath) {
    throw "Refusing to overwrite execution index: $indexPath"
}
[ordered]@{
    schema_version = 'CMAME-P4D4-MATRIX-EXECUTION-INDEX-1.0'
    image = $Image
    run_all_cases_even_after_trigger = $true
    formal_evidence = $false
    records = $records
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $indexPath -Encoding utf8

if (($records | Where-Object { $_.container_exit_code -ne 0 }).Count -gt 0) {
    exit 2
}
exit 0
