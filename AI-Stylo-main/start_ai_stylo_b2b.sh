#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python3 scripts/bootstrap_and_run.py --mode b2b
