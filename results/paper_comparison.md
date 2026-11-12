# Paper vs. simulator vs. KR260

**Two notes on the paper columns.**
- The paper has no 2-thread point. Our best estimate, read off its plotted line between the 1- and 4-thread points (`cva6/corev_apu/fpga/kr260/sw/bench/paper_interp_2t.py`), for CA at 100% updates: list 0.67, BST 0.97, stack 0.57, hash 1.08.
- The 4-thread values below come from `paper_digitize.py`, which reads steep curves too low: list 100% should be about 0.76 (not 0.96) and BST 100% about 0.89 (not 1.10). The other values agree with a careful reading to within a few percent.

Throughput relative to `none` (leaky) for the same data structure and update rate. Above 1.00 is faster than leaking memory. Paper columns: read off Figs. 1-2 (approximately ±15%) at 4 and 32 threads; ours: 2 threads.

## list

| updates | scheme | paper 4T | paper 32T | sim 2T | board 2T |
|---|---|---|---|---|---|
| 0% | ca | 0.49 | 1.30 | 0.34 | 0.34 |
| 0% | cafast | - | - | 0.50 | 0.50 |
| 0% | cabr | - | - | 0.50 | 0.50 |
| 0% | hp | 0.25 | 0.51 | 0.25 | 0.25 |
| 0% | qsbr | 0.94 | 0.86 | 1.00 | 1.00 |
| 10% | ca | 0.56 | 1.11 | 0.35 | 0.35 |
| 10% | cafast | - | - | 0.51 | 0.51 |
| 10% | cabr | - | - | 0.49 | 0.49 |
| 10% | hp | 0.29 | 0.55 | 0.26 | 0.26 |
| 10% | qsbr | 1.02 | 1.26 | 1.00 | 1.00 |
| 100% | ca | 0.96 | 2.21 | 0.41 | 0.41 |
| 100% | cafast | - | - | 0.59 | 0.59 |
| 100% | cabr | - | - | 0.58 | 0.58 |
| 100% | hp | 0.44 | 0.53 | 0.31 | 0.31 |
| 100% | qsbr | 0.98 | 0.73 | 0.99 | 0.99 |

## bst

| updates | scheme | paper 4T | paper 32T | sim 2T | board 2T |
|---|---|---|---|---|---|
| 0% | ca | 0.55 | 0.60 | 0.46 | 0.46 |
| 0% | cafast | - | - | 0.62 | 0.62 |
| 0% | cabr | - | - | 0.59 | 0.59 |
| 0% | hp | 0.43 | 0.19 | 0.38 | 0.38 |
| 0% | qsbr | 0.62 | 0.91 | 1.00 | 1.00 |
| 10% | ca | - | 0.88 | 0.51 | 0.51 |
| 10% | cafast | - | - | 0.66 | 0.66 |
| 10% | cabr | - | - | 0.64 | 0.64 |
| 10% | hp | 0.40 | 0.24 | 0.42 | 0.42 |
| 10% | qsbr | 0.69 | 0.98 | 0.98 | 0.98 |
| 100% | ca | 1.10 | 1.72 | 0.59 | 0.59 |
| 100% | cafast | - | - | 0.76 | 0.76 |
| 100% | cabr | - | - | 0.74 | 0.74 |
| 100% | hp | 0.62 | 0.41 | 0.47 | 0.47 |
| 100% | qsbr | 0.74 | 0.83 | 0.90 | 0.90 |

## stack

| updates | scheme | paper 4T | paper 32T | sim 2T | board 2T |
|---|---|---|---|---|---|
| 0% | ca | 1.04 | 0.90 | 0.37 | 0.37 |
| 0% | cafast | - | - | 0.43 | 0.43 |
| 0% | cabr | - | - | 0.42 | 0.42 |
| 0% | hp | 0.46 | 0.26 | 0.50 | 0.50 |
| 0% | qsbr | 0.70 | 0.79 | 0.92 | 0.92 |
| 10% | ca | - | 0.69 | 0.74 | 0.74 |
| 10% | cafast | - | - | 0.79 | 0.79 |
| 10% | cabr | - | - | 0.79 | 0.79 |
| 10% | hp | - | 0.62 | 0.80 | 0.80 |
| 10% | qsbr | - | 0.77 | 0.93 | 0.93 |
| 100% | ca | 0.72 | 0.74 | 1.19 | 1.20 |
| 100% | cafast | - | - | 1.25 | 1.25 |
| 100% | cabr | - | - | 1.27 | 1.27 |
| 100% | hp | 0.73 | 0.83 | 0.99 | 0.99 |
| 100% | qsbr | 0.72 | 0.90 | 1.02 | 1.03 |

