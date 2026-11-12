# 8. In depth: how it all fits together

The other guides each cover one part. This page follows one idea through the whole system: from the problem, to the instructions, to the hardware that makes them work, to what we measured. It assumes you know what a pipeline and a cache are. Paths are relative to `cva6/`.

## Why immediate freeing is safe with CA
Take a sorted list `A → N → B`. Core 0 is searching and has just read `A->next`, so it holds a pointer to `N`. Core 1 wants to delete `N`: it writes `A->next = B` and then frees `N`.

To write `A->next`, core 1 needs `A`'s cache line in the Modified state. The coherence protocol therefore invalidates every other copy of that line, including core 0's. So the hardware already knows, at exactly the right moment, that core 0's view has gone stale. CA passes that knowledge on to software:
- `cread` loads a value **and tags its line** (each core can tag up to 8 lines).
- If a tagged line is invalidated by another core's write, or leaves the cache, the core's access is **revoked**, and its next `cread` or `cwrite` fails.

A search with CA tags hand over hand: it always keeps the current node and the one before it tagged (`list_search` in `corev_apu/fpga/kr260/sw/bench/bench.c`):
```c
untagAll();
pred = head;
curr = cread(&pred->next);  if (failed) retry;
ck   = cread(&curr->key);   if (failed) retry;
while (ck < key) {
    untagOne(pred);                          // keep only pred and curr tagged
    pred = curr;
    curr = cread(&pred->next);  if (failed) retry;
    ck   = cread(&curr->key);   if (failed) retry;
}
```
If core 1 frees `curr` while core 0 is looking at it, core 1 must first have written `pred->next`. That invalidated `pred`, which core 0 has tagged, so core 0's next `cread` fails and it retries before using anything from `curr`. Every value the reader acts on came from a `cread` that succeeded after the node before it was tagged. That is why core 1 may call `free()` right after unlinking.

Updates use a try-lock: `cread` the lock word, then `cwrite` it. The `cwrite` succeeds only if nobody has touched the tagged lines in between. The stack needs no locks at all: `pop` is `cread(top)`, `cread(t->next)`, `cwrite(top, next)`.

## What the hardware has to provide
1. **Coherence that invalidates**, and tells the CA unit when it does. CVA6 is single-core and had no coherence, so we added MSI to its write-back L1 ([design](02_design.md)).
2. **A tag set next to each L1**, checked on every `cread` and `cwrite`: `core/cache_subsystem/ca_tag_set.sv`.
3. **An atomic `cwrite`**: the check and the store must happen together.
4. **Correct behaviour in a speculative pipeline**, which the paper's simulator did not model.
5. **A cheap way to check for failure.**

The next sections take these one at a time.

## Coherence: from a bus to a directory
Each L1 line is Modified, Shared or Invalid; we added one bit (`owned`) to CVA6's write-back cache to tell M from S. Before a cache touches memory for a line, it asks the interconnect for a *tenure*. The interconnect snoops the other cache if needed: on a GetM the other copy is invalidated, and that is the event the CA unit listens to.

We started with an atomic snooping bus (`cc_bus.sv`, about 150 lines): simple, and with two cores a broadcast reaches exactly the cache that matters. Later we added a directory (`cc_directory.sv`), as in the paper. It records which caches hold each line, snoops only those, and lets misses to different lines proceed at the same time. A `cc_interconnect.sv` wrapper picks either one, so we could compare them on the same design.

One rule keeps all of this deadlock-free: **a cache must always be able to answer a snoop without needing the interconnect itself.** Caches accept snoops only while idle or waiting for a tenure, never in the middle of their own memory operation.

## CA in a speculative pipeline
CVA6 runs loads before it knows whether an older branch was mispredicted. A `cread` on a wrong path must not change anything. So:
- `cread`, `untagOne` and `untagAll` are **recorded at issue** in a small table, keyed by the instruction's scoreboard index (`trans_id`), and **take effect at commit**. A flush simply drops them.
- `cwrite` **runs at commit, like an atomic instruction** (`AMO_CWRITE` in `miss_handler.sv`). It waits until it is the oldest instruction, takes the line in M during a tenure (so no snoop can arrive), then checks the tag set and stores in the same step.
- Two extra rules the paper does not need: while an `untagAll` waits to commit, no new CA request is accepted; and a `cread` fails if an older `cread` that has not committed yet already lost its line.

## Checking for failure
The paper assumes a flag register that a conditional jump can test, like EFLAGS on x86. RISC-V has no flags. Our first version put CAFAIL in a CSR (0xCC0), and that turned out to be the biggest cost: CVA6 executes CSR reads only at commit, so `cread` + check took 7 cycles against 2 for the `cread` alone.

