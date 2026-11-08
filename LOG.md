# Project Log: Implementing Conditional Access on FPGA
Newest entries at the top. One or two lines each: what was tried, what worked, what broke, and why decisions were made.
Tag event entries with [LAUNCH], [MIDPOINT], or [COMPLETION].

## 2026-11-08
- Project moved into this repository: CVA6 fork as a submodule, step-by-step docs, prebuilt bitstream, raw results. Testbench file lists, negative controls and run scripts moved from personal folders into the fork.

## 2026-11-07
- Measured the cost of coherence on the board (`micro_coh.c`): plain miss 54 cycles, miss to a remote dirty line 97, invalidating a clean copy ~1, handoff 151. Area from Vivado: CA unit ~1,100 LUTs per core, no block RAM.
- Poster finished ([docs/talks/poster.pdf](docs/talks/poster.pdf)).

## 2026-11-04
- Design documentation written (`cva6/docs/msi_ca_kr260/`).

## 2026-11-02
- Ran the paper's benchmarks on the board: 288/288 runs valid. CA frees immediately (0 unfreed nodes) and is fastest on the contended stack (1.33× the leaky baseline), but slower on read-heavy work because the failure check is a CSR read (7 cycles with `cread`, vs. 2).

## 2026-11-01
- Bitstream on the KR260 at 50 MHz (50% LUTs, 51% BRAM). `msi_2core`, `ca_2core`, controls and 72/73 ISA tests pass, identical to simulation.
- Vivado found two combinational loops that Verilator's `-Wno-UNOPTFLAT` had hidden (between the two cores' AXI ports; trap → CA revoke → cwrite ack → trap). Fixed with an `axi_cut` per core and a registered trap. Lesson: lint with `-Wwarn-UNOPTFLAT` first.
- Board results go through an uncached mailbox, since a write-back cache can hold `tohost` forever.

## 2026-10-30
- CA on the coherent write-back cache: `ca_tag_set.sv`, `cwrite` at commit as an atomic, CSR 0xCC0. Testbench with a model of the paper's rules: 400/400 runs, 11/11 injected CA bugs caught. `ca_2core` passes; with plain loads/stores it fails, as it should.
- Two cores on `cc_bus`: the testbench found a stale-S-copy race during upgrades and an LR/SC livelock between cores; both fixed. AMOs and LR/SC now run inside the L1.

## 2026-10-29
- MSI on one write-back cache (`std_nbdcache`): `owned` bit, snoop port, new config `cv32a6_imac_sv32_wb` (RV32 to fit two cores in the KR260). 300/300 random seeds, 9/9 injected bugs caught.

## 2026-10-26
- Evaluated OpenPiton for multicore: it pins a 2022 CVA6 with a different config system; our CA patch conflicted in 7 of 9 files, and it would need a new L1.5 adapter. Decided to build our own two-core coherence on current CVA6 instead.
- Decided on the write-back cache: the write-through cache cannot hold lines in M, which MSI and CA need.

## 2026-10-20
- [MIDPOINT] Midpoint review. CA instructions run through the CVA6 pipeline on one core; next: multicore.
- CA tag-set module (8 entries, commit-time updates) on the write-through cache, with unit testbenches.

## 2026-10-14
- Repository created from the Turing House template.

## 2026-10-13
- Fixes from review: `data_error` struct field, CA decoding moved to the top-level opcode case.

## 2026-09-08
- The four CA instructions run through the full CVA6 pipeline (single core, 64-bit, write-through cache, Verilator).

## 2026-08-26
- First CA hardware primitives added to CVA6.

## 2026-08-13
- [LAUNCH] Kickoff at Turing House: implement Conditional Access in real hardware.
