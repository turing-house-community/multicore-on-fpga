# 8. The project in depth: what we did, how, and why

This is the long version: everything needed to explain the project to an advisor or a review panel, and to answer their follow-up questions. It assumes basic computer architecture (pipelines, caches) and goes into the exact mechanisms. Every claim refers to the code (paths under `cva6/`) or to measured data (under `results/`).

The shorter guides cover the same ground at a gentler pace: [background](01_background.md), [design](02_design.md), [results](06_results.md), [challenges](07_challenges.md).

**Contents**
1. [The project in one paragraph](#1-the-project-in-one-paragraph)
2. [The problem: safe memory reclamation](#2-the-problem-safe-memory-reclamation)
3. [Conditional Access: the idea and why it is safe](#3-conditional-access-the-idea-and-why-it-is-safe)
4. [The starting point: CVA6](#4-the-starting-point-cva6)
5. [MSI coherence: what we built and how it works](#5-msi-coherence-what-we-built-and-how-it-works)
6. [Atomics inside the L1](#6-atomics-inside-the-l1)
7. [The CA unit and its pipeline integration](#7-the-ca-unit-and-its-pipeline-integration)
8. [The FPGA system on the KR260](#8-the-fpga-system-on-the-kr260)
9. [Verification: how we know it is correct](#9-verification-how-we-know-it-is-correct)
10. [Evaluation: benchmarks and what the numbers mean](#10-evaluation-benchmarks-and-what-the-numbers-mean)
11. [Differences from the paper, and limitations](#11-differences-from-the-paper-and-limitations)
12. [What is our contribution](#12-what-is-our-contribution)
13. [Questions we expect, with answers](#13-questions-we-expect-with-answers)
14. [Glossary](#14-glossary)

---

## 1. The project in one paragraph

Singh, Brown and Spear proposed **Conditional Access (CA)**: four new instructions that let lock-free data structures free memory *immediately* and safely, by reusing the invalidations the cache-coherence protocol already produces. They evaluated it only in a simulator. We implemented it in **real hardware**: we took the open-source single-core RISC-V processor **CVA6**, built a **two-core** system with private write-back L1 data caches kept consistent by an **MSI coherence protocol we designed** (on a small snooping bus), added the **four CA instructions** to the pipeline and a **CA unit** to each cache, verified it (randomized testbenches with reference models, bug injection, ISA test suites, on-board tests), put it on an **AMD KR260 FPGA** at 50 MHz, and ran the paper's benchmarks on the board. The paper's main claims hold on real hardware: CA frees every node immediately (0 unfreed nodes) and is the fastest scheme under high contention (1.33× the leaky baseline on a stack). It is slower than the paper suggests on read-heavy work, because reading the failure flag is expensive in CVA6; we measured how expensive, and explain where the cost most likely comes from.

---

## 2. The problem: safe memory reclamation

### 2.1 Lock-free data structures
In a lock-free (optimistic) data structure, readers traverse shared nodes **without locks**. Writers insert and remove nodes concurrently, usually with atomic instructions or fine-grained locks on just the nodes they change. This scales well, because readers never block each other or writers.

### 2.2 The use-after-free
Take a sorted linked list `A → N → B`.
1. Core 0, searching, has loaded the pointer to `N` and is about to read `N->key`.
2. Core 1 deletes `N`: it sets `A->next = B` and calls `free(N)`. The memory of `N` goes back to the allocator and may immediately be reused for some other node.
3. Core 0 now reads `N->key` and `N->next`. It reads freed memory: garbage, a pointer into a different structure, or a crash.

Core 1 had no way to know that core 0 still held a pointer to `N`. **The question is when it is safe to call `free(N)`.** That is the *safe memory reclamation* problem.

### 2.3 Existing software solutions and their costs
| Scheme | Mechanism | Cost |
|---|---|---|
| **Hazard pointers (HP)** (Michael 2004) | Before dereferencing a pointer, a reader writes it to its own "hazard" slot, issues a **memory fence**, and re-checks that the pointer is still valid. A remover puts nodes in a retired list and periodically scans all hazard slots; a node is freed only when no slot names it. | A fence and a re-validation **on every pointer read**: traversals get slow. Retired nodes wait for the next scan. |
| **Epoch-based / quiescent-state (EBR, QSBR, RCU)** (Fraser 2004, Hart et al. 2007) | Removed nodes go into a limbo list tagged with the current epoch. Each thread announces when it is between operations (quiescent). A node is freed once every thread has passed a quiescent point since it was removed. | Reads are nearly free, but **memory accumulates**: nodes wait for the slowest thread. One stalled thread blocks all freeing. |
| **Leaky (`none`)** | Never free. | Fastest, unbounded memory. Used as an upper bound on speed. |
| Hardware transactional memory | Run the traversal as a transaction. | Being disabled on modern CPUs (security and errata), and aborts under contention. |

The common issue is **delayed reclamation**: memory is freed some time after removal, and each scheme trades speed (HP) against memory (EBR). The paper's goal is to get both: immediate freeing **and** near-sequential read cost.

---

## 3. Conditional Access: the idea and why it is safe

### 3.1 The observation
For core 1 to safely unlink and reuse `N`, it must **write** to memory that core 0 depends on (at least `A->next`, typically also a "deleted" mark in `N`). In a coherent multicore, a write to a line requires **exclusive ownership** (M state), so the coherence protocol **invalidates every other copy** of that line, including core 0's. The hardware therefore already knows, at the exact moment, that core 0's view has become stale. CA exposes that knowledge to software.

### 3.2 The four instructions (paper semantics)
Each core has:
- a **tagSet**: the cache lines it is watching (8 in our implementation);
- an **accessRevokedBit**: set when any watched line is invalidated or lost;
- a **failure flag (CAFAIL)**: set when a CA instruction fails.

| Instruction | Semantics |
|---|---|
| `cread rd, off(rs1)` | If access is revoked: fail (CAFAIL = 1, rd = 0). Otherwise load the word **and add its line to the tagSet**. |
| `cwrite rs2, off(rs1)` | If the line is in the tagSet and access is not revoked: store, as **one atomic step** with the check. Otherwise fail, store nothing. |
| `untagOne rs1` | Remove one line from the tagSet. |
| `untagAll` | Empty the tagSet, clear accessRevokedBit and CAFAIL. |

Access is revoked when a watched line is **written by another core** (an invalidation), **evicted** from the cache (the cache would no longer see invalidations for it), when the tagSet **overflows**, or on an **interrupt/trap**. A remote **read** does not revoke (it only downgrades the line to shared).

### 3.3 Why this makes immediate freeing safe: hand-over-hand tagging
The lazy-list search with CA (`bench.c`, `list_search`, after the paper's Algorithm 3):
```c
untagAll();
pred = head;
curr = cread(&pred->next);   if (cafail()) retry;   // pred's line tagged
ck   = cread(&curr->key);    if (cafail()) retry;   // curr's line tagged
while (ck < key) {
    untagOne(pred);                                   // keep only pred and curr tagged
    pred = curr;
    curr = cread(&pred->next);  if (cafail()) retry;
    ck   = cread(&curr->key);   if (cafail()) retry;
}
```
**The safety argument.** Suppose core 0 has read `curr = pred->next` (so `pred` is tagged) and is about to `cread(&curr->key)`. For core 1 to free `curr`, it must first unlink it, i.e. write `pred->next`. That write needs `pred`'s line in M, so it invalidates core 0's copy of `pred`, which is tagged, so core 0's accessRevokedBit is set. Core 0's next `cread` (of `curr->key`) therefore **fails**, and core 0 never uses the value. More generally: **a node can only be freed after a write to a line the reader has tagged, and every value the reader uses came from a cread that succeeded after it tagged its predecessor.** So no value from freed memory is ever acted on, and core 1 may call `free()` immediately after unlinking.

Updates use the same mechanism. The **CA try-lock** (paper, Algorithm 2; `bench.c`, `ca_trylock`):
```c
v = cread(&node->lock);           // tag the node, read the lock word
if (cafail() || v) return FAIL;   // revoked, or held
cwrite(&node->lock, 1);           // take it only if nobody touched the node since
return !cafail();
```
Once a thread holds the locks on `pred` and `curr` (and has validated them), those nodes cannot be freed by anyone else (a remover would need the lock), so the update itself uses plain loads and stores. The deleting thread sets `curr->mark = 1`, writes `pred->next = curr->next`, releases, and **frees `curr` right away**.

The **Treiber stack** with CA (Algorithm 1) needs no locks at all: `pop` is `t = cread(&top); nx = cread(&t->next); cwrite(&top, nx)`, and the `cwrite` succeeds only if nobody changed `top` (or freed `t`) in between, which is exactly what a compare-and-swap would check, plus protection of the `t->next` read.

### 3.4 What CA needs from the hardware
1. A coherence protocol that **invalidates** remote copies on a write, and tells the CA unit when that happens.
2. A per-core **tagSet** next to the L1, checked on every `cread`/`cwrite`.
3. An **atomic** `cwrite` (check and store indivisible).
4. Correct behaviour in a **speculative pipeline** (the paper's simulator model ignores this; we had to design it).

CVA6 had (1) only for single-core use (no coherence at all) and none of (2)–(4). That is what we built.

---

## 4. The starting point: CVA6

**CVA6** (OpenHW Group; formerly Ariane, ETH Zürich) is an open-source, application-class RISC-V core: 6 stages, single-issue, in-order issue with out-of-order write-back, a scoreboard, MMU, M/S/U privilege. It boots Linux on FPGA boards. It is configured at elaboration time by a config package.

Our configuration, **`cv32a6_imac_sv32_wb`** (new file `core/include/cv32a6_imac_sv32_wb_config_pkg.sv`):

| Parameter | Value |
|---|---|
| ISA | RV32IMAC + Zicsr (no floating point) |
| Data cache | `std_nbdcache` (write-back), 32 KiB, 8-way, 16-byte lines (256 sets) |
| Instruction cache | 16 KiB, 4-way, 16-byte lines |
| Scoreboard | 8 entries (so `trans_id` is 3 bits) |
| Commit ports | 2 |
| MMU | present (Sv32), unused in our bare-metal programs |

**Why CVA6:** open source, actively maintained, realistic pipeline (speculation, commit stage, store buffer), and it already runs on Xilinx FPGAs. **Why its write-back cache:** CVA6 has three D-caches. The write-through one never holds dirty, exclusively owned lines, so it cannot implement MSI's M state. The HPDcache is large and complex. `std_nbdcache` is a write-back, set-associative, non-blocking cache with a miss handler that we could extend.

**The upstream base** is commit `81245a47` of `openhwgroup/cva6`; see [code_map.md](code_map.md) for every file we changed.

---

## 5. MSI coherence: what we built and how it works

Upstream CVA6 is single-core: its cache has no notion of another cache. Everything in this section is new.

### 5.1 States and their encoding
| State | Meaning | Encoding in the status array |
|---|---|---|
| **M** (Modified) | only copy, may be newer than memory; reads and writes allowed | `valid = 1, owned = 1` (`dirty` = written since fill) |
| **S** (Shared) | clean copy, others may have it too; reads only | `valid = 1, owned = 0` (never dirty) |
| **I** (Invalid) | not present | `valid = 0` |

We added one bit per way, **`owned`**, to the status SRAM of `std_nbdcache` (`core/cache_subsystem/std_nbdcache.sv`). `dirty` already existed.

### 5.2 Bus requests
| Request | Issued by | Effect on the other cache |
|---|---|---|
| **GetS** | load miss | if it has the line in M: write it back to memory, then M → S |
| **GetM** | store miss, store to an S line (upgrade), AMO, LR/SC, `cwrite` | write back if dirty, then → I. **This is the event that revokes CA access.** |
| **PutM** | write-back of a dirty line on eviction or flush | none (the writer owns the line, so nobody else has it) |

### 5.3 The coherence bus (`core/cache_subsystem/cc_bus.sv`, ~150 lines)
An **atomic broadcast bus**: at most **one transaction (a "tenure") exists at a time**. Its state machine:

| State | What happens |
|---|---|
| `IDLE` | Pick a requesting cache, round-robin starting after the last owner. A PutM goes straight to GRANT (nothing to snoop). |
| `SNOOP` | Present the request to every other cache as a snoop (`snoop_o`). Wait until each has **accepted** (`snoop_ready_i`) and **acknowledged** (`snoop_ack_i`). An ack means "my copy is downgraded or invalidated, and any dirty data is already in memory". |
| `GRANT` | Grant the requester (`gnt_o`). |
| `TENURE` | The requester accesses memory over its **own AXI port**, then pulses `done_i`. |

A complete GetS miss to a line the other core holds dirty, as a timeline:
```
core 0 miss handler        cc_bus                core 1 miss handler          memory
BUS_REQ: cc_req(GetS,X) -> IDLE: pick core 0
                           SNOOP: snoop(GetS,X) -> SNOOP_REQ / SNOOP_CHECK: X is M, dirty
                                                   SNOOP_WB: write X back --------> write
                                                   SNOOP_WB_WAIT: wait for B response <-- B
                                                   SNOOP_UPDATE: M -> S, ack
                           GRANT  <-------------------------------------------- ack
MISS / REQ_CACHELINE: read X ------------------------------------------------> read
SAVE_CACHELINE: fill X in S <------------------------------------------------- data
cc_done ----------------> TENURE -> IDLE
```
**Key design choice: no cache-to-cache data transfer.** The snooped cache writes dirty data back to DDR and acknowledges **only after the AXI write response (B)**. When the requester is granted, memory is guaranteed up to date, so it simply reads memory. This keeps the bus tiny (no data path) and needs no L2, at the price of a slower dirty miss (measured: 97 vs 54 cycles, [section 10.6](#106-coherence-cost-micro_cohc-two-cores)).

### 5.4 The miss handler (`core/cache_subsystem/miss_handler.sv`)
This is the largest change (~500 lines). New states (in the `state_e` enum):

| State | Purpose |
|---|---|
| `BUS_REQ` | wait for a tenure before serving a miss (MSHR) |
| `FLUSH_BUS_REQ`, `FLUSH_WB_WAIT` | tenure for writing back a dirty line during a flush, held until the B response |
| `SNOOP_REQ`, `SNOOP_CHECK`, `SNOOP_WB`, `SNOOP_WB_WAIT`, `SNOOP_UPDATE` | serve a snoop: read the set, look up the line, write back if dirty, wait for B, downgrade/invalidate and ack |
| `AMO_BUS_REQ`, `AMO_LOOKUP`, `AMO_EXEC` | atomics and `cwrite` executed in the L1 under a GetM tenure |
| `LR_HOLD` | keep the LR's tenure for its SC (forward progress) |

**Flows:**
- **Load miss:** `BUS_REQ` (GetS) → granted → `MISS` → evict a victim if needed (dirty victim: written back within the same tenure) → `REQ_CACHELINE` → fill in **S**.
- **Store miss:** same with GetM; fill in **M**.
- **Store to an S line (upgrade):** `cache_ctrl.sv` treats a store hit on a non-owned line as a **miss**. The miss handler takes a GetM tenure (invalidating the other copy) and **refills the line in place** from memory, in M. The refill avoids having the same tag twice in a set. Consequence: an upgrade costs about as much as a miss (measured 49.5 vs 53.7 cycles). An upgrade without data would be a valid optimization.
- **Eviction of a dirty line:** write-back under the current tenure. An evicted **tagged** line revokes CA access (`ca_inval_valid_o`).
- **Snoop:** see above. A GetM snoop that hits a line also invalidates the LR reservation if it is on that line, and tells the CA unit (`ca_snoop_inval_valid_o`).

### 5.5 Correctness invariants
1. **Single-writer / multiple-reader (SWMR):** at any time, a line is either M in exactly one cache (and I elsewhere), or S/I everywhere. Guaranteed because every transition to M happens under a GetM tenure that first invalidated all other copies, and tenures are serialized.
2. **Data-value invariant:** a read returns the most recent write. Guaranteed because the only way to get a line is a tenure, and at the grant memory is up to date (dirty copies were written back before the ack).
3. Both are checked **every cycle** by the two-cache testbench ([section 9](#9-verification-how-we-know-it-is-correct)).

### 5.6 Deadlock freedom
The classic deadlock: cache A holds the bus and waits for B's snoop answer, while B is stuck waiting for the bus. Our rule: **a cache can always answer a snoop without needing the bus.** In code (`miss_handler.sv`):
```systemverilog
assign snoop_ready_o = !bus_held_q &&
    (state_q inside {IDLE, BUS_REQ, FLUSH_BUS_REQ, FLUSH_REQ_STATUS, AMO_BUS_REQ});
```
Snoops are accepted only when the cache holds **no tenure** and is in a state where nothing is half-done: idle, or merely *waiting* for the bus. In those states the snoop path (read set, maybe write back, update, ack) uses only the cache's own SRAM and AXI port. Since the bus only snoops caches that do not own the tenure, every snoop is eventually accepted and completes, so every tenure completes, so the bus always makes progress. After serving a snoop, the cache returns to the waiting state and re-reads the set (a snoop may have changed the line it was about to fetch).

### 5.7 Races we handled
| Race | Resolution |
|---|---|
| A snoop arrives while our own miss to the **same line** waits for the bus | after the grant, the miss re-reads the tags (`MISS` state) rather than trusting what it saw before |
| A store is between its tag look-up and its SRAM write when a snoop takes the line | a snoop on a set holds off stores to that set (stores are look-up-then-write, not atomic) |
| A store to an S line: while the upgrade is in flight, a **load** could still hit the old S copy after the other core wrote a newer value (**found by our testbench**) | a load may not hit the line the miss unit is fetching (`mshr_addr_matches_i` in `cache_ctrl.sv`) |
| Two cores each doing LR/SC on one line invalidate each other's reservations forever: **livelock** (**found by our testbench**) | after an LR, the cache keeps its tenure up to `LrHoldCycles = 64` cycles waiting for the matching SC ([section 6](#6-atomics-inside-the-l1)) |

### 5.8 Snooping or directory?
The paper's simulator used a **directory** protocol because it modelled up to 32 cores. We use **snooping (broadcast)**:
- With **two cores** there is exactly one other cache, so a broadcast reaches exactly the cache a directory would pick. A directory would add per-line sharer state (memory and LUTs), extra protocol states and races, and no benefit.
- CA is **protocol-agnostic**: it only needs the "another core is writing this line" event. A GetM snoop gives it here; a directory invalidation gives it in the paper.
- What would change with a directory: latencies (an extra hop through the directory), and scalability. For 4+ cores, a directory or a scalable interconnect becomes worthwhile ([PLAN.md](../PLAN.md)).

---

## 6. Atomics inside the L1

Upstream `std_nbdcache` executes AMOs by **flushing the whole cache** and sending the AMO to memory (AXI atomics). With two caches that is both slow and wrong: the other cache could hold a stale or dirty copy. We moved cacheable AMOs and LR/SC **into the L1**:
1. `AMO_BUS_REQ`: take a **GetM tenure** for the line (invalidating the other copy).
2. `AMO_LOOKUP` / `AMO_EXEC`: if the line is not present in M, fetch it in M under the same tenure; then do the read-modify-write in one step with `amo_alu.sv` (an upstream module we now use here).
3. Release the tenure.

Because **no snoop can arrive while a cache holds a tenure** (snoops are only accepted without one), the look-up and the write in `AMO_EXEC` are atomic with respect to the other core.

**LR/SC:** LR records a reservation (line address). A GetM snoop on that line, an eviction of it, a flush of its set, or any SC clears it. SC succeeds only if the reservation is still valid. **Livelock fix:** two cores running LR/SC loops on the same line would steal the line from each other between LR and SC forever. After an LR, the cache stays in `LR_HOLD` and **keeps its tenure** for up to 64 cycles, during which only the SC to the reserved line may run. This guarantees that an LR followed promptly by its SC succeeds (the RISC-V spec's forward-progress guarantee for constrained LR/SC loops).

**`cwrite` reuses this path** as a new AMO type, `AMO_CWRITE` (encoding `4'b1110` in `ariane_pkg.sv`). That is what makes it atomic ([section 7.4](#74-cwrite-atomic-at-commit)).

---

## 7. The CA unit and its pipeline integration

### 7.1 Instruction encodings and decoding (`core/decoder.sv`)
| Instruction | Opcode | funct3 | Format | Functional unit / op |
|---|---|---|---|---|
| `cread rd, imm(rs1)` | custom-0 `0x0B` | 0 | I | LOAD / `CREAD` |
| `cwrite rs2, imm(rs1)` | custom-0 `0x0B` | 1 | S | STORE / `CWRITE` (rd forced to 0: bits 11:7 are an immediate in S-format) |
| `untagOne rs1` | custom-1 `0x2B` | 0 | I | LOAD / `UNTAG_ONE` |
| `untagAll` | custom-1 `0x2B` | 1 | I | LOAD / `UNTAG_ALL` |

Custom-0/1 are opcode spaces the RISC-V spec reserves for extensions, so no standard instruction is displaced. Other funct3 values stay illegal. In software we emit them with `.insn` (assembler) or inline assembly wrappers (`bench.c`). Accesses are 32-bit words with alignment checks.

**The failure flag** is a new **read-only CSR `0xCC0`** (`CSR_CAFAIL`, `csr_regfile.sv`): bit 0 = CAFAIL, bit 1 = accessRevokedBit. Software checks `csrr t0, 0xCC0; andi t0, t0, 1`. RISC-V has no condition-flags register, so a CSR was the natural ISA-visible place. Writes to it are illegal; `untagAll` is the only way to clear it.

### 7.2 The CA unit (`core/cache_subsystem/ca_tag_set.sv`, ~240 lines)
One per core, inside `std_nbdcache`. State:
| Structure | Size | Purpose |
|---|---|---|
| **tagSet** | 8 entries × line address + valid | lines tagged by **committed** creads |
| **pending table** | 8 entries (one per scoreboard `trans_id`) × {op, line address, invalidated, failed} | CA ops seen by the cache but **not yet committed** |
| `revoked` | 1 bit | accessRevokedBit |
| `cafail` | 1 bit | CAFAIL |

All of it is flip-flops and comparators, **no block RAM**: about 1,100 LUTs and 540 registers per core in the implemented design (4.5% of a core).

### 7.3 Speculation: record at issue, apply at commit
CVA6 issues loads speculatively: a `cread` may execute in the cache and then be **squashed** (mispredicted branch, exception in an older instruction). If a squashed `cread` had tagged a line, the program would later see spurious failures; worse, if a squashed `untagAll` had cleared the revoked bit, a real revocation would be lost. So CA state changes **only at commit**:

1. **Issue.** When a CA op reaches the cache with its physical address (`cache_ctrl.sv`, `ca_issue_o`), it is written into the pending table at index `trans_id`, line-aligned.
2. **Answer.** A `cread` is answered like a load, but checked at that moment: if `cread_revoked` is true, it returns **0** and is marked *failed* in the pending table. `untagOne`/`untagAll` do no memory access at all and return immediately.
3. **While pending:** if the line of a pending cread is invalidated (snoop or eviction), its entry is marked *invalidated*.
4. **Commit** (`ca_commit_valid_i/ca_commit_id_i`, driven from `cva6.sv` for each commit port using the instruction's `trans_id`, in program order):
   - committed failed cread → set CAFAIL;
   - committed cread whose line was invalidated while pending → set revoked (the line went away between access and commit);
   - committed successful cread → add its line to the tagSet; if the tagSet is full → set revoked (**overflow**);
   - `untagOne` → remove the line; `untagAll` → clear tagSet, revoked, CAFAIL.
5. **Flush** (`ca_flush_i`, on any pipeline flush): drop all pending entries.

**When a cread fails** (`p_status` in `ca_tag_set.sv`):
```systemverilog
cread_revoked_o = revoked_q || tag_hit_now || pending_lost;
```
- `revoked_q`: access already revoked;
- `tag_hit_now`: a tagged line is being invalidated **in this very cycle**;
- `pending_lost`: an **older, still uncommitted** cread already lost its line.

**Two ordering rules the paper did not need** (its model has no speculation):
1. **untagAll hold-off.** While an `untagAll` is pending (issued, not committed), the cache accepts **no new CA op** (`ca_block_i` → `ca_accept_ok` in `cache_ctrl.sv`). Without this, the standard retry loop `untagAll; cread ...` would have the `cread` checked against the *old* revoked bit (the `untagAll` that clears it has not committed yet), fail, retry, and fail forever.
2. **Pending-lost rule.** Program: `cread A; cread B`. Both execute before either commits. If A's line is invalidated after A executed but before B executes, then B must fail: when A commits it will set revoked, and B's data may already come from a reclaimed node (the remover's write to A may have been the unlink of B). Hence `pending_lost`.

### 7.4 `cwrite`: atomic at commit
`cwrite` must check "tagged and not revoked" **and** store, with no window in between. In the original write-through prototype the decision was made early and the store happened later, so another core could slip in. Our design (`store_unit.sv`, `commit_stage.sv`, `miss_handler.sv`):
1. `cwrite` is routed to the **AMO path**: it waits until it is the oldest instruction and the store buffer has drained, like `amoswap`.
2. In `IDLE`, the miss handler checks `ca_cwrite_allowed` (line tagged, access not revoked). If not allowed: **fail immediately, without touching the bus**, set CAFAIL.
3. Otherwise take a **GetM tenure** (`AMO_BUS_REQ`), fetching the line in M if needed.
4. In `AMO_EXEC`, **check again**: while this core waited for its tenure, the other core may have held the bus and written a tagged line, which revoked access. Then write. While the tenure is held no snoop can arrive, so the check and the write are atomic.

The re-check in step 4 matters: injected bug c4 (remove it) was caught by the testbench in 26 of 40 runs.

### 7.5 Revocation sources and where they come from
| Source | Signal | Origin |
|---|---|---|
| another core's write | `snoop_invalidate_valid_i` | `miss_handler.sv`, `SNOOP_UPDATE` on a GetM |
| eviction of a tagged line, flush | `invalidate_valid_i` (+ `invalidate_all_i` for a flush) | `miss_handler.sv`, `MISS_REPL` and flush states |
| tagSet overflow | internal | commit of a cread with a full tagSet |
| trap/interrupt | `invalidate_all_i` via `ca_trap_i` | `cva6.sv` (`ex_commit.valid`), **registered one cycle** in `std_nbdcache.sv` |

**Why eviction must revoke:** a line that is no longer in the cache will not be snooped, so a later remote write to it would go unnoticed. Revoking on eviction is the conservative, correct choice (the paper does the same). Consequence: CA's watch capacity is bounded by cache associativity; we see this as ~25 failures per BST run even with one thread ([section 10.4](#104-throughput-results-and-their-explanation)).

**Why trap revocation is delayed one cycle:** originally a trap revoked in the same cycle. The commit stage decides about traps using the `cwrite`'s acknowledge, which depends on `cwrite_allowed`, which depended on the revoked bit, which depended on the trap: a **combinational loop** that Vivado rejected (DRC LUTLP-1). Registering the trap breaks it. This is safe: a trap flushes the pipeline, so no tagged operation can commit in the cycle in between.

### 7.6 Remote reads do not revoke
A GetS snoop downgrades our M line to S but leaves it valid, so it does not revoke (as in the paper). Bug c10 ("GetS revokes") would cause spurious failures; the testbench's precision check (every failure must have a cause) catches it 40/40.

---

## 8. The FPGA system on the KR260

**Board:** AMD Kria KR260, K26 SOM, Zynq UltraScale+ (`xck26-sfvc784-2LV-c`): ARM processing system (PS) with 4 GB DDR4, plus programmable logic (PL) with 117,120 LUTs, 234,240 flip-flops, 144 BRAM36.

**Top level** (`corev_apu/fpga/kr260/src/cva6_kr260_top.sv`):
- two `cva6` instances (`cv32a6_imac_sv32_wb`, parameter `CoherentL1 = 1`), hart IDs 0 and 1, both booting at `0x8000_0000`;
- one `cc_bus` connecting their snoop/tenure ports;
- one `axi_cut` (register slice) per core, then an `axi_mux` merging the two AXI masters (the cut breaks a combinational loop between the two cores' arbiters, see [challenges](07_challenges.md));
- address remap: core `0x8000_0000–0xBFFF_FFFF` (cacheable) → PS DDR `0x4000_0000`; core `0xC000_0000` → mailbox (uncached).

**Block design** (`scripts/kr260_bd.tcl`): Zynq PS with the KR260 preset; the cores' DDR traffic enters through `S_AXI_HP0_FPD`; the PS reaches an 8 KiB true-dual-port **mailbox BRAM** and a **run GPIO** via `M_AXI_HPM0_FPD`; PL clock 50 MHz.

**No OS, no SD card.** A run (`scripts/run_test.tcl` via `xsdb` over JTAG): program the PL, initialize the PS (`psu_init` from the `.xsa`), hold the cores (run = 0), clear the mailbox, write the seed to mailbox word 2, copy the program image to DDR, set run = 1, poll `tohost` (mailbox word 0), print the result and mailbox words 16+.

**Why the mailbox:** with write-back caches a result stored to DDR may sit in a core's cache indefinitely; the PS reading DDR would not see it. The mailbox is outside the cacheable range, so stores go straight out. `sw/link_kr260.ld` places `tohost` there.

**Implementation results** (`prebuilt/reports/`):
| Resource | Used | Of | % |
|---|---|---|---|
| LUTs | 58,853 | 117,120 | 50.3 |
| Flip-flops | 32,058 | 234,240 | 13.7 |
| BRAM36 | 74 | 144 | 51.4 |
| DSP | 8 | 1,248 | 0.6 |

Per core about 25K LUTs and 41 BRAM36. Timing met at 50 MHz with **WNS +2.39 ns** (about 57 MHz would be possible without further work). Block RAM is the limiting resource: a third and fourth core with these caches would not fit.

---

## 9. Verification: how we know it is correct

We verified bottom-up, and each level was passing before we moved to the next.

### 9.1 Level 1: one cache (`core/cache_subsystem/test/std_nbdcache_msi_tb.sv`)
The testbench drives one `std_nbdcache` with random loads, stores and **snoops** (playing the other cache and the bus), against a byte-accurate reference memory and an AXI memory model. It checks every load value, the line states after each snoop, and that dirty data is written back before an ack. **300/300 seeds pass.**

### 9.2 Level 2: two caches + bus + CA (`std_nbdcache_2core_tb.sv`)
Two caches, the real `cc_bus`, the CA units, and the testbench playing both pipelines (including the commit stage: it commits, squashes and raises traps).
- **Every cycle:** SWMR on every line in use (millions of checks per run: e.g. "SWMR checks=3072550").
- **Loads:** checked against the history of written values (a load must return a value that was current at some point during its execution).
- **AMOs:** exact; two AMOs on a counter never return the same old value.
- **Liveness:** deadlock/timeout and fairness watchdogs.
- **CA reference model of the paper's rules**, checked after every op:
  - S1: a successful cread ⇒ no tagged line was invalidated or written by the other core since tagging;
  - S2: a successful cwrite targets a tagged line under the same condition; a failed cwrite wrote nothing (final memory compare);
  - S3: cread values are linearizable;
  - S4: CAFAIL is set after a committed failure and cleared by untagAll;
  - **precision:** every failure must have a revoking event (no spurious failures).
- **11 directed CA tests:** basic success; remote write revokes; remote read does not; cwrite to an untagged line; untagOne; overflow; eviction; trap (with and without tags); squashed cread; untagAll hold-off; older pending cread lost.
- **400/400 runs pass** (200 seeds × normal and `+hot`, where both cores fight over two lines).

### 9.3 Is the testbench any good? Bug injection
We injected bugs into the RTL one at a time and checked that the testbenches fail (40 seeds each). **26 of 27 detected:**

| Group | Mutants | Detected |
|---|---|---|
| One cache (m1–m9): snoop skips dirty write-back; ack before B response; GetM does not invalidate; snoop does not hold off stores; no in-place refill on upgrade; stale-hit bug re-introduced; store without ownership; flush releases bus before B response; GetS fill marked M | 9 | 9 (m8 was missed at first; we added flush-race tests until it was caught) |
| Two caches (p1–p7): grant before snoop acks; no snoop on GetS; SC ignores reservation; GetM keeps reservation; no LR hold (livelock); AMO without the bus; no round-robin | 7 | 6 |
| CA (c1–c11): snoop does not revoke; eviction does not revoke; cwrite ignores tag; cwrite without re-check; no untagAll hold-off; no pending-lost rule; failed cread returns data; trap does not revoke; untagAll keeps revoked; GetS revokes; overflow does not revoke | 11 | 11 |

The one miss, **p7 (no round-robin)**, is undetectable with two caches *by construction*: after `done`, the bus always spends a cycle in IDLE, by which time the other waiting cache is the only requester, so it is picked anyway. The fairness monitor remains as a guard for more cores.

### 9.4 Level 3: the full processor
CVA6's Verilator testharness with our config, one core and two cores (`defines=CVA6_2CORE`):
- **RISC-V ISA tests** (rv32ui, um, ua, uc, mi, si; p environment): **72/73 pass**, including all 10 atomic tests through the new in-L1 path. The failure, `rv32mi-p-breakpoint`, is disabled upstream for 32-bit configs too (needs debug triggers).
- **`msi_2core.S`** (both harts): `amoadd` counter = 2N, LR/SC counter = 2N, turn-taking ping-pong with plain loads/stores = 2N, interleaved false-sharing array exact, message passing with fences.
- **`ca_2core.S`**: every instruction and the CSR; the cwrite immediate (a decoder bug we fixed); trap revocation; an illegal CSR write; **reclamation**: hart 1 unlinks and poisons nodes while hart 0 traverses with creads, and a successful cread never sees a poisoned node; **the paper's try-lock** guarding a plain counter, which must reach exactly 2N.

### 9.5 Negative controls: proving the tests can fail
A test that always passes proves nothing. Variants of `ca_2core.S` in `verif/tests/custom/ca_2core/controls/`:
| Variant | Expected and observed |
|---|---|
| plain `lw` instead of `cread` in the reader | **fails** (code 30): reads a reclaimed node |
| plain `sw` instead of `cwrite` in the try-lock | **fails** (code 32): two threads in the lock, counter wrong |
| additionally require at least one revoked cread | **passes**: revocations really happen during the run |

So the reclamation test genuinely detects use-after-free, and CA genuinely prevents it.

### 9.6 Level 4: the exact FPGA design, then the board
`sim/kr260_bd_wrapper_sim.sv` replaces the Vivado block design with a behavioural model (DDR preloaded from a binary, mailbox, run bit), so Verilator simulates **exactly the RTL that goes into Vivado**. Then on the board: `msi_2core` and `ca_2core` pass 10/10 runs each, the controls behave as above, 72/73 ISA tests pass. **No difference between board and simulation was found.** All 288 benchmark runs also validate their data structure at the end.

---

## 10. Evaluation: benchmarks and what the numbers mean

### 10.1 Setup (after the paper's section 6)
| | |
|---|---|
| Data structures | lazy list (1K keys), external BST (10K keys), Treiber stack, hash table (128 buckets of lazy lists) |
| Schemes | `none` (leaky), `ca`, `hp` (hazard pointers, scan every 30 removals), `qsbr` (epoch advanced every 150 allocations): the paper's parameters |
| Workload | 0 / 10 / 100% updates (inserts:deletes 50:50), uniform random keys, 50% prefill, 3,000 ops per thread |
| Threads | 1, 2 |
| Seeds | 1, 2, 3 (spread between seeds is small; `results/summary.csv`, `mops_spread_pct`) |
| Total | 96 configurations × 3 = **288 runs**, all valid |

**Metric:** throughput = total operations / the slowest thread's `mcycle` time at 50 MHz. **Unreclaimed** = nodes removed but not yet freed at the end of the run. Nodes are exactly one 16-byte line (key, next, lock, mark), so there is no false sharing between nodes. `free_node` writes the node (`key = KEY_MIN`) and pushes it on a per-thread free list, so freed memory really is reused and poisoned.

### 10.2 Implementation notes that matter for interpretation
- **CA_CHECK** after every cread is `csrr 0xCC0; andi 1; bnez` (the paper models a free flag register).
- `none`/`hp`/`qsbr` use the standard lazy list with spin locks, and `__atomic_compare_exchange_n` for the stack, which compiles to an **LR/SC loop** on RV32IMA.
- HP publishes each pointer with a store + `fence rw,rw` + re-validation.

### 10.3 Memory: the headline result
Removed-but-unfreed nodes at the end (2 threads, 100% updates): `ca` **0** in every structure, `hp` 19–34, `qsbr` 102–198, `none` 1,489–3,028. This is the paper's central claim, reproduced on hardware: **CA has the memory footprint of a sequential structure.**

### 10.4 Throughput results and their explanation
Relative to `none`, 2 threads:

| | read-only | 100% updates |
|---|---|---|
| list: ca / hp / qsbr | 0.34 / 0.25 / 1.00 | 0.43 / 0.33 / 1.00 |
| BST | 0.64 / 0.56 / 1.00 | 0.78 / 0.65 / 0.90 |
| stack | 0.37 / 0.50 / 0.92 | **1.33** / 1.09 / 1.05 |
| hash | 0.49 / 0.48 / 0.99 | **0.98** / 0.85 / 0.99 |

**Read-heavy: CA is slower than QSBR (as in the paper), by more than in the paper.** Root cause, measured with `micro.c`: a `cread` costs 2 cycles (vs. 1 for a load), but **`cread` + check costs 7**. The check is a CSR read, and CVA6 executes CSR instructions **non-speculatively, at commit**. A `csrr` alone costs 1 cycle (nothing older is in flight), but right after a `cread` it has to wait until that load has completed and committed before it executes, and younger instructions wait behind it: the check serializes the pipeline at every hop. (This is our explanation of the measured 7 cycles; we did not instrument the pipeline to break it down.) A list hop has two creads, so ~14 cycles of CA overhead per node versus ~2 for plain loads; the list (long traversals) suffers most, the BST (short paths) least. QSBR's read path is plain loads, so it matches `none`. **HP is even slower** than CA on the list/BST/hash, because each hop pays a store + fence (6 cycles) + re-validation.

**High contention: CA wins.** On the stack at 100% updates with 2 threads, CA reaches 1.33× `none` (HP 1.09×, QSBR 1.05×). Going from 1 to 2 threads, `none` drops from 0.36 to 0.19 Mops/s, while CA drops from 0.40 to 0.25. Both threads hammer one line (`top`). The CAS-based versions retry with LR/SC (24 cycles per attempt, and the LR holds the bus); a CA attempt is `cread` + `cwrite` (17 cycles), and a `cwrite` whose access is already revoked fails **without taking the bus**. We report this as the measured outcome; the per-cause breakdown is our explanation, not separately measured. On the hash table (contention spread over 128 buckets) CA ties `none` and QSBR and beats HP.

**One-thread BST failures** (~25 per run) are **evictions** of tagged lines: a 10K-key tree does not fit a 32 KiB, 8-way L1 with 16-byte lines. This is the paper's associativity caveat, visible on real hardware.

### 10.5 Latency of the primitives (`micro.c`, one core, L1 hits)
| Operation | Cycles |
|---|---|
| plain load / plain store | 1.0 / 1.0 |
| `cread` | 2.0 |
| `cread` + check | 7.0 |
| `csrr 0xCC0` alone | 1.0 |
| `untagOne` / `untagAll` | 0 (hidden) / 4.0 |
| `cread` + `cwrite` (try-lock) | 17 |
| `amoswap.w` (in-L1 AMO) | 14 |
| `lr.w` + `sc.w` | 24 |
| `fence rw,rw` | 6 |

### 10.6 Coherence cost (`micro_coh.c`, two cores)
Hart 0 measures, hart 1 prepares the remote state; every test uses 256 fresh lines; mean of 3 runs, spread under 0.2%; includes ~6.5 cycles loop overhead.
| Access | Cycles/line |
|---|---|
| read miss, no other copy | 53.7 |
| read miss, other core holds it **M** | 96.9 |
| write to S, other core also has S | 50.4 |
| write to S, nobody else has it | 49.5 |
| one-way handoff (ping-pong) | 150.6 |
| read hit | 6.5 |

Interpretation: a dirty remote line costs ~43 extra cycles (≈1.8×) because it goes through DDR (write-back, then read); **invalidating a clean copy costs ~1 cycle**, so the event CA listens to is almost free; an upgrade costs a full refill (our design refetches the line, [5.4](#54-the-miss-handler-corecache_subsystemmiss_handlersv)).

### 10.7 Hardware cost
CA unit: ~1,100 LUTs + ~540 FFs per core, **no BRAM** (4.5% of a core, ~1% of the FPGA). Coherence bus: 48 LUTs + 40 FFs. So the mechanism is cheap; the cost is in the CA_CHECK latency, not in area.

---

## 11. Differences from the paper, and limitations

| | Paper | This work | Effect |
|---|---|---|---|
| Platform | Graphite simulator | real RTL on FPGA | ours includes real pipeline effects |
| Cores | 1–32 | 2 | contention much milder |
| Coherence | directory MSI | snooping MSI, atomic bus, no cache-to-cache transfer | dirty misses slower |
| Lines / L2 | 64 B, 256 KiB shared L2 | 16 B, no L2 | no false sharing between nodes; misses go to DDR |
| Failure check | flag register | CSR read at commit | main source of read-side overhead |
| Baselines | none, rcu, qsbr, ibr, hp, he | none, qsbr, hp | qsbr represents the epoch family |
| Clock | n/a | 50 MHz | absolute throughput low; compare ratios |

**Limitations:** two cores; bare metal only (no OS, no context switches: a trap simply revokes); the second core is not connected to interrupts/debug in the two-core harness; short runs (3K ops/thread, 0.03–0.7 s); the tagSet does not survive traps; eviction-induced failures with large working sets.

---

## 12. What is our contribution

1. **The first hardware implementation of Conditional Access** that we know of, on a real RISC-V pipeline, running real benchmarks.
2. **A coherent multicore CVA6 without OpenPiton**: MSI on CVA6's write-back cache, a deadlock-free atomic snooping bus, AMOs and LR/SC in the L1 with a livelock fix. Useful beyond CA.
3. **Design of CA in a speculative pipeline**: record-at-issue/apply-at-commit, atomic `cwrite` at commit, and two ordering rules (untagAll hold-off, pending-lost) that the paper's model did not need.
4. **A verification methodology with evidence**: reference models of MSI and of the paper's CA rules, 1,100/1,100 randomized runs, 26/27 injected bugs detected, negative controls, board = simulation.
5. **Measured answers to questions a simulator cannot answer**: instruction latencies, coherence costs, area; and the finding that **the cost of reading the failure flag dominates** CA's read-side overhead on a real core, which points to a concrete ISA improvement (branch-on-CA-failure).

---

## 13. Questions we expect, with answers

### About the idea
**Q: Why can't software alone do this?**
Software cannot observe that another core wrote a line it read without paying for it on every read (HP's fence) or deferring frees (epochs). The coherence protocol observes it for free; CA exposes it.

**Q: Is it really safe to free immediately?**
Yes, under the CA discipline: every value is read by a `cread` that was checked after its predecessor was tagged, and freeing a node requires writing a line the reader has tagged (the unlink), which revokes the reader ([3.3](#33-why-this-makes-immediate-freeing-safe-hand-over-hand-tagging)). Our `ca_2core` reclamation test and the `plain_reads` control demonstrate it on hardware.

**Q: What if the freed memory is reused before the reader notices?**
Reuse writes the node (our `free_node` even poisons it), which again invalidates any copy the reader has, and the reader's next `cread` fails. The reader never acts on a value from a failed `cread` (it returns 0, and software checks CAFAIL before use).

**Q: Why does a remote read not revoke?**
A read does not change the data, so the watched values are still valid. Revoking on reads would cause spurious retries (our mutant c10 shows the testbench would flag that).

**Q: Why 8 tags?**
The paper's algorithms need only a few lines tagged at a time (list: pred and curr; BST: gp, p, l; with `untagOne` dropping lines behind). 8 gives headroom. It is a parameter (`DEPTH`); overflow revokes, so correctness never depends on it.

### About the hardware
**Q: Why snooping and not a directory, when the paper used a directory?**
See [5.8](#58-snooping-or-directory): with two cores a broadcast reaches exactly the one other cache; a directory adds state and races for no benefit. CA only needs the invalidation event, which both provide. The paper needed a directory to simulate 32 cores.

**Q: Why not OpenPiton, the standard multicore CVA6?**
It pins a 2022 CVA6 with a different configuration system; our CA patch conflicted in 7 of 9 files; it is a heavy framework (own build system, old Verilator); and it would need a new adapter to its L1.5. Building a two-core snooping system on current CVA6 was less work and gave us full control ([challenges](07_challenges.md)).

**Q: Why 32-bit?**
Two 64-bit cores plus caches and test logic did not fit comfortably on the KR260. CA and MSI are independent of XLEN; the 32-bit core keeps everything else identical.

**Q: Why no L2? Isn't that unrealistic?**
It makes misses slower but simplifies the protocol: memory is always up to date at a grant, so no cache-to-cache transfers and no L2 coherence are needed. CA's mechanism is unaffected; only absolute latencies change.

**Q: How do you know the bus cannot deadlock or livelock?**
Deadlock: snoops are only accepted when a cache holds no tenure and is idle or waiting, and serving a snoop never needs the bus ([5.6](#56-deadlock-freedom)). Livelock (LR/SC): the LR hold. Starvation: round-robin. All three are checked by watchdogs in every testbench run, and the "no LR hold" mutant is caught 40/40.

**Q: Is `cwrite` really atomic?**
Yes: it executes at commit as an AMO, under a GetM tenure, and the check is repeated in `AMO_EXEC` where no snoop can arrive; check and store happen in the same step ([7.4](#74-cwrite-atomic-at-commit)). Removing the re-check (mutant c4) is caught; the `plain_lock` control shows the try-lock breaks without it.

**Q: What about speculation and branch mispredictions?**
CA ops are recorded at issue per `trans_id` and applied at commit; flushes drop them ([7.3](#73-speculation-record-at-issue-apply-at-commit)). Directed test CA9 (squashed cread) and mutants c5/c6 cover it.

**Q: What about memory ordering (RVWMO)?**
Loads and stores still follow CVA6's ordering; CA does not weaken it. The algorithms use explicit `fence` where they publish data (e.g. before linking a new node). `cwrite` is ordered like an AMO (it waits for older stores to drain). `cread` is a load whose *success* is checked against the coherence state at the time it is answered.

**Q: What happens on an interrupt or context switch?**
A trap revokes access (one cycle after it is taken), so after returning the program's next CA op fails and it retries. The tagSet is not saved/restored; with an OS one could save it or simply rely on revoke-and-retry. This is an open question in [PLAN.md](../PLAN.md).

**Q: How big is the CA unit?**
~1,100 LUTs and ~540 flip-flops per core (4.5% of a core), no BRAM: 8 tag comparators plus the 8-entry pending table and control.

**Q: Why is the clock only 50 MHz?**
It is a conservative target for a first bring-up; timing has 2.39 ns slack, so ~57 MHz works as-is. The critical paths are in the existing CVA6, not in our logic. Throughput ratios are what matter.

**Q: Does the FPGA behave like the simulation?**
Yes: every test gave the same result; we never found a difference. We simulated the exact FPGA RTL before every Vivado run.

### About the results
**Q: Why is CA so much slower than QSBR on read-only work?**
The failure check. A CSR read is executed at commit in CVA6, so `cread` + check costs 7 cycles instead of 2 ([10.4](#104-throughput-results-and-their-explanation)). The paper assumed a free flag. A branch-on-CA-failure instruction, or a `cread` that returns failure in a register, would remove most of it.

**Q: Then why is CA faster than `none` on the stack?**
Under contention on one line, the CAS versions spin in LR/SC loops (24 cycles per attempt, the LR holding the bus); CA's `cread`/`cwrite` attempt is cheaper (17 cycles) and an already-revoked `cwrite` fails without taking the bus. The measured result is 1.33×; the attribution is our explanation.

**Q: Are 2 cores and 3,000 operations enough to conclude anything?**
They are enough to reproduce the paper's qualitative findings (memory, contention, read-side cost) and to measure costs a simulator cannot give; spread between seeds is small. They are not enough for scaling claims; we make none.

**Q: What does "1.33×" mean exactly?**
Total operations divided by the slowest thread's cycles, for `ca`, divided by the same for `none`, both at 2 threads, 100% updates, mean of 3 seeds.

**Q: Why does CA fail even with one thread on the BST?**
Evictions: the tree does not fit in the L1, and an evicted tagged line must revoke. With 64-byte lines and a larger cache this would mostly disappear.

### About the process
**Q: What was the hardest part?**
Getting coherence right under all interleavings (two real races found only by the randomized testbench), and making CA correct in a speculative pipeline (the two ordering rules). On the FPGA side: two combinational loops that only Vivado found.

**Q: What would you do next?**
A branch-on-CA-failure instruction (biggest performance win); cache-to-cache transfers; 64-byte lines; more cores with a scalable interconnect. See [PLAN.md](../PLAN.md).

---

## 14. Glossary
| Term | Meaning |
|---|---|
| **AMO** | atomic memory operation (`amoadd`, `amoswap`, …) |
| **AXI** | ARM's on-chip bus protocol; the cores reach memory through AXI |
| **B response** | the AXI write acknowledgement: data has reached memory |
| **CAFAIL / accessRevokedBit** | CA's failure flag and revoked flag, in CSR 0xCC0 |
| **commit** | the pipeline stage where an instruction's effect becomes permanent |
| **GetS / GetM / PutM** | bus requests: read shared, get exclusive, write back |
| **LR/SC** | load-reserved / store-conditional, RISC-V's other atomic primitive |
| **MSHR** | miss status holding register: the miss being served |
| **PL / PS** | programmable logic (FPGA fabric) / processing system (ARM side) of the Zynq |
| **QSBR / EBR** | quiescent-state / epoch-based reclamation |
| **snoop** | a request the bus forwards to the other cache |
| **SWMR** | single-writer/multiple-reader, the coherence invariant |
| **tagSet** | the lines a core is watching with CA |
| **tenure** | exclusive use of the coherence bus for one transaction |
| **`trans_id`** | CVA6's scoreboard index, follows an instruction from issue to commit |
| **WNS** | worst negative slack; positive means timing is met |
