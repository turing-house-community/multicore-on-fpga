# 5. Benchmarks: reproducing the paper's evaluation on the board

This page reruns our measurements. You need the board set up as in [the FPGA guide](04_fpga_kr260.md). All commands run in `multicore-on-fpga/cva6`. The results we got are in [`results/`](../results/) and explained in [the results page](06_results.md).

All sources are in `corev_apu/fpga/kr260/sw/bench/`:

| File | What it is |
|---|---|
| `bench.c` | the four data structures and four reclamation schemes, chosen at compile time |
| `crt.S` | startup: a stack per hart, calls `main(hartid)` |
| `build_all.sh` | builds all 96 benchmark configurations |
| `run_batch.sh` | runs them all on the board, 3 seeds each, resumable |
| `analyze.py` | decodes the mailbox words into `runs.csv`, `summary.csv`, `tables.md` |
| `plot.py` | draws the charts (SVG + `index.html`, no Python packages needed) |
| `micro.c` | cost of each CA instruction vs. plain loads, stores, atomics (1 hart) |
| `micro_coh.c` | cost of coherence: misses, invalidations, line handoffs (2 harts) |
| `build_micro.sh` | builds the two micro-benchmarks |

## What the benchmark does

We follow the paper's setup (section 6), scaled to 2 cores:

| | Choices |
|---|---|
| Data structures | **lazy list** (1K keys), **external BST** (10K keys), **Treiber stack**, **hash table** (128 buckets of lazy lists) |
| Reclamation schemes | **`none`** (leaky: never frees, the speed upper bound), **`ca`** (conditional access, frees immediately), **`hp`** (hazard pointers), **`qsbr`** (epoch-based) |
| Workload | **0%, 10%, 100% updates** (inserts and deletes 50/50, the rest lookups), random keys, 50% prefill, 3,000 operations per thread |
| Threads | 1 and 2 |
| Repeats | seeds 1, 2, 3 (mean reported) |

4 × 4 × 3 × 2 = **96 configurations × 3 seeds = 288 runs**. After every run the program checks that the data structure is still valid (sorted, no marked nodes, size = prefill + successful inserts − successful deletes) and reports a failure otherwise.

The compile-time switches are `-DDS=1..4` (list, bst, stack, hash), `-DSCHEME=0..3` (none, ca, hp, qsbr), `-DUPD=0|10|100`, `-DNTHREADS=1|2`, `-DNOPS=3000`.

**How CA is used** (paper, Algorithms 1–3): every shared read is a `cread` followed by a failure check (`csrr 0xCC0; andi 1`); traversals `untagOne` lines they leave behind; updates take a `cread`/`cwrite` try-lock on the nodes they change; a removed node is **freed immediately** after it is unlinked.

## 1. Build
```bash
B=corev_apu/fpga/kr260/sw/bench
mkdir -p build/bench
$B/build_all.sh build/bench/elf           # 96 ELFs: bench_<ds>_<scheme>_u<upd>_t<threads>.elf
$B/build_micro.sh build/bench             # micro.elf, micro_coh.elf
```

## 2. Run one configuration
```bash
corev_apu/fpga/kr260/kr260_run.sh build/bench/elf/bench_stack_ca_u100_t2.elf 60 1
```
```
LOADED ... bytes
RESULT PASS after ... ms
MBOX 3395203073 3 1 100 2 3000 ...
```
The `MBOX` words are the results, starting at mailbox word 16:

| Words | Contents |
|---|---|
| 0–12 | magic, data structure, scheme, update %, threads, ops per thread, seed, prefill, final size, expected size, valid flag, unreclaimed nodes at the end, maximum unreclaimed |
| 16–24, 32–40 | for thread 0 and thread 1: cycles, operations, successful inserts, successful deletes, lookups found, CA retries, allocations, frees, removed nodes |

`analyze.py` decodes them; you do not need to read them by hand. A run reports `RESULT FAIL code 41..44` if the data structure was corrupted (41 = list, …, 44 = hash).

## 3. Run everything (about 30 minutes)
```bash
$B/run_batch.sh build/bench          # all of build/bench/elf × seeds 1,2,3
```
It appends one line per run to `build/bench/raw/results.txt` and skips runs that already have a result, so you can stop it (Ctrl-C) and start it again. Runs that got no answer because of a JTAG hiccup are retried. It ends with `done 288 / 288, not pass: 0`.

## 4. Analyze and plot
```bash
python3 $B/analyze.py build/bench/raw/results.txt build/bench   # runs.csv, summary.csv, tables.md
kr260_run=corev_apu/fpga/kr260/kr260_run.sh
$kr260_run build/bench/micro.elf 60     | grep MBOX > build/bench/micro_raw.txt   # plot.py needs this file
python3 $B/plot.py build/bench                                   # build/bench/plots/*.svg, index.html
```
Open `build/bench/plots/index.html` in a browser (from Windows: `explorer.exe build/bench/plots/index.html`). Our PNG versions in `results/plots/` were rendered from the SVGs.

**Check your setup against ours:** `analyze.py` on our raw data reproduces our tables exactly:
```bash
python3 $B/analyze.py ../results/raw/results.txt build/check && diff build/check/summary.csv ../results/summary.csv
```

## 5. The micro-benchmarks
```bash
$kr260_run build/bench/micro.elf 60
$kr260_run build/bench/micro_coh.elf 60
```
Both print `MBOX <magic> 1 <v1> 2 <v2> ...`: pairs of (test number, **cycles × 100**). For example `2 202` in `micro` means test 2 (`cread`) takes 2.02 cycles. The test numbers are listed at the top of each `.c` file; our decoded values are in `results/micro.md` and `results/micro_coh.md`.

- **`micro.c`** (one hart, everything in the L1): each primitive in a loop of 2,000, minus the empty loop.
- **`micro_coh.c`** (two harts): hart 1 prepares the remote cache state, hart 0 measures. Each test uses 256 fresh cache lines so it starts from a known state:
  1. read miss, no other copy
  2. read miss, the other core holds the line Modified
  3. write to a Shared line the other core also holds
  4. write to a Shared line nobody else holds
  5. ping-pong of one line between the cores (per one-way handoff)
  6. read hit (loop overhead reference)

## Ideas for new measurements
- Vary the CA tag-set size (`DEPTH` in `ca_tag_set.sv`) and see when the BST's eviction failures disappear.
- Longer runs (`build_all.sh <out> 30000`) and more seeds for tighter error bars.
- Add `ibr`, `he` or `rcu`, the paper's other baselines (🙋 in [PLAN.md](../PLAN.md)).
