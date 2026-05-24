#!/usr/bin/env python3
"""Transform the beamer pitch deck (PITCH.md) into pptx-friendly Markdown.

PowerPoint can't render the beamer-only bits — \alert, \vspace, \begin{center},
size macros — and pptx embeds raster images, not PDF. This rewrites those into
plain Markdown and points figures at the PNG copies in assets/. Pandoc then
turns the result into an editable .pptx. Usage: md2pptx.py PITCH.md > out.md
"""
import re
import sys
import pathlib

src = pathlib.Path(sys.argv[1]).read_text()

# Drop the beamer YAML; write a minimal pptx front-matter (title slide).
body = re.sub(r"^---\n.*?\n---\n", "", src, count=1, flags=re.S)

yaml = (
    "---\n"
    'title: "Scrubless"\n'
    'subtitle: "Stop scrubbing. Start searching."\n'
    'author: "Chukwuebuka Ernest-Opara — getscrubless.com"\n'
    'date: "May 2026"\n'
    "slide-level: 2\n"
    "---\n"
)

t = body
t = re.sub(r"\\vspace\{[^}]*\}", "", t)                       # spacing macros
t = re.sub(r"\\(footnotesize|small|normalsize|large|Large|bfseries)\b", "", t)
t = t.replace(r"\begin{center}", "").replace(r"\end{center}", "")
t = re.sub(r"\\\\(\[[^\]]*\])?", "\n\n", t)                   # \\ and \\[2pt]
t = re.sub(r"\\textbf\{([^{}]*)\}", r"**\1**", t)
t = re.sub(r"\\emph\{([^{}]*)\}", r"*\1*", t)


def alert(m):
    inner = m.group(1).strip()
    if inner.startswith("**") and inner.endswith("**"):
        return inner
    return "**" + inner + "**"


t = re.sub(r"\\alert\{([^{}]*)\}", alert, t)
t = t.replace(r"\quad·\quad", "  ·  ").replace(r"\quad", "  ")

# Figures: diagrams/*.pdf and assets/*.png -> assets/*.png, drop {width=...}.
t = re.sub(r"!\[\]\((?:diagrams|assets)/([\w-]+)\.(?:pdf|png)\)(\{[^}]*\})?",
           r"![](assets/\1.png)", t)


def fold_caption(m):
    """Fold a caption paragraph that trails a standalone image onto the image.

    PowerPoint otherwise orphans the trailing text onto its own slide; as an
    image caption it stays on the same slide. (Column figures don't match —
    they're followed by a `:::` fence, not a paragraph.)
    """
    path, cap = m.group(1), m.group(2).strip().replace("\n", " ")
    cap = re.sub(r"\*\*([^*]*)\*\*", r"\1", cap)   # drop bold
    cap = re.sub(r"\*([^*]*)\*", r"\1", cap)        # drop italic
    cap = cap.replace("`", "").strip()
    return "![%s](%s)" % (cap, path)


t = re.sub(r"\n{3,}", "\n\n", t)   # collapse blanks first so the fold matches
t = re.sub(r"!\[\]\((assets/[\w-]+\.png)\)\n\n([^\n#:>*\-].*?)(?=\n\n##|\n\n:|\Z)",
           fold_caption, t, flags=re.S)
sys.stdout.write(yaml + "\n" + t)
