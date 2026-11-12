# 7. Challenges, decisions and lessons

What went wrong or was hard, what we decided, and what we would tell the next person. Read this before changing the design.

## Choosing a base: why not OpenPiton
**The usual route** to a multicore CVA6 is **OpenPiton** (Princeton's manycore framework, which ships CVA6 tiles with a coherent L1.5/L2). We tried it first, and dropped it:
- **Old CVA6.** OpenPiton pins a CVA6 commit from 2022 (`4c01614f`). Current CVA6 has a completely different configuration system (`CVA6Cfg` instead of `ariane_cfg_t`), and our first CA patch (written against current CVA6) conflicted in 7 of 9 files when applied to it.
- **Heavy framework.** Its own build tools, Verilator 4.014, and a large tile/NoC infrastructure, most of which we did not need.
- **More work than writing our own.** We would have had to bring OpenPiton up to date with current CVA6 first, then add our changes, including a new adapter between CVA6's cache and OpenPiton's L1.5.

**Decision:** build a coherent two-core system directly on current CVA6. For two cores, a small snooping bus (`cc_bus.sv`, about 150 lines) is far simpler than adopting a manycore framework.

## Fitting the FPGA: why 32-bit
The KR260's K26 chip has 117K LUTs. Two 64-bit CVA6 cores plus their caches, the bus and room for test logic did not fit comfortably, so we moved to the **32-bit RV32IMAC** CVA6 (new config `cv32a6_imac_sv32_wb`) and designed the caches, coherence and tests around it. The first two-core design used 50% of the LUTs and 51% of the block RAM; with the directory and the L2 it is 67% of the LUTs. A third core might fit, a fourth would not with these cache sizes.

Getting a board at all took time. Most FPGAs we could get had far fewer LUTs; the KR260 (117K) is the smallest that fits two cores with room to spare.

## Which cache: write-through vs. write-back
CA was first prototyped on CVA6's **write-through** cache (the `wt_*` files; see [code map](code_map.md#earlier-attempt-ca-on-the-write-through-cache-not-used-in-the-final-design)). A write-through cache never holds a line exclusively and dirty, so it cannot implement MSI's M state, and CA needs MSI's invalidations. We moved to the **write-back** `std_nbdcache` and added the `owned` bit.

## Deadlock freedom
With two caches that both want the bus and both receive snoops, it is easy to build a cycle: cache A waits for the bus while holding something cache B's snoop needs, and B waits for A. Our rule: **a cache can always answer a snoop without needing the bus.** Snoops are accepted only when the cache is idle or merely waiting for the bus, never in the middle of its own memory operation. The testbench's deadlock and starvation watchdogs check this on every run.

## Races found by the testbench
The randomized two-cache testbench found two real bugs in our first design:
1. **Stale shared copy during an upgrade.** A store to an S line starts an upgrade to M. Meanwhile, a load could still hit the old S copy after the other core had already written a newer value. **Fix:** loads may not hit a line the miss unit is fetching.
2. **LR/SC livelock.** Two cores spinning on LR/SC to the same line kept invalidating each other's reservation, forever. **Fix:** after an LR, the cache keeps the bus up to 64 cycles so its SC can complete.

**Lesson:** write the randomized testbench with reference models **before** the full-system tests. Both bugs would have been very hard to find on the full processor.

## Atomic `cwrite`
`cwrite` must check "has any watched line been taken?" and do the store **as one step**. If the check happens early and the store later (as in the original write-through implementation), another core can slip in between. **Solution:** `cwrite` executes at commit, like an atomic instruction. It waits to be the oldest instruction, takes the line in M under a bus tenure (so no snoop can arrive), then checks and stores in the same cycle.

## Speculation
CVA6 issues loads before it knows whether an earlier branch was mispredicted. A `cread` on a wrong path must not tag anything. **Solution:** CA operations are recorded at issue, keyed by their scoreboard index, and take effect only at commit; a flush discards them. Two extra ordering rules were needed (see [design](02_design.md#how-ca-fits-a-speculative-pipeline)) that the paper does not discuss, because it does not model a speculative pipeline.

## Two combinational loops that only Vivado found
Our Verilator runs used `-Wno-UNOPTFLAT`, which hides combinational loops. Vivado refused to generate a bitstream (DRC `LUTLP-1`):
1. **Across the two cores.** Each core's AXI arbiter makes `ar_valid` depend on `ar_ready`; the shared mux makes one core's ready depend on the other's valid. **Fix:** a register slice (`axi_cut`) per core in the KR260 top.
2. **Inside each core.** A trap revoked CA access in the same cycle, which changed the `cwrite` acknowledge, from which the commit stage decides traps. **Fix:** register the trap in `std_nbdcache.sv` (revocation one cycle later; safe because a trap flushes the pipeline).

**Lesson:** before every Vivado run, lint the FPGA top with `-Wwarn-UNOPTFLAT` ([simulation guide](03_simulation.md#4-the-exact-fpga-design)).

## Reading results from a write-back cache
With write-back caches, a value a core stores to DDR may stay in its cache indefinitely, so the PC, which reads DDR, would never see a program's result. **Solution:** an uncached mailbox BRAM; `tohost` and all results go there. Keep this in mind when writing board programs.

## CA failure check is expensive
The paper assumes a free flag register, like x86's EFLAGS that a conditional jump can test. RISC-V has no flags, so our first failure flag was a CSR. CVA6 reads CSRs only at commit, so `cread` + check cost 7 cycles instead of 2, and that made CA much slower than in the paper on read-heavy work.

We tried two fixes:
1. **Return all ones from a failed `cread`** and compare the value first; read the CSR only on a match. Cheap in hardware (one line), and `cread` + check drops to 5 cycles.
2. **`bcafail`, a new branch instruction** that reads CAFAIL without waiting for commit: 4 cycles. The hard part was speculation. The branch must not look at CAFAIL before every older `cread` has been answered, and it must also see a `cread` that failed but has not committed yet. It costs 17 LUTs.

Both lifted CA's throughput by up to 1.5×. **Lesson:** an idea written for x86 does not always map to RISC-V directly; look for the closest RISC-V mechanism (here, a branch) instead of copying the x86 one.

## Bus or directory
With two cores a snooping bus does the job, and it was the right place to start. But the paper uses a directory, and anything beyond two cores needs one, so we added a directory next to the bus with the same interface. Keeping both selectable (`cc_interconnect.sv`) let us measure the difference on the same design: up to 17% faster on the board, never more than 2% slower. **Lesson:** keep the old version switchable when you replace a block; it makes a fair comparison almost free.

## An L2 bug that only the board found
Without an L2, every miss went to DDR, so our platform differed from the paper's in a way that changed the results. We wrote a shared L2 (`axi_l2_cache.sv`). It passed its randomized testbench and the full-system simulation, then **hung on the board**.
- **The cause:** an AXI rule says that once a request is offered (`valid` high), its contents must not change until it is accepted (`ready`). The L2's arbiter towards DDR could switch to a different request while waiting. The simulated DDR always accepted immediately, so this never happened in simulation; the real interconnect sometimes makes you wait.
- **Why our checks missed it:** we had written assertions for exactly this rule, but Verilator only checks assertions when you build with `--assert`, and we had not.
- **The fix:** the arbiter now holds its choice until the request is accepted. The DDR model in the testbench now stalls at random, and every L2 build uses `--assert`.

**Lessons:** a simulation model that is nicer than the real hardware hides bugs; make your models difficult. And check that your assertions actually run, for example by breaking one on purpose.

## Making the simulator match the board
We wanted to know whether simulator numbers can be trusted, so we ran every benchmark both ways. Without an L2, the simulated DDR needed a fixed extra latency (34 cycles, measured with `micro_coh.c` on the board) and still differed by up to 13% in a few contended cases. With the L2, most misses never reach DDR, and simulator and board now agree exactly in all 144 configurations.

## Faster is not always better
On read-heavy work, epochs (QSBR) beat CA in our runs, which at first made us wonder what CA is for. The answer is in the other numbers: CA never leaves a removed node waiting (0, against 100–200 for epochs, and without any bound if a thread stalls), and under contention it is the fastest scheme. The paper's large speed-ups appear at 16–32 threads, which two cores cannot show. **Lesson:** decide up front which numbers answer your question, and report the ones that do not go your way too.

## Comparing with numbers read off a plot
The paper's results exist only as plots. We read them off the images in the PDF with a script, and later found that it read steep curves too low: it averaged each marker with the line running into it. Also, the paper has no 2-thread point, so we estimate it from the 1- and 4-thread points. **Lesson:** check a few digitized values by eye before trusting them.

## Learning curve
We had to learn, at the same time:
- **CVA6's microarchitecture**: the pipeline, the scoreboard and `trans_id`, the load/store unit, and the cache subsystems.
- **The KR260 and Vivado**: block designs, the Zynq PS, how data flows between our cores (PL) and the ARM side's DDR (PS), `xsdb`, and running Windows tools from WSL.
- **The concepts**: cache coherence, RISC-V atomics, memory consistency, and lock-free memory reclamation.

Practical things that cost us days:
- **Vivado version and licence.** The KR260 needs Vivado 2023.2 or newer; the institute's licence was for 2019.2. The free Standard edition of 2023.2 supports the KR260's chip.
- **The board itself.** Before trusting it with our design we booted the official Linux image to check it worked, which needed the board's Ethernet set up and a login. Programs are loaded through the JTAG debug adapter (the micro-USB port), which needs Vivado's cable drivers on Windows.
- **Two file systems.** Vivado runs on Windows, everything else in WSL. Builds inside `/mnt/c` are very slow, and Windows tools cannot work well inside the WSL file system, so the scripts copy sources across (see [the FPGA guide](04_fpga_kr260.md)).
- **Old repositories.** OpenPiton looked like the obvious start, but it pins a 2022 CVA6 and its own tools. An unmaintained framework can cost more than writing the part you need yourself.

### A suggested learning path for newcomers
1. The CA paper, sections 1–4, and [01_background.md](01_background.md).
2. *A Primer on Memory Consistency and Cache Coherence*, chapters 2, 6 and 7 (coherence basics, snooping protocols).
3. The [CVA6 user manual](https://docs.openhwgroup.org/projects/cva6-user-manual/), then read `core/cva6.sv` top-down and follow one load through `load_store_unit.sv` → `load_unit.sv` → `std_nbdcache.sv` → `cache_ctrl.sv` → `miss_handler.sv`.
4. Run [the two-cache testbench](03_simulation.md#2-two-caches-the-msi--ca-testbench) with `+catrace` and follow a few CA operations in the trace.
5. Break something on purpose (e.g. make a GetM snoop not revoke CA access in `ca_tag_set.sv`) and watch the testbench catch it.
6. Then the board: [04_fpga_kr260.md](04_fpga_kr260.md).

---

**Next:** [the project in depth](in_depth.md), with a FAQ.
