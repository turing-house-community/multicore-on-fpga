# Code map: what we changed in CVA6

Our fork is upstream CVA6 at commit `81245a47` ("Fix hgatp unsupported mode writes", OpenHW Group master), plus the changes below on branch `ca-snoop`. To see the full diff yourself:
```bash
cd cva6
git remote add upstream https://github.com/openhwgroup/cva6.git && git fetch upstream
git diff --stat 81245a47 HEAD
```
All paths are relative to `cva6/`. **New** = file added by us.

## The final design (two-core MSI + CA + `bcafail`, write-back cache, RV32, shared L2 on the FPGA)

### Coherent write-back L1 data cache
| File | What changed |
|---|---|
| `core/cache_subsystem/miss_handler.sv` | Coherence tenures before every cacheable miss and write-back; snoop handling (GetS/GetM, write-back of dirty lines); AMOs and LR/SC executed inside the L1; `cwrite` at commit (`AMO_CWRITE`); revocation of CA access on snoop and eviction. The biggest change (~500 lines). |
| `core/cache_subsystem/cache_ctrl.sv` | A store to a Shared line becomes a miss (upgrade to M); `cread`/untag handling on the load port (a failed `cread` returns all ones); loads may not hit a line being fetched. |
| `core/cache_subsystem/std_nbdcache.sv` | The `owned` bit (M vs S) in the status memory; snoop and bus ports; instantiates the CA unit. |
| `core/cache_subsystem/std_cache_subsystem.sv` | Passes the coherence and CA ports through. |
| `core/cache_subsystem/cc_bus.sv` | **New.** The atomic broadcast coherence bus: one tenure at a time, round-robin, forwards each request as a snoop to the other cache. |
| `core/cache_subsystem/cc_directory.sv` | **New.** The directory (default): records which caches hold each line, snoops only those, runs requests for different lines at the same time, back-invalidates on its own evictions. |
| `core/cache_subsystem/cc_interconnect.sv` | **New.** Picks the directory or the bus (parameter `Directory`). |
| `core/include/std_cache_pkg.sv` | Bus request types (GetS/GetM/PutM) and snoop structs. |

### Conditional access
| File | What changed |
|---|---|
| `core/cache_subsystem/ca_tag_set.sv` | **New.** The CA unit: 8-entry tag set, pending table keyed by `trans_id`, accessRevokedBit, CAFAIL, and `cafail_spec_o` (CAFAIL including failed `cread`s not yet committed) for `bcafail`. |
| `core/issue_read_operands.sv`, `core/issue_stage.sv`, `core/alu.sv` | `bcafail`: held in issue until older `cread`s are answered and older `cwrite`/`untagAll` have committed; then it branches on `cafail_spec_o`. |
| `core/decoder.sv` | Decodes `cread`/`cwrite` (custom-0) and `untagOne`/`untagAll`/`bcafail` (custom-1). |
| `core/load_unit.sv`, `core/load_store_unit.sv` | `cread` and untag go through the load port with their CA op. |
| `core/store_unit.sv` | `cwrite` takes the atomic (AMO) path instead of the store buffer. |
| `core/commit_stage.sv` | Commits CA ops; `cwrite` waits until it is the oldest instruction. |
| `core/csr_regfile.sv`, `core/include/riscv_pkg.sv` | CSR 0xCC0 (`CSR_CAFAIL`). |
| `core/cva6.sv` | New ports (`cc_*`, `snoop_*`), parameter `CoherentL1`, CA commit and flush signals. |
| `core/include/ariane_pkg.sv` | The decoded operations `CREAD`, `CWRITE`, `UNTAG_ONE`, `UNTAG_ALL`, `BCAFAIL` and the `AMO_CWRITE` atomic. |
| `core/include/wt_cache_pkg.sv` | The cache-side CA op encoding `ca_op_t` (`CA_CREAD`, …), shared by both caches. |
| `core/store_buffer.sv`, `core/zcmt_decoder.sv`, `core/cva6_mmu/cva6_ptw.sv` | Drive the new `ca_op` request field to `CA_NONE` (ordinary accesses). |
| `core/include/cv32a6_imac_sv32_wb_config_pkg.sv` | **New.** The RV32IMAC config with the write-back cache that everything uses. |
| `core/Flist.cva6` | Lists the new files. |

