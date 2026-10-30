#!/usr/bin/env bash
# Rebuild everything from scratch: data -> tidy tables -> dashboard HTML.
# Run from the repository root. Requires Python deps (requirements.txt) and Quarto.
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/generate_data.py --out data
python scripts/export_tidy.py --data data --out data/tidy
quarto render dashboard
echo "Rendered to dashboard/_site/index.html"
