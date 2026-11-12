# Execution Plan: Implementing Conditional Access on FPGA
_Last updated: 2026-11-12 by @AceAryan_

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

## Phase 3: Closer to the paper (2026-11-11 → 2026-11-12)
- [x] Smaller retire lists (512) and a blocking QSBR, so epochs cannot hide unbounded garbage
- [x] A directory next to the bus (`cc_directory.sv`), selectable for comparison: up to 17% faster on the board
- [x] Cheaper failure checks: a failed `cread` returns all ones (fast check), and `bcafail`, a branch on CA failure (4 cycles instead of 7)
- [x] The benchmark campaign on a cycle-exact simulation of the FPGA design, next to the board and the paper
- [x] A shared 256 KiB L2 in front of DDR, as in the paper's platform; found and fixed an AXI bug that only the board showed
- [x] The paper's 2-thread values estimated from its plots; final poster (A1 and A0)

## Stretch / Ideas
Open for anyone who wants to continue. Pick one, tell us on Discord, and add a line to [LOG.md](LOG.md) when you learn something. Rough difficulty in brackets.
- [ ] **Failure in a register** [hard]: a `cread` variant that writes its success into a second register, so no separate check is needed at all. Compare with `bcafail` using `micro.c` and the benchmarks. — unassigned 🙋
- [ ] **Faster `bcafail` after `cwrite`** [medium]: today `bcafail` waits for an older `cwrite` to commit, which makes `cread` + `cwrite` + `bcafail` 1 cycle slower than the CSR check. — unassigned 🙋
- [ ] **Native-Linux board flow** [easy]: a `kr260_run_linux.sh` / build script that calls Linux `xsdb`/`vivado` directly (see [docs/04_fpga_kr260.md](docs/04_fpga_kr260.md#using-native-linux-instead-of-wsl)). — unassigned 🙋
- [ ] **Clean up the fork** [easy]: remove the accidentally committed `iti.traces`, `encaps.traces`, `test_iti_asm.o`, and undo the ~40 file-mode-only changes. — unassigned 🙋
- [ ] **More baselines** [medium]: the paper's `ibr`, `he` and `rcu` in `bench.c`. — unassigned 🙋
- [ ] **Tag-set depth sweep** [easy]: rebuild with `DEPTH` 4/8/16 in `ca_tag_set.sv`, measure area and the BST's eviction failures. — unassigned 🙋
- [ ] **Cache-to-cache transfer** [medium]: let the owning cache send dirty data directly to the other cache instead of through the L2. — unassigned 🙋
- [ ] **64-byte L1 lines** [medium]: the last big difference from the paper's platform. — unassigned 🙋
- [ ] **Higher clock** [medium]: timing has 2.9 ns slack at 50 MHz; try 55–60 MHz. — unassigned 🙋
- [ ] **More cores** [hard]: the directory is ready for it, but 4 cores need smaller caches or a bigger FPGA. — unassigned 🙋
- [ ] **C intrinsics header** [easy]: move the inline-assembly wrappers from `bench.c` into a reusable `ca.h`. — unassigned 🙋

## Blockers & Open Questions
- Should CA state survive interrupts and context switches (save/restore the tag set), so it can be used under an OS? Today a trap simply revokes access.
- Is it worth upstreaming the MSI write-back cache to CVA6 independently of CA?
- With 4+ cores, do CA's gains over epochs appear, as the paper's 16–32-thread results suggest?

<!--
Conventions:
- Tick boxes as tasks finish; add a line to LOG.md if anything was learned.
- Mark unassigned tasks with 🙋 so newcomers can pick them up.
- Update "Last updated" whenever you edit this file.
-->
