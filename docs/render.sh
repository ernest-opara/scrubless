#!/usr/bin/env bash
# Render the architecture doc to PDF. Run after editing ARCHITECTURE.md.
#   ./docs/render.sh
set -euo pipefail
cd "$(dirname "$0")"
pandoc ARCHITECTURE.md -o ARCHITECTURE.pdf \
  --pdf-engine=xelatex \
  -V monofont="Menlo" \
  -V mainfont="Helvetica Neue"
echo "wrote $(pwd)/ARCHITECTURE.pdf"
