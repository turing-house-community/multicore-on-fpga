# Directory vs. bus, on the board (no L2)

The `board_dir` column is the directory design and `board_bus` the snooping-bus design, same benchmarks and seeds. Throughput relative to `none` is almost the same; the speed-up of the directory shows in cycles per operation, in the section "Directory vs. bus" below.

Throughput relative to `none` (leaky) for the same data structure and update rate. Above 1.00 is faster than leaking memory. Paper columns: read off Figs. 1-2 (approximately ±15%) at 4 and 32 threads; ours: 2 threads.

## list

| updates | scheme | paper 4T | paper 32T | board_dir 2T | board_bus 2T |
|---|---|---|---|---|---|
| 0% | ca | 0.49 | 1.30 | 0.34 | 0.34 |
| 0% | cafast | - | - | 0.50 | - |
| 0% | hp | 0.25 | 0.51 | 0.25 | 0.25 |
| 0% | qsbr | 0.94 | 0.86 | 1.00 | 1.00 |
| 10% | ca | 0.56 | 1.11 | 0.35 | 0.35 |
| 10% | cafast | - | - | 0.52 | - |
| 10% | hp | 0.29 | 0.55 | 0.27 | 0.27 |
| 10% | qsbr | 1.02 | 1.26 | 1.00 | 1.00 |
| 100% | ca | 0.96 | 2.21 | 0.43 | 0.43 |
| 100% | cafast | - | - | 0.61 | - |
| 100% | hp | 0.44 | 0.53 | 0.33 | 0.33 |
| 100% | qsbr | 0.98 | 0.73 | 0.99 | 1.00 |

## bst

| updates | scheme | paper 4T | paper 32T | board_dir 2T | board_bus 2T |
|---|---|---|---|---|---|
| 0% | ca | 0.55 | 0.60 | 0.56 | 0.64 |
| 0% | cafast | - | - | 0.71 | - |
| 0% | hp | 0.43 | 0.19 | 0.48 | 0.56 |
| 0% | qsbr | 0.62 | 0.91 | 1.00 | 1.00 |
| 10% | ca | - | 0.88 | 0.60 | 0.67 |
| 10% | cafast | - | - | 0.74 | - |
| 10% | hp | 0.40 | 0.24 | 0.51 | 0.57 |
| 10% | qsbr | 0.69 | 0.98 | 0.98 | 0.97 |
| 100% | ca | 1.10 | 1.72 | 0.70 | 0.78 |
| 100% | cafast | - | - | 0.84 | - |
| 100% | hp | 0.62 | 0.41 | 0.57 | 0.65 |
| 100% | qsbr | 0.74 | 0.83 | 0.90 | 0.90 |

## stack

| updates | scheme | paper 4T | paper 32T | board_dir 2T | board_bus 2T |
|---|---|---|---|---|---|
| 0% | ca | 1.04 | 0.90 | 0.37 | 0.37 |
| 0% | cafast | - | - | 0.43 | - |
| 0% | hp | 0.46 | 0.26 | 0.50 | 0.50 |
| 0% | qsbr | 0.70 | 0.79 | 0.92 | 0.92 |
| 10% | ca | - | 0.69 | 0.76 | 0.77 |
| 10% | cafast | - | - | 0.81 | - |
| 10% | hp | - | 0.62 | 0.84 | 0.84 |
| 10% | qsbr | - | 0.77 | 0.95 | 0.94 |
| 100% | ca | 0.72 | 0.74 | 1.36 | 1.33 |
| 100% | cafast | - | - | 1.37 | - |
| 100% | hp | 0.73 | 0.83 | 1.23 | 1.12 |
| 100% | qsbr | 0.72 | 0.90 | 1.08 | 1.07 |

## hash

| updates | scheme | paper 4T | paper 32T | board_dir 2T | board_bus 2T |
|---|---|---|---|---|---|
| 0% | ca | 0.92 | 0.96 | 0.49 | 0.49 |
| 0% | cafast | - | - | 0.60 | - |
| 0% | hp | 0.46 | 0.30 | 0.48 | 0.48 |
| 0% | qsbr | 0.89 | 0.67 | 0.99 | 0.99 |
| 10% | ca | 0.93 | 1.14 | 0.68 | 0.69 |
| 10% | cafast | - | - | 0.75 | - |
| 10% | hp | 0.46 | 0.30 | 0.65 | 0.65 |
| 10% | qsbr | 0.93 | 0.64 | 0.98 | 0.98 |
| 100% | ca | 1.37 | 4.76 | 0.91 | 0.98 |
| 100% | cafast | - | - | 0.95 | - |
| 100% | hp | 0.53 | 0.63 | 0.82 | 0.85 |
| 100% | qsbr | 0.56 | 0.46 | 0.96 | 0.99 |

