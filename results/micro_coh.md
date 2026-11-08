# Coherence cost on the KR260 (`corev_apu/fpga/kr260/sw/bench/micro_coh.c`)

Date: 2026-11-07. Two CVA6 cores, MSI on the cc_bus, 50 MHz, 16-byte lines, DDR behind the PS.
Hart 0 measures, while hart 1 sets up the remote state. Each test uses 256 fresh lines, and each value is the mean of 3 runs (spread < 0.2%).
The figures include about 6.5 cycles of loop overhead per line (test 6).

| # | access | cycles per line | net of loop |
|---|---|---|---|
| 1 | read miss, no other copy (refill from DDR) | 53.7 | ~47 |
| 2 | read miss, other core holds the line Modified (snoop, write-back, refill) | 96.9 | ~90 |
| 3 | write to a Shared line the other core also holds (invalidating GetM) | 50.4 | ~44 |
| 4 | write to a Shared line no other core holds (GetM) | 49.5 | ~43 |
| 5 | one-way handoff of a line between the cores (ping-pong) | 150.6 per handoff | |
| 6 | read hit (reference) | 6.5 | |

**Reading:**
- Taking a line that the other core holds dirty costs about 43 extra cycles per miss, roughly 1.8× a plain miss, because the dirty data must reach DDR first.
- Invalidating a remote clean copy costs about 1 cycle, because the snoop finds the line clean and answers at once.
- A full handoff between cores is about 150 cycles, or 3 µs at 50 MHz.
