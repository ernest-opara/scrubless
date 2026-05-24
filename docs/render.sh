#!/usr/bin/env bash
# Build the architecture doc and the pitch deck. Run after editing
# ARCHITECTURE.md, PITCH.md, or diagrams/.
#   ./docs/render.sh
set -euo pipefail
cd "$(dirname "$0")"

# 1. Render Graphviz sources to vector PDFs (embedded by pandoc).
for f in diagrams/*.dot; do
  dot -Tpdf "$f" -o "${f%.dot}.pdf"
done

# 2. Architecture doc (article-style PDF).
pandoc ARCHITECTURE.md -o ARCHITECTURE.pdf \
  --pdf-engine=xelatex \
  -V monofont="Menlo" \
  -V mainfont="Helvetica Neue"
echo "wrote $(pwd)/ARCHITECTURE.pdf"

# 3. Pitch deck (16:9 beamer slides, metropolis theme).
pandoc PITCH.md -t beamer -o PITCH.pdf \
  --pdf-engine=xelatex
echo "wrote $(pwd)/PITCH.pdf"
