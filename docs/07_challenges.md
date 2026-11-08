# 7. Challenges, decisions and lessons

What went wrong or was hard, what we decided, and what we would tell the next person. Read this before changing the design.

## Choosing a base: why not OpenPiton
**The usual route** to a multicore CVA6 is **OpenPiton** (Princeton's manycore framework, which ships CVA6 tiles with a coherent L1.5/L2). We tried it first, and dropped it:
- **Old CVA6.** OpenPiton pins a CVA6 commit from 2022 (`4c01614f`). Current CVA6 has a completely different configuration system (`CVA6Cfg` instead of `ariane_cfg_t`), and our first CA patch (written against current CVA6) conflicted in 7 of 9 files when applied to it.
- **Heavy framework.** Its own build tools, Verilator 4.014, and a large tile/NoC infrastructure, most of which we did not need.
- **More work than writing our own.** We would have had to bring OpenPiton up to date with current CVA6 first, then add our changes, including a new adapter between CVA6's cache and OpenPiton's L1.5.

**Decision:** build a coherent two-core system directly on current CVA6. For two cores, a small snooping bus (`cc_bus.sv`, about 150 lines) is far simpler than adopting a manycore framework.

## Fitting the FPGA: why 32-bit
The KR260's K26 chip has 117K LUTs. Two 64-bit CVA6 cores plus their caches, the bus and room for test logic did not fit comfortably, so we moved to the **32-bit RV32IMAC** CVA6 (new config `cv32a6_imac_sv32_wb`) and designed the caches, coherence and tests around it. The final design uses 50% of the LUTs and 51% of the block RAM. A third and fourth core would not fit with these cache sizes: block RAM runs out first.

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
The paper assumes a free flag register. In RISC-V, our failure flag is a CSR, and CVA6 reads CSRs only at commit, so `cread` + check costs 7 cycles instead of 2. This is the main reason CA is slower than in the paper on read-heavy workloads. A branch-on-CA-failure instruction would fix it (first item in [PLAN.md](../PLAN.md)).

## Learning curve
We had to learn, at the same time:
- **CVA6's microarchitecture**: the pipeline, the scoreboard and `trans_id`, the load/store unit, and the cache subsystems.
- **The KR260 and Vivado**: block designs, the Zynq PS, `xsdb`, and running Windows tools from WSL.
- **The concepts**: cache coherence, RISC-V atomics, memory consistency, and lock-free memory reclamation.

### A suggested learning path for newcomers
1. The CA paper, sections 1–4, and [01_background.md](01_background.md).
2. *A Primer on Memory Consistency and Cache Coherence*, chapters 2, 6 and 7 (coherence basics, snooping protocols).
3. The [CVA6 user manual](https://docs.openhwgroup.org/projects/cva6-user-manual/), then read `core/cva6.sv` top-down and follow one load through `load_store_unit.sv` → `load_unit.sv` → `std_nbdcache.sv` → `cache_ctrl.sv` → `miss_handler.sv`.
4. Run [the two-cache testbench](03_simulation.md#2-two-caches-the-msi--ca-testbench) with `+catrace` and follow a few CA operations in the trace.
5. Break something on purpose (e.g. make a GetM snoop not revoke CA access in `ca_tag_set.sv`) and watch the testbench catch it.
6. Then the board: [04_fpga_kr260.md](04_fpga_kr260.md).
