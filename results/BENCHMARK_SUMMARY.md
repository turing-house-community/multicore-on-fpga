# Benchmark summary

Final design: two CVA6 cores (RV32IMAC) at 50 MHz on the KR260, private 32 KiB L1 data caches with 16 B lines kept coherent by a directory, a shared 256 KiB L2 (64 B lines) in front of the PS DDR4, and conditional access with the `bcafail` branch. Benchmarks follow the paper's section 6, scaled to 2 cores; [docs/05_benchmarks.md](../docs/05_benchmarks.md) explains how to rerun them.

Unless stated otherwise, numbers are 2 threads, mean of seeds 1–3, from `board/`.

## Correctness
- 432 / 432 board runs valid (4 data structures × 6 schemes × 3 update rates × 1–2 threads × 3 seeds). After every run the program checks the structure (sorted, no marked nodes, size = prefill + inserts − deletes).
- The same 432 runs in simulation (`sim/`) give exactly the board's cycle counts: over all 144 configurations, sim / board = 1.00 (median and range).
- Correctness tests on the board: `msi_2core`, `ca_2core`, `bcafail` (2,000 two-core rounds, every outcome checked against the CSR) pass; the negative controls fail as designed; 72/73 ISA tests (`rv32mi-p-breakpoint` is disabled upstream too).

## Memory: nodes removed but not yet freed (end of run, 100% updates)
| | `none` | `ca` (all variants) | `hp` | `qsbr` |
|---|---|---|---|---|
| list | 1,489 | **0** | 20 | 118 |
| BST | 3,028 | **0** | 32 | 141 |
| stack | 2,972 | **0** | 34 | 202 |
| hash | 1,485 | **0** | 23 | 102 |

## Throughput relative to `none`
1.00 means as fast as never freeing memory; higher is better.

| | `ca` | `cafast` | `cabr` | `hp` | `qsbr` |
|---|---|---|---|---|---|
| list 0% | 0.34 | 0.50 | 0.50 | 0.25 | **1.00** |
| list 100% | 0.41 | 0.59 | 0.58 | 0.31 | **0.99** |
| BST 0% | 0.46 | 0.62 | 0.59 | 0.38 | **1.00** |
| BST 100% | 0.59 | 0.76 | 0.74 | 0.47 | **0.90** |
| stack 0% | 0.37 | 0.43 | 0.42 | 0.50 | **0.92** |
| stack 100% | 1.20 | 1.25 | **1.27** | 0.99 | 1.03 |
| hash 0% | 0.48 | 0.56 | 0.64 | 0.47 | **0.99** |
| hash 100% | 0.81 | 0.87 | **0.99** | 0.69 | 0.91 |

The 10% rows are in `board/tables.md`.

- Under contention (stack and hash at 100% updates) CA with `bcafail` is the fastest reclaiming scheme. On the stack it even beats `none`. Part of the reason is that `none` keeps allocating fresh nodes that miss in the cache, while CA reuses freed ones: the gap shrank from 1.37 to 1.27 once the L2 made those misses cheaper.
- On read-heavy work epochs (`qsbr`) are fastest, as in the paper at low thread counts. CA pays for every protected read: `cread` + check costs 4 cycles with `bcafail`, against 1 for a plain load.
- The fast check and `bcafail` are close. `bcafail` wins where failures are common (stack, hash), the fast check on long read-only traversals (list, BST).

## What the shared L2 changed
Same benchmarks on the same design without the L2 (`no_l2/`):

| | `none` speed-up from the L2 | best CA vs `none`: no L2 → L2 | fastest scheme: no L2 → L2 |
|---|---|---|---|
| list 100% | 1.10× | 0.61 → 0.59 | qsbr → qsbr |
| BST 0% | 1.48× | 0.71 → 0.62 | qsbr → qsbr |
| BST 100% | 1.46× | 0.83 → 0.76 | qsbr → qsbr |
| stack 100% | 2.26× | 1.37 → 1.27 | cafast → cabr |
| hash 100% | 1.70× | 1.01 → 0.99 | cabr → cabr |

Latencies: read miss 54 → 33 cycles, read of a line the other core holds Modified 97 → 32, a full handoff between the cores 151 → 59 (`micro/`). Without an L2 every miss went to DDR, which hid part of CA's per-read cost; with it, CA's ratios drop a little, but the winners stay the same.

## Directory vs. bus
Same design without L2, 100% updates, board (`bus/directory_vs_bus.md`): the directory is up to 17% faster than the snooping bus when the two cores miss on different lines at once (BST, hash), and never more than 2% slower.

## Compared with the paper
CA vs `none` at 100% updates. The paper has no 2-thread point; its values are read off the plot between 1 and 4 threads (about ±15%).

| | paper, 2 threads (est.) | our simulator | our board |
|---|---|---|---|
| list | 0.67 | 0.59 | 0.59 |
| BST | 0.97 | 0.76 | 0.76 |
| stack | 0.57 | 1.27 | 1.27 |
| hash | 1.08 | 0.99 | 0.99 |

We are close on the list and hash table. The BST is lower, which fits our more expensive failure check. The stack is the big difference: in the paper CA is slower than never freeing, on our in-order cores it is faster. The paper's large CA wins appear at 16–32 threads, which we cannot test with 2 cores. More columns (4 and 32 threads, all schemes) are in `paper_comparison.md`.

## Hardware cost
From `prebuilt/reports/` (Vivado, post-implementation):

| Block | LUTs | Memory |
|---|---|---|
| CA unit (`ca_tag_set`), per core | about 1,000 (under 1% of the FPGA) | none |
| `bcafail` | +17 for the whole design | none |
| Coherence directory | 676 | 2 UltraRAM |
| Shared L2 | 18,508 | 8 UltraRAM, 8 block RAM (18 Kb) |
| Whole design | 78,120 of 117,120 (67%) | 78 block RAM tiles, 10 UltraRAM |

Timing is met at 50 MHz with 2.86 ns to spare.