## hash

| updates | scheme | paper 4T | paper 32T | sim 2T | board 2T |
|---|---|---|---|---|---|
| 0% | ca | 0.92 | 0.96 | 0.48 | 0.48 |
| 0% | cafast | - | - | 0.56 | 0.56 |
| 0% | cabr | - | - | 0.64 | 0.64 |
| 0% | hp | 0.46 | 0.30 | 0.47 | 0.47 |
| 0% | qsbr | 0.89 | 0.67 | 0.99 | 0.99 |
| 10% | ca | 0.93 | 1.14 | 0.63 | 0.63 |
| 10% | cafast | - | - | 0.71 | 0.71 |
| 10% | cabr | - | - | 0.79 | 0.79 |
| 10% | hp | 0.46 | 0.30 | 0.60 | 0.60 |
| 10% | qsbr | 0.93 | 0.64 | 0.98 | 0.98 |
| 100% | ca | 1.37 | 4.76 | 0.81 | 0.81 |
| 100% | cafast | - | - | 0.87 | 0.87 |
| 100% | cabr | - | - | 0.99 | 0.99 |
| 100% | hp | 0.53 | 0.63 | 0.69 | 0.69 |
| 100% | qsbr | 0.56 | 0.46 | 0.91 | 0.91 |

## Fastest reclaiming scheme per workload (excluding `none`)

| ds | updates | paper 4T | paper 32T | sim 2T | board 2T |
|---|---|---|---|---|---|
| list | 0% | qsbr | ca | qsbr | qsbr |
| list | 10% | qsbr | qsbr | qsbr | qsbr |
| list | 100% | qsbr | ca | qsbr | qsbr |
| bst | 0% | qsbr | qsbr | qsbr | qsbr |
| bst | 10% | qsbr | qsbr | qsbr | qsbr |
| bst | 100% | ca | ca | qsbr | qsbr |
| stack | 0% | ca | ca | qsbr | qsbr |
| stack | 10% | - | qsbr | qsbr | qsbr |
| stack | 100% | hp | qsbr | cabr | cabr |
| hash | 0% | ca | ca | qsbr | qsbr |
| hash | 10% | qsbr | ca | qsbr | qsbr |
| hash | 100% | ca | ca | cabr | cabr |

## How closely `sim` matches `board` (cycles per operation)

Ratio sim / board per configuration; 1.00 is an exact match.

| ds | scheme | 1T: 0% / 10% / 100% | 2T: 0% / 10% / 100% |
|---|---|---|---|
| list | none | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| list | ca | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| list | cafast | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| list | cabr | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| list | hp | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| list | qsbr | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| bst | none | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| bst | ca | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| bst | cafast | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| bst | cabr | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| bst | hp | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| bst | qsbr | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| stack | none | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| stack | ca | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| stack | cafast | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| stack | cabr | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| stack | hp | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| stack | qsbr | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| hash | none | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| hash | ca | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| hash | cafast | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| hash | cabr | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| hash | hp | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| hash | qsbr | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |

All 144 configurations: median 1.00, range 1.00-1.00.

## Unreclaimed nodes at the end (2 threads, 100% updates)

| ds | sim: ca | sim: hp | sim: qsbr | board: ca | board: hp | board: qsbr |
|---|---|---|---|---|---|---|
| list | 0 | 20 | 116 | 0 | 20 | 118 |
| bst | 0 | 32 | 140 | 0 | 32 | 141 |
| stack | 0 | 34 | 202 | 0 | 34 | 202 |
| hash | 0 | 23 | 103 | 0 | 23 | 102 |

Paper (Fig. 3, lazy list, 16 threads, 100% updates): CA stays at the ~500 live nodes (0 unreclaimed); qsbr and rcu grow without bound late in the run.
