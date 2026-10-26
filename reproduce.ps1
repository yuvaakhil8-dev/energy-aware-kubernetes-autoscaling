# Reproduce the committed confirmatory analysis from a clean checkout.
#
# Default mode reads the committed raw confirmatory run and regenerates the
# derived tables, headline report, diagnostics, forecast-accuracy tables, and
# Pareto SVGs.  Use -Rerun to execute the 300 paired simulations again, and
# -Extensions to regenerate the expensive exploratory extensions.
param(
    [switch]$Rerun,
    [switch]$Extensions,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$env:ENERGY_AWARE_NO_BG = "1"
$env:PYTHONIOENCODING = "utf-8"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Invoke-Step([string]$Label, [scriptblock]$Body) {
    Write-Host ""
    Write-Host "=== $Label ==="
    $global:LASTEXITCODE = 0
    & $Body
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed with exit code ${LASTEXITCODE}: $Label"
    }
}

Invoke-Step "Python and dependency check" {
    python --version
    python -c "import importlib.metadata as m, yaml; print('Flask', m.version('flask'), '| PyYAML', yaml.__version__)"
}

Invoke-Step "Configuration load" {
    python -c "from eaes.config import load_configs; c=load_configs(); print('configs OK:', ', '.join(sorted(c)))"
}

Invoke-Step "Protected dataset hashes" {
    python analysis/verify_dataset_hashes.py
}

$runDir = Join-Path $root "results\runs\v3_paired_20261025T220942Z"
if ($Rerun) {
    Invoke-Step "Paired simulation (300 runs; creates a new run id)" {
        python -m experiments.run_v3
    }
    $pointer = Get-Content (Join-Path $root "results\latest_run.json") -Raw | ConvertFrom-Json
    $runDir = Join-Path $root $pointer.run_dir
}
if (-not (Test-Path (Join-Path $runDir "manifest.json"))) {
    throw "Confirmatory run not found: $runDir"
}
Write-Host "Using run: $runDir"

Invoke-Step "Statistical analysis and headline tables" {
    python -m analysis.analyze --run-dir "$runDir"
}

Invoke-Step "EAES diagnostic" {
    python -m analysis.diagnose --run-dir "$runDir"
}

Invoke-Step "Forecast accuracy and decision relevance" {
    python -m analysis.forecast_accuracy
}

Invoke-Step "Energy-versus-drop Pareto SVGs" {
    python -m analysis.energy_vs_drop
}

Invoke-Step "Native-HPA replay (recorded cluster samples)" {
    python -m analysis.hpa_replay
}

if ($Extensions) {
    Invoke-Step "Exploratory extensions (oracle, startup sweep, seeds 11-30)" {
        python -m experiments.run_extensions
    }
    Invoke-Step "Energy sensitivity extension" {
        python -m analysis.energy_sensitivity
    }
}

if (-not $SkipTests) {
    Invoke-Step "Test suite" {
        python -m pytest -q
    }
}

Invoke-Step "Document references and required files" {
    python scripts/validate_docs.py
}

Write-Host ""
Write-Host "=== Reproduction summary ==="
$manifest = Get-Content (Join-Path $runDir "manifest.json") -Raw | ConvertFrom-Json
$summary = Get-Content (Join-Path $runDir "summary.json") -Raw | ConvertFrom-Json
Write-Host ("Run:            {0}" -f $manifest.run_id)
Write-Host ("Runs:           {0}" -f $summary.Count)
Write-Host ("Commit:         {0}" -f $manifest.git_commit)
Write-Host ("Execution mode: {0}" -f $manifest.execution_mode)
Write-Host ("Energy:         modelled, not measured")
Write-Host ("Headline:       results/RESULTS.md")
Write-Host ("Tables:         results/tables/headline.csv, paired_headline.csv")
Write-Host ("Extensions:     results/extension/")
if (Get-Command git -ErrorAction SilentlyContinue) {
    $diff = git status --porcelain
    if ($diff) {
        Write-Host ""
        Write-Host "Working-tree changes after reproduction (expected: analysis/commit provenance fields and regenerated timestamps):"
        $diff | ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Host "Working tree clean after reproduction."
    }
}
Write-Host "REPRODUCTION COMPLETED"
