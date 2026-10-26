#!/usr/bin/env bash
# Reproduce the committed confirmatory analysis from a clean checkout.
# Default mode reads the committed raw run. Use --rerun to execute 300
# simulations again and --extensions to regenerate exploratory extensions.
set -euo pipefail
export ENERGY_AWARE_NO_BG=1
export PYTHONIOENCODING=utf-8

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

RERUN=0
EXTENSIONS=0
SKIP_TESTS=0
for arg in "$@"; do
  case "$arg" in
    --rerun) RERUN=1 ;;
    --extensions) EXTENSIONS=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() {
  echo
  echo "=== $1 ==="
  shift
  "$@"
}

step "Python and dependency check" python --version
step "Dependency import" python -c "import flask, yaml; print('Flask', flask.__version__, '| PyYAML', yaml.__version__)"
step "Configuration load" python -c "from eaes.config import load_configs; c=load_configs(); print('configs OK:', ', '.join(sorted(c)))"
step "Protected dataset hashes" python analysis/verify_dataset_hashes.py

RUN_DIR="$ROOT/results/runs/v3_paired_20261025T220942Z"
if [ "$RERUN" -eq 1 ]; then
  step "Paired simulation (300 runs; creates a new run id)" python -m experiments.run_v3
  RUN_DIR="$ROOT/$(python -c "import json; print(json.load(open('results/latest_run.json'))['run_dir'])")"
fi
if [ ! -f "$RUN_DIR/manifest.json" ]; then
  echo "Confirmatory run not found: $RUN_DIR" >&2
  exit 1
fi
echo "Using run: $RUN_DIR"

step "Statistical analysis and headline tables" python -m analysis.analyze --run-dir "$RUN_DIR"
step "EAES diagnostic" python -m analysis.diagnose --run-dir "$RUN_DIR"
step "Forecast accuracy and decision relevance" python -m analysis.forecast_accuracy
step "Energy-versus-drop Pareto SVGs" python -m analysis.energy_vs_drop
step "Native-HPA replay" python -m analysis.hpa_replay

if [ "$EXTENSIONS" -eq 1 ]; then
  step "Exploratory extensions" python -m experiments.run_extensions
  step "Energy sensitivity extension" python -m analysis.energy_sensitivity
fi

if [ "$SKIP_TESTS" -eq 0 ]; then
  step "Test suite" python -m pytest -q
fi

step "Document references and required files" python scripts/validate_docs.py

echo
echo "=== Reproduction summary ==="
python - "$RUN_DIR" <<'PY'
import json, sys
run_dir = sys.argv[1]
manifest = json.load(open(f"{run_dir}/manifest.json", encoding="utf-8"))
summary = json.load(open(f"{run_dir}/summary.json", encoding="utf-8"))
print(f"Run:            {manifest['run_id']}")
print(f"Runs:           {len(summary)}")
print(f"Commit:         {manifest['git_commit']}")
print(f"Execution mode: {manifest['execution_mode']}")
print("Energy:         modelled, not measured")
print("Headline:       results/RESULTS.md")
print("Tables:         results/tables/headline.csv, paired_headline.csv")
print("Extensions:     results/extension/")
PY
if command -v git >/dev/null 2>&1; then
  if [ -n "$(git status --porcelain)" ]; then
    echo
    echo "Working-tree changes after reproduction (expected: analysis_manifest timestamp and regenerated report):"
    git status --porcelain
  else
    echo "Working tree clean after reproduction."
  fi
fi
echo "REPRODUCTION COMPLETED"
