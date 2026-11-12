# Poster source: "Implementing Conditional Access on FPGA"

The compiled poster is [`../poster.pdf`](../poster.pdf) (A1 portrait).

| File | What it is |
|---|---|
| `poster.tex` | the poster (LaTeX `article` class, A1, Times via `newtx`) |
| `figures/make_figs.py` | draws every figure as SVG: `python3 figures/make_figs.py figures` |
| `figures/*.png` | the figures as used by `poster.tex` (SVGs rendered at 3× in a browser) |

The benchmark numbers in the figures and tables are typed in by hand from [`results/`](../../../../results/). If you rerun the benchmarks, update them in `make_figs.py` and `poster.tex`.

## Build
- **Overleaf:** upload `poster.tex` and the `figures/` folder, compile with pdfLaTeX.
- **Locally** (TeX Live or TinyTeX with `newtx`, `geometry`, `multicol`, `booktabs`, `enumitem`, `anyfontsize`, `xcolor`):
  ```bash
  cd docs/talks/poster && pdflatex poster.tex
  ```
- **Logo:** `logo.png` (IIT Gandhinagar) sits next to `poster.tex`; without it a `[LOGO]` box is shown.
- **SVG → PNG:** open the SVG in Chrome/Edge at its own size and render at 3×, e.g.
  `chrome --headless --screenshot=uaf_steps.png --window-size=1400,440 --force-device-scale-factor=3 uaf_steps.svg`.

## Fitting on one page
- If it spills onto page 2, lower `\figscale` at the top of `poster.tex` (e.g. 0.75).
- If space is left at the bottom, raise it (up to 1.0).
