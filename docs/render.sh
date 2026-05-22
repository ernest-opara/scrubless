#!/usr/bin/env bash
# Build the architecture PDF. Run after editing ARCHITECTURE.md or diagrams/.
#   ./docs/render.sh
set -euo pipefail
cd "$(dirname "$0")"

# 1. Render Graphviz sources to vector PDFs (embedded by pandoc).
for f in diagrams/*.dot; do
  dot -Tpdf "$f" -o "${f%.dot}.pdf"
done

# 2. Build the document.
pandoc ARCHITECTURE.md -o ARCHITECTURE.pdf \
  --pdf-engine=xelatex \
  -V monofont="Menlo" \
  -V mainfont="Helvetica Neue"

echo "wrote $(pwd)/ARCHITECTURE.pdf"
