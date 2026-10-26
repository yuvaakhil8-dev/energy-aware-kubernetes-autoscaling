# Reproduce the project in a disposable clone and compare committed tables.
#
# The original working tree is never modified.  The clone is created under the
# system temp directory, reproduce.ps1 is executed there, and every committed
# derived table/report is compared by SHA-256 before and after reproduction.
param(
    [string]$Branch = "research-rebuild",
    [string]$ReportDir = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$source = $repoRoot
Set-Location $source
if (-not $ReportDir) {
    $ReportDir = Join-Path $repoRoot "results\extension\clean_checkout"
}
if (-not (Test-Path (Join-Path $repoRoot ".git"))) {
    throw "Repository root not found at $repoRoot"
}
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

$stamp = Get-Date -Format "yyyyMMddTHHmmssZ"
$clone = Join-Path $env:TEMP "eaes-clean-$stamp"
$logPath = Join-Path $ReportDir "REPRODUCTION_REPORT.txt"
$commit = (git rev-parse HEAD).Trim()

$compareFiles = @(
    "results\RESULTS.md",
    "results\tables\descriptive.csv",
    "results\tables\paired.csv",
    "results\tables\friedman.csv",
    "results\tables\nemenyi.csv",
    "results\tables\forecasting.csv",
    "results\tables\sensitivity.csv",
    "results\tables\headline.csv",
    "results\tables\headline.md",
    "results\tables\paired_headline.csv",
    "results\tables\forecast_accuracy.csv",
    "results\tables\forecast_accuracy.md",
    "results\tables\forecast_accuracy_summary.csv",
    "results\tables\forecast_decision_relevance.csv",
    "results\extension\energy_vs_drop\README.md",
    "results\extension\energy_vs_drop\pareto.csv",
    "results\extension\energy_vs_drop\bursty.svg",
    "results\extension\energy_vs_drop\heavy.svg",
    "results\extension\energy_vs_drop\light.svg",
    "results\extension\energy_vs_drop\medium.svg",
    "results\extension\energy_vs_drop\steady.svg",
    "results\extension\energy_vs_drop\variable.svg",
    "results\extension\hpa_replay\HPA_REPLAY.md",
    "results\extension\hpa_replay\replay.csv",
    "results\extension\hpa_replay\mismatches.csv"
)

$lines = [System.Collections.Generic.List[string]]::new()
function Write-Report([string]$Text = "") {
    $lines.Add($Text) | Out-Null
    Write-Host $Text
}

Write-Report "CLEAN-CHECKOUT REPRODUCTION REPORT"
Write-Report "=================================="
Write-Report ("Started:       {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Report ("Source:        {0}" -f $source)
Write-Report ("Branch:        {0}" -f $Branch)
Write-Report ("Commit:        {0}" -f $commit)
Write-Report ("Clone:         {0}" -f $clone)
Write-Report ""

try {
    Write-Report "Cloning the committed branch..."
    git clone --quiet --branch $Branch $source $clone
    if ($LASTEXITCODE -ne 0) { throw "git clone failed with exit code $LASTEXITCODE" }

    $before = @{}
    foreach ($rel in $compareFiles) {
        $path = Join-Path $clone $rel
        if (Test-Path $path) {
            $before[$rel] = (Get-FileHash -Algorithm SHA256 $path).Hash
        } else {
            $before[$rel] = $null
            Write-Report "WARNING: committed file missing before reproduction: $rel"
        }
    }

    Write-Report ""
    Write-Report "Running reproduce.ps1 -SkipTests in the clone (tests are run separately below)..."
    Push-Location $clone
    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $clone "reproduce.ps1") -SkipTests 2>&1 |
            Tee-Object -FilePath (Join-Path $ReportDir "reproduce_clone_output.txt") |
            ForEach-Object { Write-Host $_ }
        $reproExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    Write-Report ("reproduce.ps1 exit code: {0}" -f $reproExit)
    if ($reproExit -ne 0) { throw "reproduce.ps1 failed with exit code $reproExit" }

    Write-Report ""
    Write-Report "Running the test suite in the clean clone..."
    Push-Location $clone
    try {
        $env:ENERGY_AWARE_NO_BG = "1"
        python -m pytest -q 2>&1 |
            Tee-Object -FilePath (Join-Path $ReportDir "tests_clone_output.txt") |
            ForEach-Object { Write-Host $_ }
        $testExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    Write-Report ("pytest exit code: {0}" -f $testExit)

    Write-Report ""
    Write-Report "Derived-artifact comparison (SHA-256):"
    $mismatches = 0
    $missing = 0
    foreach ($rel in $compareFiles) {
        $path = Join-Path $clone $rel
        if (-not (Test-Path $path)) {
            Write-Report ("  MISSING  {0}" -f $rel)
            $missing += 1
            continue
        }
        $after = (Get-FileHash -Algorithm SHA256 $path).Hash
        if ($before[$rel] -eq $after) {
            Write-Report ("  MATCH    {0}" -f $rel)
        } else {
            Write-Report ("  DIFFER   {0}" -f $rel)
            $mismatches += 1
        }
    }

    Write-Report ""
    Write-Report "git status in the clean clone after reproduction:"
    Push-Location $clone
    try {
        $status = git status --porcelain
    } finally {
        Pop-Location
    }
    if ($status) {
        $status | ForEach-Object { Write-Report ("  {0}" -f $_) }
    } else {
        Write-Report "  (clean)"
    }

    Write-Report ""
    Write-Report ("Summary: {0} files matched, {1} differed, {2} missing, tests exit {3}, reproduce exit {4}." -f (
        $compareFiles.Count - $mismatches - $missing), $mismatches, $missing, $testExit, $reproExit)
    if ($mismatches -gt 0 -or $missing -gt 0 -or $testExit -ne 0 -or $reproExit -ne 0) {
        Write-Report "RESULT: FAIL - reproduction is not byte-identical or a step failed."
        $exitCode = 1
    } else {
        Write-Report "RESULT: PASS - all compared committed artifacts were regenerated byte-identically."
        $exitCode = 0
    }
} catch {
    Write-Report ""
    Write-Report ("ERROR: {0}" -f $_.Exception.Message)
    Write-Report "RESULT: FAIL - reproduction aborted."
    $exitCode = 1
} finally {
    Write-Report ("Finished:      {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    $lines | Set-Content -Path $logPath -Encoding UTF8
    Write-Host ""
    Write-Host "Report: $logPath"
    Write-Host "Clone retained for inspection: $clone"
}

exit $exitCode
