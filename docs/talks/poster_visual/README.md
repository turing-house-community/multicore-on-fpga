# Visual poster: "Implementing Conditional Access on FPGA"

A diagram-first alternative to [the main poster](../poster/): the same story and the same measured numbers, with one or two lines of text per section, a 24pt body (the main poster uses 17pt) and 42pt section headings. The compiled poster is [`../poster_visual.pdf`](../poster_visual.pdf) (A1 portrait, one page).

| File | What it is |
|---|---|
| `poster_visual.tex` | the poster (LaTeX `article` class, A1, Times via `newtx`) |
| `logo.png` | IIT Gandhinagar logo |
| `figures/make_figs_visual.py` | draws the new diagrams as SVG: `python3 figures/make_figs_visual.py figures` |
| `figures/*.png` | the figures as used by the poster (SVGs rendered at 3× in Chrome) |
| `figures/uaf_steps.png` | reused from `../poster/figures/` |

## Build
- **Overleaf:** upload `poster_visual.tex`, `logo.png` and the `figures/` folder (or the zip), compile with pdfLaTeX.
- **Locally:** `pdflatex poster_visual.tex` (needs `newtx`, `geometry`, `multicol`, `anyfontsize`, `xcolor`, `graphicx`).
- **SVG → PNG:** `chrome --headless --screenshot=<name>.png --window-size=<w>,<h> --force-device-scale-factor=3 <name>.svg`; the sizes are printed by `make_figs_visual.py`.

## Fitting on one page
The figure widths (`\fig[<width>]{...}`) are tuned so both columns end at the bottom margin. If you change a figure, adjust its width; `\figscale` scales the left column's figures together.