We then tried two cheaper checks:
- **The fast check.** A failed `cread` returns `0xFFFF_FFFF`. Software compares the value and reads the CSR only on a match, which is rare. That gives 5 cycles.
- **`bcafail`.** A branch instruction (custom-1, funct3 2) that jumps if CAFAIL is set, without waiting for commit. That gives 4 cycles.
  - The issue stage holds it until every older `cread` has its answer and every older `cwrite`/`untagAll` has committed.
  - Then it reads CAFAIL together with any older `cread` that failed but has not committed yet, and branches.
  - It is predicted not taken.

The CSR stays the reference: the test `verif/tests/custom/ca_2core/bcafail.S` compares every `bcafail` outcome with it, also while the other core is writing the watched line.

## The shared L2
Our first system sent every L1 miss straight to the ARM side's DDR4. The paper's platform has a shared 256 KiB L2, and that difference changed results: a core-to-core handoff cost 151 cycles, because dirty data went out to DDR and back.

The L2 we wrote (`corev_apu/fpga/kr260/src/axi_l2_cache.sv`) sits between the cores' AXI mux and DDR.
- **Size and layout:** 256 KiB, 64-byte lines, 8 ways, write-back, data in UltraRAM.
- **Non-blocking:** up to four misses can be in flight, and hits are served while they wait.
- **No coherence logic of its own:** it answers a write only once the data is in the L2, and the L1s already write dirty data back before answering a snoop, so a later read from either core sees the latest data.
- **Reset:** it empties itself on every program load, because the ARM side writes the new program straight into DDR.

With the L2, a handoff costs 59 cycles and a miss 33.

## How a program runs on the board
1. A C program (`bench.c`) or a test (`.S`) is cross-compiled for RV32IMA, bare metal (no OS), and linked to run at `0x8000_0000`, with `tohost` in an uncached mailbox at `0xC000_0000`.
2. Vivado turns the RTL into a bitstream for the KR260's programmable logic (PL).
3. On the PC, `kr260_run.sh` uses AMD's `xsdb` over the JTAG cable to:
   1. load the bitstream and set up the ARM side (PS), which owns the DDR;
   2. hold the cores in reset;
   3. copy the program into DDR;
   4. release the cores.
4. Both cores start at `0x8000_0000` (the PS sees that DDR at `0x4000_0000`). When the program finishes, it writes its result and its measurements to the mailbox, and `xsdb` reads them back as `RESULT` and `MBOX` lines.

The mailbox is needed because the caches are write-back: a result stored to DDR could stay in a cache, invisible to the PC.

## How we know it works
We tested from small to large, and made sure each level could fail:
1. **One cache, then two caches with the interconnect**, driven with random traffic and checked every cycle against models of MSI and of the paper's CA rules. To check the checker, we injected 27 bugs on purpose; it caught 26 (the one it missed cannot matter with two caches).
2. **The L2 on its own**, against a reference memory, with a DDR model that is slow, reorders and stalls.
3. **The full processor in simulation**: the RISC-V ISA tests, and our two-core coherence and CA programs. Negative controls replace `cread` with plain loads; those must fail, and do.
4. **The exact FPGA design in simulation**, then **the board**: the same tests, and 1,800 benchmark runs across all our designs, each one checking the data structure at the end.

The final design's simulation matches the board cycle for cycle, which also means anyone can study the system without a board.

## What the results mean
- **Memory:** CA never leaves a removed node waiting (0 in every structure). Hazard pointers keep 20–34, epochs 102–202. This is the paper's main claim, and it holds on real hardware.
- **Under contention:** on the stack and the hash table at 100% updates, CA with `bcafail` is the fastest reclaiming scheme. On the stack it even beats never freeing at all.
- **Read-heavy work:** epochs win. CA pays something on every protected read (4 cycles with `bcafail` against 1 for a plain load), and two cores cannot show the paper's large gains, which come at 16–32 threads.
- **Platform matters:** adding the L2 made everything faster and lowered CA's ratios somewhat (BST from 0.71 to 0.62 of never freeing), but did not change which scheme wins. A simulator and a board agree only when the model of memory is right.

[Results](06_results.md) has the tables.

## Differences from the paper
| | Paper | Us | Effect |
|---|---|---|---|
| Platform | Graphite simulator | real RTL on an FPGA | everything here was actually built |
| Threads | up to 32 | 2 | CA's largest wins are out of reach |
| Cores | simulated cores | in-order CVA6, 50 MHz | compare ratios only |
| L1 lines | 64 B | 16 B | a node is one line; no false sharing |
| Failure check | free flag | `bcafail` (2 cycles after a `cread`) | CA a bit slower on read-heavy work |
| Baselines | hp, he, ibr, qsbr, rcu, none | hp, qsbr, none | |

## Open questions
- Should the tag set survive interrupts and context switches, so CA can be used under an OS? Today a trap simply revokes access.
- How does CA behave with 4 or more cores? That needs smaller caches or a bigger FPGA.
- Could `bcafail` be avoided altogether, for example by a `cread` that writes its failure into a register?

[PLAN.md](../PLAN.md) lists these as open tasks.
