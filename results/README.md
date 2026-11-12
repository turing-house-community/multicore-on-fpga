# Results

Everything here was measured on the KR260 (or, in `sim/`, on a cycle-exact simulation of the same design). [BENCHMARK_SUMMARY.md](BENCHMARK_SUMMARY.md) explains the numbers; [docs/06_results.md](../docs/06_results.md) is the guided version.

| Folder | Design | What |
|---|---|---|
| `board/` | final: directory, `bcafail`, shared L2 | the paper's benchmarks on the board, 6 schemes, 432 runs |
| `sim/` | final, simulated (Verilator, DDR latency 34 cycles) | the same 432 runs; cycle counts match the board exactly |
| `no_l2/` | directory and `bcafail`, no L2 | the same 432 runs, to see what the L2 changed |
| `bus/` | snooping bus, no L2 | `ca` and `cafast` runs on the bus, compared with the directory in `bus/directory_vs_bus.md` |
| `micro/` | final and no-L2 | cost of each instruction and of coherence |
| `paper_comparison.md` | final | the paper's ratios next to our simulator and board |
| `phase5/` | first design: bus, no L2, CSR check only | the original 288 runs (kept for reference) |

Each run folder has `raw/results.txt` (one line per run, as printed by `kr260_run.sh`), `runs.csv` and `summary.csv` (decoded by `analyze.py`), `tables.md` and `plots/` (SVG, from `plot.py`). To check your own setup, rerun `analyze.py` on our `raw/results.txt` and diff `summary.csv`.

Scheme names: `none` never frees (the speed upper bound), `ca` is conditional access checked with the CSR, `cafast` checks the all-ones return value first, `cabr` checks with `bcafail`, `hp` is hazard pointers, `qsbr` is epoch-based reclamation.