## Fastest reclaiming scheme per workload (excluding `none`)

| ds | updates | paper 4T | paper 32T | board_dir 2T | board_bus 2T |
|---|---|---|---|---|---|
| list | 0% | qsbr | ca | qsbr | qsbr |
| list | 10% | qsbr | qsbr | qsbr | qsbr |
| list | 100% | qsbr | ca | qsbr | qsbr |
| bst | 0% | qsbr | qsbr | qsbr | qsbr |
| bst | 10% | qsbr | qsbr | qsbr | qsbr |
| bst | 100% | ca | ca | qsbr | qsbr |
| stack | 0% | ca | ca | qsbr | qsbr |
| stack | 10% | - | qsbr | qsbr | qsbr |
| stack | 100% | hp | qsbr | cafast | ca |
| hash | 0% | ca | ca | qsbr | qsbr |
| hash | 10% | qsbr | ca | qsbr | qsbr |
| hash | 100% | ca | ca | qsbr | qsbr |

## Directory vs. bus: cycles per operation

Ratio board_dir / board_bus per configuration; below 1.00 means the directory is faster. It is up to 17% faster when both cores miss on different lines at the same time (BST and hash at 100% updates), and never more than 2% slower.

| ds | scheme | 1T: 0% / 10% / 100% | 2T: 0% / 10% / 100% |
|---|---|---|---|
| list | none | 1.00 / 1.00 / 0.99 | 1.00 / 1.00 / 0.99 |
| list | ca | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| list | hp | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| list | qsbr | 1.00 / 1.00 / 0.99 | 1.00 / 1.00 / 1.00 |
| bst | none | 0.98 / 0.98 / 0.98 | 0.83 / 0.86 / 0.84 |
| bst | ca | 0.99 / 0.99 / 0.99 | 0.95 / 0.96 / 0.94 |
| bst | hp | 0.99 / 0.99 / 0.99 | 0.97 / 0.97 / 0.96 |
| bst | qsbr | 0.98 / 0.98 / 0.98 | 0.83 / 0.85 / 0.84 |
| stack | none | 1.00 / 1.00 / 0.98 | 1.00 / 0.99 / 1.02 |
| stack | ca | 1.00 / 0.99 / 0.98 | 1.00 / 1.01 / 1.00 |
| stack | hp | 1.00 / 1.00 / 0.99 | 1.00 / 0.99 / 0.93 |
| stack | qsbr | 1.00 / 0.99 / 1.00 | 1.00 / 0.99 / 1.01 |
| hash | none | 1.00 / 0.98 / 0.95 | 1.00 / 0.99 / 0.90 |
| hash | ca | 1.00 / 1.00 / 0.99 | 1.00 / 1.00 / 0.97 |
| hash | hp | 1.00 / 1.00 / 0.97 | 1.00 / 1.00 / 0.93 |
| hash | qsbr | 1.00 / 0.99 / 0.97 | 1.00 / 0.99 / 0.92 |

All 96 configurations: median 0.99, range 0.83-1.02.

## Unreclaimed nodes at the end (2 threads, 100% updates)

| ds | board_dir: ca | board_dir: hp | board_dir: qsbr | board_bus: ca | board_bus: hp | board_bus: qsbr |
|---|---|---|---|---|---|---|
| list | 0 | 20 | 117 | 0 | 19 | 115 |
| bst | 0 | 32 | 175 | 0 | 32 | 140 |
| stack | 0 | 34 | 194 | 0 | 34 | 188 |
| hash | 0 | 30 | 103 | 0 | 20 | 125 |

Paper (Fig. 3, lazy list, 16 threads, 100% updates): CA stays at the ~500 live nodes (0 unreclaimed); qsbr and rcu grow without bound late in the run.
