#!/usr/bin/env python3
"""Validate required documentation and local references.

The check is deliberately strict for the required top-level and docs/ files:
each must exist and must be tracked by git.  For those files, relative Markdown
links and backticked repository paths are resolved and checked.  Legacy
documents outside the required set are not scanned so historical notes do not
block the reproduction pipeline.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import Iterable, List, Tuple

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED = [
    "README.md",
    "METHODOLOGY.md",
    "LIMITATIONS.md",
    "RESULTS.md",
    "docs/EXTENSIONS.md",
    "docs/REVERSAL_EXPLANATION.md",
    "docs/verification_log.txt",
    "docs/ARCHITECTURE.md",
    "docs/EXECUTION_GUIDE.md",
    "docs/TESTING.md",
    "docs/DASHBOARD_GUIDE.md",
    "docs/KUBERNETES_VALIDATION.md",
    "docs/REPRODUCIBILITY.md",
    "docs/LIMITATIONS.md",
    "docs/METHODOLOGY.md",
]

DOCS_TO_SCAN = REQUIRED + [
    "docs/FAILURE_ANALYSIS.md",
    "docs/RESULTS_AND_INTERPRETATION.md",
]

PATH_PREFIXES = (
    "analysis/", "eaes/", "experiments/", "configs/", "kubernetes/",
    "templates/", "static/", "tests/", "scripts/", "traces/", "data/",
    "results/", "docs/",
)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BACKTICK_RE = re.compile(r"`([^`\n]+)`")


def tracked(path: str) -> bool:
    try:
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", path],
            cwd=APP_DIR,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def check_required() -> List[str]:
    errors: List[str] = []
    for rel in REQUIRED:
        full = os.path.join(APP_DIR, rel)
        if not os.path.isfile(full):
            errors.append(f"missing required file: {rel}")
        elif not tracked(rel):
            errors.append(f"required file is not tracked by git: {rel}")
    return errors


def _clean_reference(ref: str) -> str:
    ref = ref.strip()
    if ref.startswith("<") and ref.endswith(">"):
        ref = ref[1:-1]
    ref = ref.split("#", 1)[0]
    ref = ref.split("?", 1)[0]
    return ref


def _is_placeholder(ref: str) -> bool:
    return any(token in ref for token in ("<", ">", "...", "*"))


def check_references(rel_doc: str) -> List[str]:
    errors: List[str] = []
    path = os.path.join(APP_DIR, rel_doc)
    if not os.path.isfile(path):
        return errors
    doc_dir = os.path.dirname(path)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    refs = []
    for match in LINK_RE.finditer(text):
        ref = _clean_reference(match.group(1))
        if ref and not re.match(r"^(https?:|mailto:|#)", ref):
            refs.append((ref, doc_dir))
    for match in BACKTICK_RE.finditer(text):
        ref = _clean_reference(match.group(1))
        if ref.startswith(PATH_PREFIXES) and " " not in ref:
            refs.append((ref, APP_DIR))
    seen = set()
    for ref, base in refs:
        if ref in seen or _is_placeholder(ref):
            continue
        seen.add(ref)
        candidate = ref if os.path.isabs(ref) else os.path.normpath(os.path.join(base, ref))
        if not os.path.exists(candidate):
            errors.append(f"{rel_doc}: referenced path does not exist: {ref}")
            continue
        rel = os.path.relpath(candidate, APP_DIR).replace("\\", "/")
        if rel.startswith(".."):
            continue
        if not tracked(rel) and not os.path.isdir(candidate):
            errors.append(f"{rel_doc}: referenced file is not tracked by git: {ref}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-git", action="store_true", help="only check existence")
    args = parser.parse_args()
    errors = [] if args.skip_git else check_required()
    for doc in DOCS_TO_SCAN:
        if os.path.isfile(os.path.join(APP_DIR, doc)):
            errors.extend(check_references(doc))
    if errors:
        print("DOCUMENT VALIDATION FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"DOCUMENT VALIDATION PASSED: {len(REQUIRED)} required files; {len(DOCS_TO_SCAN)} documents scanned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
