# Micro-benchmarks (KR260 board)

Cycles per operation, measured with `cva6/corev_apu/fpga/kr260/sw/bench/micro.c` and `micro_coh.c`. The raw `MBOX` lines are in this folder (values are mailbox words / 100).

## Cost of each instruction (`micro.c`, one core, all accesses hit in the L1)

| # | Operation | with L2 | without L2 |
|---|---|---|---|
| 1 | plain load (hit) | 0.97 | 1.00 |
| 2 | `cread` (hit) | 2.00 | 2.02 |
| 3 | `cread` + check with the CSR (`csrr 0xCC0; andi`) | 6.98 | 7.04 |
| 4 | `csrr 0xCC0` alone | 1.00 | 1.02 |
| 5 | `untagOne` | 0.00 | 0.00 |
| 6 | `untagAll` | 3.97 | 3.99 |
| 7 | plain store | 1.00 | 1.01 |
| 8 | `cread` + `cwrite` (try-lock) | 14.97 | 15.03 |
| 9 | `amoswap.w` (atomic in the L1) | 11.99 | 11.99 |
| 10 | `lr.w` + `sc.w` | 21.97 | 22.02 |
| 11 | `fence rw,rw` | 6.00 | 6.02 |
| 12 | `cread` + fast check (compare with all ones) | 5.01 | 5.07 |
| 13 | `cread` + `bcafail` | 3.98 | 4.02 |
| 14 | `cread` + `cwrite` + CSR check | 17.00 | 17.05 |
| 15 | `cread` + `cwrite` + `bcafail` | 17.99 | 18.01 |

Everything here hits in the L1, so the L2 makes no difference. The CA failure check costs about 5 cycles with the CSR, 3 with the fast check and 2 with `bcafail`.

## Cost of coherence (`micro_coh.c`, two cores, 256 fresh lines per test)

Cycles per line, including about 6.5 cycles of loop overhead.

| # | Access | with L2 (directory) | without L2 (bus) |
|---|---|---|---|
| 1 | read miss, no other copy | 32.8 | 53.7 |
| 2 | read miss, the other core holds the line Modified | 32.1 | 96.9 |
| 3 | write to a Shared line the other core also holds | 20.0 | 50.4 |
| 4 | write to a Shared line nobody else holds | 16.2 | 49.5 |
| 5 | one-way handoff of a line between the cores (ping-pong) | 59.0 | 150.6 |
| 6 | read hit (reference) | 6.3 | 6.5 |

Without the L2 every miss and every write-back goes to the PS DDR4. With it, a line the other core has just written back is usually still in the L2, so taking it costs about as much as a plain miss.

The without-L2 coherence numbers are the mean of 3 runs on the first design (snooping bus), from `results/phase5/`.
