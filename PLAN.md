# Execution Plan: Implementing Conditional Access on FPGA
_Last updated: 2026-11-08 by @AceAryan_

## Goal
A two-core RISC-V processor (CVA6) with private, MSI-coherent L1 caches and the four Conditional Access instructions (`cread`, `cwrite`, `untagOne`, `untagAll`), running on an AMD KR260 FPGA, verified, and benchmarked against the paper's evaluation.

## Phase 1: Launch → Midpoint (2026-08-13 → 2026-10-20)
- [x] Read the paper (Singh, Brown, Spear); choose CVA6 as the base core
- [x] Decode the four CA instructions and run them through CVA6's pipeline (single core, 64-bit, write-through cache)
- [x] CA tag set with commit-time semantics on the write-through cache, with unit testbenches
- [x] Review fixes: `data_error` struct field, CA decoding at the top-level opcode case

## Phase 2: Midpoint → Completion
- [x] Evaluate OpenPiton for multicore; drop it (old CVA6, heavy framework, needs an L1.5 adapter)
- [x] Move to the write-back cache and RV32 (`cv32a6_imac_sv32_wb`) to fit two cores on the KR260
- [x] MSI on one cache: `owned` bit, snoop port; randomized testbench, 300 seeds, 9/9 injected bugs caught
- [x] Two cores on `cc_bus` (atomic snooping bus); AMOs and LR/SC in the L1; fix a stale-S race and an LR/SC livelock
- [x] CA on the coherent cache: `ca_tag_set.sv`, `cwrite` at commit, CSR 0xCC0; 400/400 runs, 11/11 CA bugs caught
- [x] Full-processor tests: 72/73 ISA tests, `msi_2core`, `ca_2core`, negative controls
- [x] KR260 bitstream at 50 MHz (two combinational loops fixed); all tests pass on the board, identical to simulation
- [x] Paper's benchmarks on the board (288 runs), instruction latency, coherence cost, area
- [x] Poster, documentation and this repository

## Stretch / Ideas
Open for anyone who wants to continue. Pick one, tell us on Discord, and add a line to [LOG.md](LOG.md) when you learn something. Rough difficulty in brackets.
- [ ] **Branch on CA failure** [hard, highest impact]: a `bcafail` instruction, or a `cread` variant that reports failure in a register, so the check costs ~0 instead of 5 cycles. Re-measure with `micro.c` and the benchmarks. — unassigned 🙋
- [ ] **Native-Linux board flow** [easy]: a `kr260_run_linux.sh` / build script that calls Linux `xsdb`/`vivado` directly (see [docs/04_fpga_kr260.md](docs/04_fpga_kr260.md#using-native-linux-instead-of-wsl)). — unassigned 🙋
- [ ] **Clean up the fork** [easy]: remove the accidentally committed `iti.traces`, `encaps.traces`, `test_iti_asm.o`, and undo the ~40 file-mode-only changes. — unassigned 🙋
- [ ] **More baselines** [medium]: the paper's `ibr`, `he` and `rcu` in `bench.c`. — unassigned 🙋
- [ ] **Tag-set depth sweep** [easy]: rebuild with `DEPTH` 4/8/16 in `ca_tag_set.sv`, measure area and the BST's eviction failures. — unassigned 🙋
- [ ] **Cache-to-cache transfer** [medium]: let the owning cache send dirty data directly instead of via DDR; should cut the 97-cycle dirty miss. — unassigned 🙋
- [ ] **64-byte lines or an L2** [medium]: closer to the paper's platform. — unassigned 🙋
- [ ] **Higher clock** [medium]: timing has 2.4 ns slack at 50 MHz; try 55–60 MHz. — unassigned 🙋
- [ ] **More cores** [hard]: 4 cores need smaller caches (block RAM) and a scalable interconnect or a directory. — unassigned 🙋
- [ ] **C intrinsics header** [easy]: move the inline-assembly wrappers from `bench.c` into a reusable `ca.h`. — unassigned 🙋

## Blockers & Open Questions
- Should CA state survive interrupts and context switches (save/restore the tag set), so it can be used under an OS? Today a trap simply revokes access.
- Is it worth upstreaming the MSI write-back cache to CVA6 independently of CA?
- For 4+ cores: snooping bus or directory, given the KR260's block-RAM limit?

<!--
Conventions:
- Tick boxes as tasks finish; add a line to LOG.md if anything was learned.
- Mark unassigned tasks with 🙋 so newcomers can pick them up.
- Update "Last updated" whenever you edit this file.
-->
