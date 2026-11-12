# Implementing Conditional Access on FPGA
A dual-core, cache-coherent RISC-V processor (CVA6) with the Conditional Access instructions for immediate memory reclamation, running on an AMD KR260 FPGA.

**Status:** ✅ completed
**Maintainers:** @AceAryan
**Started:** August 2026

Team: Aryan Kumar, Nishant Dhankhar, Kudumula Vinod Kumar Reddy. Advisor: Prof. Ajay Singh, Department of Computer Science and Engineering, IIT Gandhinagar.

![poster](docs/demos/completion_poster.png)

## Why
In lock-free data structures, a thread can read a node that another thread has just freed: a **use-after-free**. Software fixes (hazard pointers, epoch-based reclamation) either slow every read or delay freeing memory. **Conditional Access** (Singh, Brown, Spear, [arXiv 2302.12958](https://arxiv.org/abs/2302.12958)) reuses the cache-coherence protocol, which already notices when another core writes a line you have read, to warn the reader. Nodes can then be freed **immediately**. The paper evaluated it only in a simulator; we built it in real hardware. [More background](docs/01_background.md).

## Quickstart
```bash
# 1. Clone with the CVA6 fork (submodule) and all its dependencies
git clone --recursive https://github.com/turing-house-community/multicore-on-fpga.git
cd multicore-on-fpga/cva6

# 2. Install the tools: RISC-V GCC, Verilator, Spike (once; see docs/00_getting_started.md)

# 3. Two caches + directory + CA units, random traffic against reference models (~2 min)
mkdir -p build
verilator --binary --timing -j 8 -Wno-fatal -Wno-lint -Wno-style -Wno-UNOPTFLAT \
  --top-module std_nbdcache_2core_tb -Mdir build/tb2 -f core/cache_subsystem/test/std_nbdcache_2core_tb.f
build/tb2/Vstd_nbdcache_2core_tb +seed=1 +nrandom=1500          # prints PASSED

# 4. Two complete cores running the CA test program (~10 min build)
make verilate target=cv32a6_imac_sv32_wb defines=CVA6_2CORE ver-library=work-ver-2core
riscv64-unknown-elf-gcc -march=rv32ima_zicsr -mabi=ilp32 -nostdlib -nostartfiles \
  -T verif/tests/custom/ca_2core/link.ld verif/tests/custom/ca_2core/ca_2core.S -o build/ca_2core.elf
LD_LIBRARY_PATH=tools/spike/lib work-ver-2core/Variane_testharness build/ca_2core.elf   # *** SUCCESS ***

# 5. On a KR260 with the prebuilt bitstream (see docs/04_fpga_kr260.md for setup)
mkdir -p $KR260_WIN_DIR/out && cp ../prebuilt/cva6_kr260.{bit,xsa} $KR260_WIN_DIR/out/
corev_apu/fpga/kr260/sw/build_tests.sh build/board
KR260_PROGRAM=1 corev_apu/fpga/kr260/kr260_run.sh build/board/ca_2core.elf 30            # RESULT PASS
```
Keep the repository inside the Linux/WSL file system (not `/mnt/c/...`), or builds get very slow.

## Where we are
**What works:** everything we set out to build.

Starting from the open-source single-core [CVA6](https://github.com/openhwgroup/cva6) RISC-V processor (32-bit, RV32IMAC):
1. **A second core** with its own private L1 data cache.
2. **MSI cache coherence** between the two write-back caches, through a directory (our first version used a snooping bus, which is still selectable).
3. **The four CA instructions** in the pipeline: `cread`, `cwrite`, `untagOne`, `untagAll`, with a failure flag in CSR 0xCC0.
4. **`bcafail`, a new branch instruction** that jumps if a CA operation failed. The paper assumes a flag register, which RISC-V does not have; this is the closest RISC-V equivalent.
5. **A shared 256 KiB L2 cache** in front of DDR, as in the paper's platform.
6. **The system on an AMD KR260**: both cores at 50 MHz using the board's DDR, programs loaded over JTAG.

Then we verified it (randomized testbenches, injected bugs, ISA tests, on-board tests) and ran the paper's benchmarks on the board and on a cycle-exact simulation of the same design. [How the hardware works](docs/02_design.md).

| | |
|---|---|
| **Memory** | CA frees every removed node immediately: **0** unfreed nodes, vs. 102–202 for epochs and 1,500–3,000 for never freeing |
| **Throughput** | fastest scheme under high contention: **1.27×** the never-freeing baseline on a stack (epochs 1.03×, hazard pointers 0.99×), and ahead of epochs on the hash table (0.99 vs 0.91); epochs stay fastest on read-heavy work |
| **Failure check** | `cread` 2 cycles (plain load 1); `cread` + check: 7 with the CSR, 5 with the fast check, **4 with `bcafail`** |
| **Coherence cost** | with the L2: read miss 33 cycles, miss to a line the other core holds dirty 32, handoff between cores 59 (without it: 54, 97, 151) |
| **Area** | CA unit ~1,000 LUTs per core, no memory blocks; `bcafail` 17 LUTs; directory 676 LUTs; shared L2 18.5K LUTs; whole design 67% of the FPGA |
| **Correctness** | 1,500/1,500 randomized two-cache simulations, 26/27 injected bugs caught, 200/200 L2 tests, 72/73 ISA tests, 1,800/1,800 benchmark runs valid; the simulation matches the board cycle for cycle |
| **vs. the paper** | at 2 threads close on the list and hash table; on the stack CA does better than in the paper. The paper's large wins appear at 16–32 threads, which 2 cores cannot test |

Details: [docs/06_results.md](docs/06_results.md).

**What's next:** the 🙋 ideas in [PLAN.md](PLAN.md#stretch--ideas); the most interesting are more cores and making CA work under an operating system.

**Open questions:** whether CA state should survive interrupts and context switches, and how CA behaves with 4 or more cores. Details live in [PLAN.md](PLAN.md).

## How to join
1. Read this README, then skim [LOG.md](LOG.md) to see how we got here.
2. Pick a task marked 🙋 in [PLAN.md](PLAN.md) (or ask a maintainer). To get set up, do [getting started](docs/00_getting_started.md) and the first two levels of [the simulation guide](docs/03_simulation.md).
3. Ping us on [Discord](https://discord.com/channels/1552005581009846404/1561748566366617630).

## Resources
- Singh, Brown, Spear: *Efficient Hardware Primitives for Immediate Memory Reclamation in Optimistic Data Structures*, [arXiv 2302.12958](https://arxiv.org/abs/2302.12958)
- [CVA6](https://github.com/openhwgroup/cva6) and its [user manual](https://docs.openhwgroup.org/projects/cva6-user-manual/)
- Nagarajan, Sorin, Hill, Wood: *A Primer on Memory Consistency and Cache Coherence* (2nd ed.)
- [AMD Kria KR260 Robotics Starter Kit](https://www.amd.com/en/products/system-on-modules/kria/k26/kr260-robotics-starter-kit.html)

## Guides
| # | Guide | You will |
|---|---|---|
| 0 | [Getting started](docs/00_getting_started.md) | install the tools and do a first run |
| 1 | [Background](docs/01_background.md) | understand the problem and Conditional Access |
| 2 | [Hardware design](docs/02_design.md) | understand MSI, the directory, the CA unit, `bcafail` and the L2 |
| 3 | [Simulation](docs/03_simulation.md) | verify everything without a board |
| 4 | [FPGA (KR260)](docs/04_fpga_kr260.md) | build the bitstream and run on the board |
| 5 | [Benchmarks](docs/05_benchmarks.md) | rerun the paper's evaluation |
| 6 | [Results](docs/06_results.md) | see what we measured |
| 7 | [Challenges](docs/07_challenges.md) | learn from our mistakes and decisions |
| 8 | [In depth](docs/08_in_depth.md) | follow one idea through the whole system |
| – | [Code map](docs/code_map.md) | find every file we changed in CVA6 |

## Repository layout
| Path | What |
|---|---|
| `cva6/` | **submodule**: our CVA6 fork ([AceAryan/cva6](https://github.com/AceAryan/cva6), branch `ca-snoop`) with all RTL, tests, FPGA scripts and benchmarks |
| `docs/` | the guides above, the poster (`talks/`, A1 and A0) and demos |
| `prebuilt/` | the KR260 bitstream and hardware platform, with Vivado reports |
| `results/` | raw board and simulation output of all measurements, decoded tables and charts ([index](results/README.md)) |
| `PLAN.md` | what was done, and open tasks for newcomers (🙋) |
| `LOG.md` | how we got here: what was tried, what broke, why decisions were made |
| `project.yml` | metadata for the Turing House dashboard |

## Acknowledgements
We thank Prof. Ajay Singh for his guidance throughout this project, and the Department of Computer Science and Engineering, IIT Gandhinagar, for access to the AMD KR260 board and tools.

## License
This repository's own content is under the Apache License 2.0 ([LICENSE](LICENSE)). The CVA6 code in `cva6/` keeps its own licenses (mostly Solderpad Hardware License 2.0); see the files there.

---
Part of the [Turing House Community](https://github.com/turing-house-community), IITGN CSE.
