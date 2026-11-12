# Poster source: "Implementing Conditional Access on FPGA"

The compiled poster is [`../poster.pdf`](../poster.pdf) (A1 portrait). [`../poster_a0.pdf`](../poster_a0.pdf) is the same poster scaled to A0 (every size 41% larger), for printing at A0. Older versions are in [`../archive/`](../archive/).

| File | What it is |
|---|---|
| `poster.tex` | the poster (LaTeX `article` class, A1, Times via `newtx`) |
| `poster_a0.tex` | wraps the compiled `poster.pdf` onto an A0 page |
| `figures/make_figs.py` | draws `uaf_steps` and `problem_with` |
| `figures/make_figs_v3.py` | draws every other figure |
| `figures/*.png` | the figures as used by `poster.tex` (SVGs rendered at 3× in a browser) |
| `figures/repo_qr.png` | QR code linking to this repository |
| `logo.png` | IIT Gandhinagar logo |

The numbers in the figures are typed in by hand from [`results/`](../../../results/). If you rerun the benchmarks, update them in `make_figs_v3.py` and `poster.tex`.

## Build
- **Locally** (TeX Live or TinyTeX with `newtx`, `geometry`, `multicol`, `booktabs`, `enumitem`, `anyfontsize`, `xcolor`, `alltt`, `hyperref`):
  ```bash
  cd docs/talks/poster
  pdflatex poster.tex        # A1
  pdflatex poster_a0.tex     # A0, needs poster.pdf from the line above
  ```
- **Overleaf:** upload this folder, compile `poster.tex` with pdfLaTeX.
- **SVG → PNG:** open the SVG in Chrome or Edge at its own size and render at 3×, e.g.
  `chrome --headless --screenshot=revoke_seq.png --window-size=1400,500 --force-device-scale-factor=3 revoke_seq.svg`.

## Fitting on one page
The poster is tight. After changing text, check that `pdflatex` still reports 1 page. The usual fixes are a smaller width on one of the `\includegraphics` lines, or shorter captions.