### Simulation top level
| File | What changed |
|---|---|
| `corev_apu/tb/ariane_testharness.sv`, `corev_apu/tb/ariane_soc_pkg.sv` | With `defines=CVA6_2CORE`: two cores plus the directory (`+define+CVA6_CC_BUS` for the bus). Without it, unchanged. |
| `corev_apu/src/ariane.sv`, `verif/tb/uvmt/cva6_tb_wrapper.sv` | Tie off the new ports (single core). |

### Tests
| File | What it is |
|---|---|
| `core/cache_subsystem/test/std_nbdcache_msi_tb.sv` + `.f` | **New.** One cache, random loads/stores/snoops against a reference memory. |
| `core/cache_subsystem/test/std_nbdcache_2core_tb.sv` + `.f` | **New.** Two caches + directory or bus (`-GDIR`) + CA units, random and directed tests against models of MSI and of the paper's CA rules. |
| `verif/tests/custom/msi_2core/` | **New.** Full-system coherence test (AMO and LR/SC counters, ping-pong, false sharing, message passing). |
| `verif/tests/custom/ca_2core/` | **New.** Full-system CA test (all 4 instructions, CSR, trap revocation, reclamation, try-lock), `bcafail.S` (every `bcafail` outcome against the CSR). `controls/` holds the negative controls. |

### KR260 FPGA (`corev_apu/fpga/kr260/`, all new)
| File | What it is |
|---|---|
| `src/cva6_kr260_top.sv` | Two cores, the directory (or bus, `CcDirectory`), an `axi_cut` per core, `axi_mux`, the shared L2 (`L2Enable`), address remap, mailbox port. |
| `src/axi_l2_cache.sv` | The shared L2: 256 KiB, 64 B lines, 8 ways, non-blocking with 4 MSHRs. |
| `sim/axi_l2_cache_tb.sv` | Random test of the L2 against a reference memory and a difficult DDR model (build with `--assert`). |
| `sim/run_bench_sim.sh` | Builds the simulation of the FPGA design and runs the benchmark campaign on it. |
| `scripts/kr260_bd.tcl` | The Vivado block design (Zynq PS, HP0 port, mailbox BRAM, run GPIO, 50 MHz clock). |
| `scripts/build.tcl`, `kr260_build.sh` | Batch synthesis and implementation (Vivado on Windows driven from WSL). |
| `scripts/gen_filelist.sh` | RTL file list for the FPGA build and its simulation. |
| `scripts/run_test.tcl`, `kr260_run.sh` | Load and run a program over JTAG, read the result and the mailbox. |
| `sim/kr260_bd_wrapper_sim.sv` | Simulation stand-in for the block design, to simulate the exact FPGA RTL in Verilator (`+mem_lat`, `+seed`, `+max_cycles`). |
| `sw/link_kr260.ld` | Linker script with `tohost` in the uncached mailbox. |
| `sw/build_tests.sh` | Builds the correctness tests and ISA tests for the board. |
| `sw/bench/` | Benchmarks (`bench.c`, `crt.S`), micro-benchmarks (`micro.c`, `micro_coh.c`), build/run/analyze/plot scripts, and the comparison with the paper (`compare.py`, `paper_digitize.py`, `paper_interp_2t.py`). |

### Documentation
| File | What it is |
|---|---|
| `docs/msi_ca_kr260/` | **New.** Design notes (overview, MSI and the directory, CA and `bcafail`, KR260 and the L2). |
| `docs/phase2_invalidation_paths.md` | **New.** Early analysis of every path that can invalidate a line. |
| `CLAUDE.md`, `plan.md` | Working notes and the phased plan used during development. |

## Earlier attempt: CA on the write-through cache (not used in the final design)

Before switching to the write-back cache, CA was first prototyped on CVA6's write-through cache (`wt_*`), single core, 64-bit. That cache cannot hold dirty, owned lines, so it cannot support MSI, and the work moved to `std_nbdcache`. The files are still in the fork and still build:

`core/cache_subsystem/wt_dcache*.sv`, `wt_dcache_ca_tag_set.sv`, `wt_dcache_ca_tag_cmp.sv`, `wt_cache_subsystem.sv`, `wt_axi_adapter.sv`, `wt_l15_adapter.sv`, their unit testbenches `core/cache_subsystem/test/wt_dcache_ca_tag_*_tb.sv` and `corev_apu/tb/tb_wt_*`.

## Noise you can ignore
- About 40 files show only a file-mode change (executable bit) from working on Windows/WSL.
- `iti.traces`, `encaps.traces`, `verif/tests/custom/ITI/test_iti_asm.o`: simulation output committed by accident. Safe to delete (a 🙋 task in [PLAN.md](../PLAN.md)).
