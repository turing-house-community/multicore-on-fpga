# Execution Plan: Implementing Conditional Access on FPGA
_Last updated: 2026-11-08 by @AceAryan_

## Goal
A two-core RISC-V processor (CVA6) with private, MSI-coherent L1 caches and the four Conditional Access instructions (`cread`, `cwrite`, `untagOne`, `untagAll`) from Singh, Brown and Spear, running on an AMD KR260 FPGA, verified, and benchmarked against the paper's evaluation.

**Status: done.** Everything below Phase 5 is open for anyone who wants to continue. New here? Start with the [README](README.md), then [docs/00_getting_started.md](docs/00_getting_started.md).

## Phase 0: Understanding and first prototype (Aug–Oct 2026)
- [x] Read the paper; decide on CVA6 as the base core
- [x] Add the four CA instructions to CVA6's decoder and pipeline (single core, 64-bit, write-through cache)
- [x] CA tag set with commit-time semantics on the write-through cache, unit testbenches
- [x] Evaluate OpenPiton for multicore; drop it (see [docs/07_challenges.md](docs/07_challenges.md))
- [x] Decide: build MSI on CVA6's write-back cache, 32-bit, 2 cores, snooping bus

## Phase 1: MSI on one cache
- [x] New config `cv32a6_imac_sv32_wb`
- [x] `owned` bit (M/S/I), snoop port, write-back on snoop in `std_nbdcache`
- [x] Single-cache randomized testbench, 300 seeds, 9 injected bugs caught

## Phase 2: Two cores, coherence bus
- [x] `cc_bus.sv`: atomic broadcast bus, deadlock-free by construction
- [x] AMOs and LR/SC inside the L1; LR/SC livelock fix
- [x] Two-cache randomized testbench with a single-writer checker
- [x] Two-core full-processor model (`CVA6_2CORE`), `msi_2core` test, 72/73 ISA tests

## Phase 3: Conditional Access on the coherent cache
- [x] `ca_tag_set.sv`: 8-line tag set, revocation on GetM snoop / eviction / overflow / trap
- [x] `cwrite` at commit as an atomic; CSR 0xCC0
- [x] Reference model of the paper's rules in the two-cache testbench; 11 directed tests; 400/400 runs
- [x] `ca_2core` full-system test plus negative controls

## Phase 4: KR260
- [x] Block design, top level, build and run scripts
- [x] Fix two combinational loops found by Vivado
- [x] Bitstream at 50 MHz; all tests pass on the board, identical to simulation

## Phase 5: Evaluation and write-up
- [x] Paper's benchmarks (list, BST, stack, hash × none/ca/hp/qsbr), 288 runs on the board
- [x] Micro-benchmarks: instruction latency and coherence cost; area from Vivado
- [x] Poster, documentation, this repository

## Next: open tasks 🙋
Pick one, tell a maintainer, and add a line to [LOG.md](LOG.md) when you learn something. Rough difficulty in brackets.
- [ ] **Branch on CA failure** [hard, highest impact]: a `bcafail` instruction, or a `cread` variant that reports failure in a register, so the check costs ~0 instead of 5 cycles. Re-measure with `micro.c` and the benchmarks. 🙋
- [ ] **Native-Linux board flow** [easy]: a `kr260_run_linux.sh` / build script that calls Linux `xsdb`/`vivado` directly (see [docs/04_fpga_kr260.md](docs/04_fpga_kr260.md#using-native-linux-instead-of-wsl)). 🙋
- [ ] **Clean up the fork** [easy]: remove the accidentally committed `iti.traces`, `encaps.traces`, `test_iti_asm.o`, undo the ~40 file-mode-only changes. 🙋
- [ ] **More baselines** [medium]: the paper's `ibr`, `he` and `rcu` in `bench.c`. 🙋
- [ ] **Tag-set depth sweep** [easy]: rebuild with `DEPTH` 4/8/16 in `ca_tag_set.sv`, measure area and the BST's eviction failures. 🙋
- [ ] **Cache-to-cache transfer** [medium]: let the owning cache send dirty data directly instead of via DDR; should cut the 97-cycle dirty miss. 🙋
- [ ] **64-byte lines or an L2** [medium]: closer to the paper's platform. 🙋
- [ ] **Higher clock** [medium]: timing has 2.4 ns slack at 50 MHz; try 55–60 MHz. 🙋
- [ ] **More cores** [hard]: 4 cores need smaller caches (block RAM) and a scalable interconnect or a directory. 🙋
- [ ] **C intrinsics header** [easy]: move the inline-assembly wrappers from `bench.c` into a reusable `ca.h`. 🙋

## Blockers & Open Questions
- Should CA failure also be visible to interrupts / an OS (save and restore the tag set on context switch)? Today a trap simply revokes access.
- Is it worth upstreaming the MSI write-back cache to CVA6 independently of CA?
- 4+ cores: snooping bus vs. directory, given the KR260's block-RAM limit.

<!--
Conventions:
- Tick boxes as tasks finish; add a line to LOG.md if anything was learned.
- Mark unassigned tasks with 🙋 so newcomers can pick them up.
- Update "Last updated" whenever you edit this file.
-->
