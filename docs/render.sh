#!/usr/bin/env bash
# Build the architecture doc, the project report, and the pitch deck (PDF +
# PowerPoint). Run after editing ARCHITECTURE.md, REPORT.md, PITCH.md, or diagrams/.
#   ./docs/render.sh
# Deps: pandoc, xelatex (TeX Live), graphviz (dot), poppler (pdftoppm),
#       and python-pptx in ../.venv (pip install python-pptx).
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

# 2b. Project report (evaluation write-up; figures come from eval/make_figures.py).
pandoc REPORT.md -o REPORT.pdf \
  --pdf-engine=xelatex \
  -V monofont="Menlo" \
  -V mainfont="Helvetica Neue"
echo "wrote $(pwd)/REPORT.pdf"

# 3. Pitch deck (16:9 beamer slides, metropolis theme).
pandoc PITCH.md -t beamer -o PITCH.pdf \
  --pdf-engine=xelatex
echo "wrote $(pwd)/PITCH.pdf"

# 4. Pitch deck as PowerPoint.
#    (a) PITCH.pptx — pixel-perfect, brand-matching: each PITCH.pdf page becomes
#        a full-bleed 16:9 slide image, so it looks identical to the PDF and is
#        immune to font substitution on whoever opens it. This is the one to send.
PPTX_PY="../.venv/bin/python"; [ -x "$PPTX_PY" ] || PPTX_PY="python3"
pgdir="$(mktemp -d)"
pdftoppm -png -r 300 PITCH.pdf "$pgdir/slide"
"$PPTX_PY" pdf2pptx.py "$pgdir" PITCH.pptx
rm -rf "$pgdir"
echo "wrote $(pwd)/PITCH.pptx"
#    (b) PITCH-editable.pptx — unbranded but text-editable, for quick tweaks
#        (beamer-only LaTeX rewritten to plain Markdown; figures = PNGs from 1b).
python3 md2pptx.py PITCH.md | pandoc -f markdown -t pptx -o PITCH-editable.pptx
echo "wrote $(pwd)/PITCH-editable.pptx"
