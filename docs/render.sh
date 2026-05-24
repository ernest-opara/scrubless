#!/usr/bin/env bash
# Build the architecture doc and the pitch deck. Run after editing
# ARCHITECTURE.md, PITCH.md, or diagrams/.
#   ./docs/render.sh
set -euo pipefail
cd "$(dirname "$0")"

# 1. Render Graphviz sources to vector PDFs (embedded by the PDF builds).
for f in diagrams/*.dot; do
  dot -Tpdf "$f" -o "${f%.dot}.pdf"
done

# 1b. Raster copies of the deck's diagrams for PowerPoint (pptx can't embed PDF).
mkdir -p assets
for d in pitch-flow market competition; do
  dot -Tpng -Gdpi=200 "diagrams/$d.dot" -o "assets/$d.png"
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

# 4. Pitch deck as an editable PowerPoint (beamer-only LaTeX rewritten to
#    plain Markdown; figures pointed at the PNG copies from step 1b).
python3 md2pptx.py PITCH.md | pandoc -f markdown -t pptx -o PITCH.pptx
echo "wrote $(pwd)/PITCH.pptx"
