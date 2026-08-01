[CmdletBinding()]
param(
    [switch]$ExecuteAuthorized
)

$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$root = $PSScriptRoot
$resultsRelative = 'results/P4d2_formal_20260731'
$logsRelative = 'formal_execution_logs/P4d2_formal_20260731'
$resultsRoot = Join-Path $root $resultsRelative
$logsRoot = Join-Path $root $logsRelative
$progressPath = Join-Path $logsRoot 'formal_matrix_progress.json'
$image = 'dolfinx/dolfinx@sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab'
$cases = @(
    'P4D-REF-01',
    'P4D-CONST-01',
    'P4D-SAFE-DIR-01',
    'P4D-SAFE-LS-01',
    'P4D-SAFE-RT-01',
    'P4D-SAFE-RS-01',
    'P4D-NC-CACHE-01',
    'P4D-NC-OUTPUT-01',
    'P4D-VER-01'
)
$runs = @('run_1', 'run_2')
$expectedHashes = [ordered]@{
    'P4d2_gate_results.json' = '9de8588e15e7020a8b3ee77fce8bb4728c59d98e3060f8b0fd4d19c252c9845d'
    'P4d2_source_manifest.json' = '6aa3ab71905fe8b5a54239bcd64de6b92a744dfed08c54336fa072c4d5c29541'
    'run_p4d2.py' = 'f6ba558860b5e84c818c7a41cdf191c7dfc7b43d2f26dc49f78326a89fb456b6'
    'build/libp4d_observer.so' = 'a43222350c3fa3f7efecb535d673ab88393b61673b1004bcf3517ef4ef9047e6'
}

function Write-JsonFile {
    param([string]$Path, [object]$Value)
    $json = $Value | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText($Path, $json + "`n", $utf8)
}

function Stop-Matrix {
    param([string]$Message, [object[]]$Records)
    $state = [ordered]@{
        schema_version = 'CMAME-P4D2-FORMAL-PROGRESS-1.0'
        status = 'STOPPED_ON_FAILURE'
        completed_process_count = @($Records).Count
        planned_process_count = 18
        failure = $Message
        records = @($Records)
    }
    Write-JsonFile -Path $progressPath -Value $state
    Write-Host "STOP $Message"
    exit 2
}

if (-not $ExecuteAuthorized) {
    throw 'matrix execution requires -ExecuteAuthorized before any write'
}
if ($env:P4D2_MATRIX_EXECUTION_AUTHORIZED -ne 'YES') {
    throw 'matrix execution requires P4D2_MATRIX_EXECUTION_AUTHORIZED=YES before any write'
}

foreach ($entry in $expectedHashes.GetEnumerator()) {
    $path = Join-Path $root $entry.Key
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "missing protected input: $($entry.Key)"
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
    if ($actual -ne $entry.Value) {
        throw "protected input hash mismatch: $($entry.Key)"
    }
}

$gate = Get-Content -LiteralPath (Join-Path $root 'P4d2_gate_results.json') -Raw | ConvertFrom-Json
if ($gate.all_gates_pass -ne $true -or $gate.final_status -ne 'IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED') {
    throw 'P4d.2 implementation gate is not eligible for formal execution'
}
if (Test-Path -LiteralPath $resultsRoot) {
    throw "refusing to reuse formal results root: $resultsRoot"
}
if (Test-Path -LiteralPath $logsRoot) {
    throw "refusing to reuse formal log root: $logsRoot"
}

docker image inspect $image --format '{{.Id}}' | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'pinned DOLFINx image is unavailable'
}

New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null
$records = @()
$initial = [ordered]@{
    schema_version = 'CMAME-P4D2-FORMAL-PROGRESS-1.0'
    status = 'RUNNING'
    completed_process_count = 0
    planned_process_count = 18
    records = @()
}
Write-JsonFile -Path $progressPath -Value $initial

foreach ($caseId in $cases) {
    foreach ($runId in $runs) {
        $label = "${caseId}_${runId}"
        $logPath = Join-Path $logsRoot ($label + '.log')
        Write-Host "START $caseId $runId"
        $dockerArgs = @(
            'run', '--rm',
            '--network', 'none',
            '--platform', 'linux/amd64',
            '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--env', 'OMP_NUM_THREADS=1',
            '--env', 'OPENBLAS_NUM_THREADS=1',
            '--env', 'MKL_NUM_THREADS=1',
            '--env', 'P4D2_EXECUTION_AUTHORIZED=YES',
            '--mount', "type=bind,source=$root,target=/p4d2",
            '--workdir', '/p4d2',
            $image,
            'python3', 'run_p4d2.py',
            '--case-id', $caseId,
            '--run-id', $runId,
            '--results-root', '/p4d2/results/P4d2_formal_20260731',
            '--dependency-root', '/p4d2/results/P4d2_formal_20260731',
            '--execute-authorized'
        )
        $rawOutput = @(& docker @dockerArgs 2>&1)
        $exitCode = $LASTEXITCODE
        $logText = ($rawOutput | ForEach-Object { $_.ToString() }) -join "`n"
        [System.IO.File]::WriteAllText($logPath, $logText + "`n", $utf8)

        $resultPath = Join-Path $resultsRoot "$caseId\$runId\case_result.json"
        $manifestPath = Join-Path $resultsRoot "$caseId\$runId\case_manifest.json"
        if ($exitCode -ne 0) {
            Stop-Matrix -Message "$caseId $runId exited with code $exitCode" -Records $records
        }
        if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
            Stop-Matrix -Message "$caseId $runId did not produce case_result.json" -Records $records
        }
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
            Stop-Matrix -Message "$caseId $runId did not produce case_manifest.json" -Records $records
        }

        $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
        if ($result.pass_flag -ne $true) {
            Stop-Matrix -Message "$caseId $runId returned pass_flag=false" -Records $records
        }
        if (($result.PSObject.Properties.Name -contains 'primary_verdict') -and
            ($result.PSObject.Properties.Name -contains 'expected_primary_verdict') -and
            ($result.primary_verdict -ne $result.expected_primary_verdict)) {
            Stop-Matrix -Message "$caseId $runId primary verdict mismatch" -Records $records
        }

        $record = [ordered]@{
            case_id = $caseId
            run_id = $runId
            exit_code = $exitCode
            pass_flag = $true
            primary_verdict = if ($result.PSObject.Properties.Name -contains 'primary_verdict') { $result.primary_verdict } else { $null }
            expected_primary_verdict = $result.expected_primary_verdict
            result_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $resultPath).Hash.ToLowerInvariant()
            manifest_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLowerInvariant()
            log_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $logPath).Hash.ToLowerInvariant()
        }
        $records += [pscustomobject]$record
        $progress = [ordered]@{
            schema_version = 'CMAME-P4D2-FORMAL-PROGRESS-1.0'
            status = 'RUNNING'
            completed_process_count = $records.Count
            planned_process_count = 18
            records = $records
        }
        Write-JsonFile -Path $progressPath -Value $progress
        Write-Host "PASS $caseId $runId ($($records.Count)/18)"
    }
}

$complete = [ordered]@{
    schema_version = 'CMAME-P4D2-FORMAL-PROGRESS-1.0'
    status = 'RAW_EXECUTION_COMPLETE_PENDING_DUPLICATE_QA'
    completed_process_count = 18
    planned_process_count = 18
    records = $records
}
Write-JsonFile -Path $progressPath -Value $complete
Write-Host 'COMPLETE 18/18 raw formal processes passed runner gates'
