# The project in depth

This page explains the whole project in one place: the problem, the idea, every piece of hardware we built and why it looks the way it does, how we tested it, what we measured and what the numbers mean. It ends with a FAQ and a glossary. The numbered guides (00–07) cover the same ground in smaller steps and tell you how to run things; this page is for understanding.

It assumes you know what a pipeline and a cache are. File paths are relative to `cva6/`; measured data is under [`results/`](../results/).

**Contents**
1. [The project in one paragraph](#1-the-project-in-one-paragraph)
2. [The problem: safe memory reclamation](#2-the-problem-safe-memory-reclamation)
3. [Conditional Access: the idea and why it is safe](#3-conditional-access-the-idea-and-why-it-is-safe)
4. [The starting point: CVA6](#4-the-starting-point-cva6)
5. [MSI coherence](#5-msi-coherence)
6. [Atomics inside the L1](#6-atomics-inside-the-l1)
7. [The CA unit and the pipeline](#7-the-ca-unit-and-the-pipeline)
8. [Checking for failure: CSR, fast check, `bcafail`](#8-checking-for-failure-csr-fast-check-bcafail)
9. [The shared L2](#9-the-shared-l2)
10. [The system on the KR260](#10-the-system-on-the-kr260)
11. [Verification](#11-verification)
12. [Evaluation](#12-evaluation)
13. [Compared with the paper](#13-compared-with-the-paper)
14. [What is new in this project](#14-what-is-new-in-this-project)
15. [FAQ](#15-faq)
16. [Glossary](#16-glossary)

---

## 1. The project in one paragraph

Singh, Brown and Spear proposed **Conditional Access (CA)**: a few new instructions that let lock-free data structures free memory *immediately* and safely, by reusing the invalidations that cache coherence already produces. They evaluated it only in a simulator. We built it in **real hardware**. We took the open-source single-core RISC-V processor **CVA6**, made a **two-core** system whose private write-back L1 caches are kept coherent by an **MSI protocol** we designed (first over a snooping bus, then through a **directory**), added the **CA instructions** to the pipeline and a **CA unit** next to each cache, added **`bcafail`**, a branch that makes the failure check cheap on RISC-V, and put a **shared L2** in front of memory as in the paper's platform. We verified it from single modules up to the board, ran it on an **AMD KR260 FPGA** at 50 MHz, and ran the paper's benchmarks on the board and on a cycle-exact simulation of the same design. CA frees every removed node immediately (0 left waiting) and is the fastest scheme under contention (1.27× the never-freeing baseline on a stack); on read-heavy work, epoch-based reclamation stays faster at 2 cores.

---

## 2. The problem: safe memory reclamation

### 2.1 Lock-free data structures
In a lock-free (optimistic) data structure, readers walk through shared nodes **without taking locks**. Writers insert and remove nodes at the same time, using atomic instructions or locks on just the nodes they change. This scales well, because readers never block each other or the writers.

### 2.2 The use-after-free
Take a sorted linked list `A → N → B`.
1. Core 0, searching, has loaded the pointer to `N` and is about to read `N->key`.
2. Core 1 deletes `N`: it sets `A->next = B` and calls `free(N)`. The memory of `N` goes back to the allocator and may immediately be reused for another node.
3. Core 0 now reads `N->key` and `N->next`. It reads freed memory: garbage, a pointer into some other structure, or a crash.

The remover cannot know whether some reader still holds a pointer to `N`. That is the whole problem.

### 2.3 Existing software solutions and their costs
| Scheme | How it works | Cost |
|---|---|---|
| **Hazard pointers (HP)** | Before using a node, a reader publishes its address in a shared "hazard" slot, then re-checks that the node is still reachable. A remover frees a node only if no slot names it. | Every read pays a store, a **memory fence** and a re-check. Traversals get much slower. |
| **Epoch-based / quiescent-state reclamation (EBR, QSBR)** | Removed nodes go on a list. They are freed once every thread has passed a "quiescent point" (it holds no references) after the removal. | Reads are free, but **freeing is delayed**. Unfreed memory piles up, and if one thread stalls, it grows without bound. |
| **Never free (`none`)** | Just leak. | The speed upper bound, and unusable in practice. |

All of them trade speed against memory: free late (epochs) or pay on every read (HP).

---

## 3. Conditional Access: the idea and why it is safe

### 3.1 The observation
To unlink and free `N`, core 1 must **write** something core 0 depends on (at least `A->next`, usually also a "deleted" mark in `N`). In a coherent multicore, writing a line needs **exclusive ownership**, so the coherence protocol **invalidates every other copy** of that line, including core 0's. The hardware therefore already knows, at exactly the right moment, that core 0's view has gone stale. CA passes that knowledge on to software.

### 3.2 The instructions (paper semantics)
Each core has:
- a **tagSet**: the cache lines it is watching (8 in our implementation);
- an **accessRevokedBit**: set when a watched line is invalidated or leaves the cache;
- a **failure flag (CAFAIL)**: set when a CA instruction fails.

| Instruction | What it does |
|---|---|
| `cread rd, off(rs1)` | If access is revoked: fail (CAFAIL = 1). Otherwise load the word **and add its line to the tagSet**. |
| `cwrite rs2, off(rs1)` | If the line is tagged and access is not revoked: store, as **one atomic step** with the check. Otherwise fail and store nothing. |
| `untagOne rs1` | Stop watching one line. |
| `untagAll` | Stop watching all lines; clear accessRevokedBit and CAFAIL. |

Access is revoked when a watched line is **written by another core**, **evicted** from the cache (the cache would no longer see invalidations for it), when the tagSet **overflows**, or on an **interrupt or trap**. A remote **read** does not revoke: it only downgrades the line to shared, and the data stays valid.

We added a fifth instruction, `bcafail`, to check for failure cheaply ([section 8](#8-checking-for-failure-csr-fast-check-bcafail)).

### 3.3 Why immediate freeing is safe: hand-over-hand tagging
The lazy-list search with CA (`list_search` in `corev_apu/fpga/kr260/sw/bench/bench.c`, after the paper's Algorithm 3):
```c
untagAll();
pred = head;
curr = cread(&pred->next);   if (failed) retry;   // pred's line tagged
ck   = cread(&curr->key);    if (failed) retry;   // curr's line tagged
while (ck < key) {
    untagOne(pred);                                 // keep only pred and curr tagged
    pred = curr;
    curr = cread(&pred->next);  if (failed) retry;
    ck   = cread(&curr->key);   if (failed) retry;
}
```
**The argument.** Suppose core 0 has read `curr = pred->next` (so `pred` is tagged) and is about to `cread(&curr->key)`. For core 1 to free `curr`, it must first unlink it, which means writing `pred->next`. That write needs `pred`'s line exclusively, so it invalidates core 0's copy of `pred`. `pred` is tagged, so core 0's access is revoked, and its next `cread` (of `curr->key`) **fails**. Core 0 never uses a value from `curr`.

In general: **a node can only be freed after a write to a line the reader has tagged, and every value the reader uses comes from a `cread` that succeeded after it tagged the node before it.** So no value from freed memory is ever acted on, and core 1 may call `free()` right after unlinking.

**Updates** use a CA try-lock (paper, Algorithm 2; `ca_trylock` in `bench.c`):
```c
v = cread(&node->lock);           // tag the node, read the lock word
if (failed || v) return FAIL;     // revoked, or held by someone
cwrite(&node->lock, 1);           // take it only if nobody touched the node since
return !failed;
```
Once a thread holds the locks on `pred` and `curr`, nobody else can free them (a remover would need the lock), so the update itself uses plain loads and stores. The deleting thread marks `curr`, sets `pred->next = curr->next`, unlocks, and **frees `curr` at once**.

The **Treiber stack** (Algorithm 1) needs no locks: `pop` is `t = cread(&top); nx = cread(&t->next); cwrite(&top, nx)`. The `cwrite` succeeds only if nobody changed `top` (or freed `t`) in between: exactly what a compare-and-swap would check, plus protection for the read of `t->next`.

### 3.4 What CA needs from the hardware
1. A coherence protocol that **invalidates** remote copies on a write, and tells the CA unit when it does.
2. A per-core **tagSet** next to the L1, checked on every `cread` and `cwrite`.
3. An **atomic** `cwrite`.
4. Correct behaviour in a **speculative pipeline**. The paper's simulator did not model one; we had to design this.
5. A **cheap way to check for failure** after every `cread`.

CVA6 had none of these: it is a single-core processor with no coherence at all. Sections 5–8 build them.

---

## 4. The starting point: CVA6

**CVA6** (OpenHW Group; formerly Ariane, from ETH Zürich) is an open-source application-class RISC-V core. It has 6 stages, issues one instruction per cycle in order, writes back out of order, uses a scoreboard, and has an MMU and M/S/U privilege modes. It boots Linux on FPGA boards. It is configured at elaboration time by a config package.

Our configuration, **`cv32a6_imac_sv32_wb`** (`core/include/cv32a6_imac_sv32_wb_config_pkg.sv`, new):

| Parameter | Value |
|---|---|
| ISA | RV32IMAC + Zicsr (no floating point) |
| Data cache | `std_nbdcache` (write-back), 32 KiB, 8-way, 16-byte lines |
| Instruction cache | 16 KiB, 4-way, 16-byte lines |
| Scoreboard | 8 entries (so `trans_id` is 3 bits) |
| Commit ports | 2 |
| MMU | present (Sv32), unused by our bare-metal programs |

**Why CVA6:** open source, actively maintained, a realistic pipeline (speculation, a commit stage, a store buffer), and it already runs on Xilinx FPGAs.

**Why 32-bit:** two 64-bit cores with their caches and test logic did not fit the KR260 comfortably. CA and MSI do not depend on the register width.

**Why the write-back cache:** CVA6 has three data caches. The write-through one never holds a line exclusively and dirty, so it cannot have MSI's M state. The HPDcache is large and complex. `std_nbdcache` is a write-back, set-associative, non-blocking cache with a miss handler we could extend.

Our fork starts from upstream commit `81245a47`; [code_map.md](code_map.md) lists every file we changed.

---

## 5. MSI coherence

Upstream CVA6's cache has no notion of another cache. Everything in this section is new.

### 5.1 States and their encoding
| State | Meaning | Encoding in the status array |
|---|---|---|
| **M** (Modified) | the only copy, may be newer than memory; read and write | `valid = 1, owned = 1` (`dirty` = written since the fill) |
| **S** (Shared) | a clean copy, others may have one too; read only | `valid = 1, owned = 0` (never dirty) |
| **I** (Invalid) | not present | `valid = 0` |

We added one bit per way, **`owned`**, to the status memory of `std_nbdcache`. `dirty` already existed.

**Invariant (single writer, multiple readers):** a line is either M in exactly one cache and I in the others, or S/I everywhere.

### 5.2 Requests
| Request | Sent when | Effect on the other cache |
|---|---|---|
| **GetS** | load miss | if it has the line in M: write it back to memory, M → S |
| **GetM** | store miss, store to an S line (upgrade), AMO, LR/SC, `cwrite` | write back if dirty, then → I. **This is the event that revokes CA access.** |
| **PutM** | write-back of a dirty line on eviction or flush | nothing (the writer owns the line, so nobody else has it) |

### 5.3 A tenure
Before a cache touches memory for a cacheable line, it gets a **tenure** from the interconnect:
1. The cache asks with GetS, GetM or PutM (`cc_req_o`).
2. The interconnect forwards it as a **snoop** to the caches that may hold the line (`snoop_i`).
3. Each snooped cache looks the line up and, if needed, writes dirty data back. It acknowledges only after memory confirmed the write (the AXI **B** response).
4. The interconnect grants the requester (`cc_gnt_i`), which now reads memory, knowing it is up to date.
5. The requester signals done (`cc_done_o`).

**Caches never send data to each other.** Dirty data goes to memory (the L2, in the final design) and the requester reads it from there. This keeps the interconnect small, with no data path, at the price of a slower dirty miss.

We built two interconnects with the same interface. `cc_interconnect.sv` picks one: `CcDirectory` on the KR260 top, `+define+CVA6_CC_BUS` in the testharness, `-GDIR` in the two-cache testbench.

### 5.4 The bus (`cc_bus.sv`, about 150 lines)
Our first interconnect: an **atomic broadcast bus**. At most one tenure exists at a time, and every request is snooped by every other cache.

| State | What happens |
|---|---|
| `IDLE` | Pick a requesting cache, round-robin after the last owner. A PutM goes straight to GRANT (nothing to snoop). |
| `SNOOP` | Present the request to every other cache. Wait until each has accepted (`snoop_ready_i`) and acknowledged (`snoop_ack_i`). |
| `GRANT` | Grant the requester. |
| `TENURE` | The requester uses its own AXI port, then pulses `done_i`. |

A GetS miss to a line the other core holds dirty:
```
core 0 miss handler        cc_bus                core 1 miss handler          memory
BUS_REQ: cc_req(GetS,X) -> IDLE: pick core 0
                           SNOOP: snoop(GetS,X) -> SNOOP_CHECK: X is M, dirty
                                                   SNOOP_WB: write X back --------> write
                                                   SNOOP_WB_WAIT: wait for B <----- B
                                                   SNOOP_UPDATE: M -> S, ack
                           GRANT  <---------------------------------------- ack
MISS / REQ_CACHELINE: read X ------------------------------------------------> read
SAVE_CACHELINE: fill X in S <------------------------------------------------- data
cc_done ----------------> TENURE -> IDLE
```
With two cores, a broadcast reaches exactly the one other cache, so the bus does almost everything a directory would.

### 5.5 The directory (`cc_directory.sv`, the default)
The paper uses a directory, and anything beyond two cores needs one, so we added it next to the bus. It records which caches may hold each line and snoops only those.
- **Entries:** `{valid, M, holders[NumCaches], tag}`, set associative: 2048 sets × 4 ways = 8192 lines, twice what both L1s can hold. Stored in UltraRAM.
- **Requests:**

  | Request | Directory entry | Snoops |
  |---|---|---|
  | GetS | M in another cache | GetS to the owner (it writes back and keeps S) |
  | GetS | otherwise | none; the requester joins the holders |
  | GetM | any | GetM to every other holder; the requester becomes the owner |
  | PutM | any | none |

- **Concurrency:** each cache has one transaction at a time, but transactions on **different lines run at the same time**. A request for a line that is already busy waits.
- **Stale entries are harmless:** caches drop clean lines without telling the directory, so its list of holders may be too large. A snoop to a cache that no longer has the line is answered at once.
- **Directory full:** a miss in a full set evicts an entry and invalidates its holders first (a GetM snoop). For CA that counts like an eviction, so tagged lines lose access.
- **Two handshake details:** a cache is never snooped in the cycle it is granted (the miss handler would drop the snoop), and a request a cache withdraws while it serves a snoop is granted only once it is raised again.

On the board, without the L2, the directory is up to 17% faster than the bus when both cores miss on different lines at once, and never more than 2% slower ([results](06_results.md)).

### 5.6 The miss handler (`core/cache_subsystem/miss_handler.sv`)
The largest change (about 500 lines). New states:

| State | Purpose |
|---|---|
| `BUS_REQ` | wait for a tenure before serving a miss |
| `FLUSH_BUS_REQ`, `FLUSH_WB_WAIT` | tenure for writing back a dirty line during a flush, held until the B response |
| `SNOOP_REQ`, `SNOOP_CHECK`, `SNOOP_WB`, `SNOOP_WB_WAIT`, `SNOOP_UPDATE` | serve a snoop: read the set, look up the line, write back if dirty, wait for B, downgrade or invalidate, ack |
| `AMO_BUS_REQ`, `AMO_LOOKUP`, `AMO_EXEC` | atomics and `cwrite`, in the L1, under a GetM tenure |
| `LR_HOLD` | keep the LR's tenure for its SC |

Flows:
- **Load miss:** `BUS_REQ` (GetS) → grant → `MISS` → evict a victim if needed (a dirty victim is written back in the same tenure) → `REQ_CACHELINE` → fill in **S**.
- **Store miss:** the same with GetM; fill in **M**.
- **Store to an S line (upgrade):** `cache_ctrl.sv` treats a store hit on a line it does not own as a **miss**. The miss handler takes a GetM tenure, which invalidates the other copy, and refills the line in place, in M. Refilling avoids having the same tag twice in a set. An upgrade therefore costs about as much as a miss; an upgrade without data would be a valid optimization.
- **Eviction of a dirty line:** written back in the current tenure. Evicting a **tagged** line revokes CA access.
- **Snoop:** as above. A GetM snoop that hits also clears an LR reservation on that line and tells the CA unit.

### 5.7 Deadlock freedom
The classic deadlock: cache A holds a tenure and waits for B's snoop answer, while B waits for a tenure. Our rule: **a cache can always answer a snoop without needing the interconnect.** In `miss_handler.sv`:
```systemverilog
assign snoop_ready_o = !bus_held_q &&
    (state_q inside {IDLE, BUS_REQ, FLUSH_BUS_REQ, FLUSH_REQ_STATUS, AMO_BUS_REQ});
```
Snoops are accepted only when the cache holds **no tenure** and nothing is half-done: it is idle, or merely *waiting* for a tenure. In those states, answering a snoop (read the set, maybe write back, update, ack) uses only the cache's own memory and AXI port. So every snoop is answered, every tenure ends, and the system always makes progress. After a snoop, the cache goes back to waiting and re-reads the set, because the snoop may have changed the line it was about to fetch. The same rule holds for the directory. **Keep it if you change anything.**

### 5.8 Races we handled
| Race | Resolution |
|---|---|
| A snoop arrives while our own miss to the **same line** waits for a tenure | after the grant, the miss re-reads the tags instead of trusting what it saw before |
| A store is between its tag look-up and its write when a snoop takes the line | a snoop on a set holds off stores to that set |
| During an upgrade (store to an S line), a **load** could still hit the old S copy after the other core had written a newer value (**found by our testbench**) | a load may not hit the line the miss unit is fetching (`mshr_addr_matches_i` in `cache_ctrl.sv`) |
| Two cores doing LR/SC on one line invalidate each other's reservations forever: a **livelock** (**found by our testbench**) | after an LR, the cache keeps its tenure up to 64 cycles for the matching SC (section 6) |

---

## 6. Atomics inside the L1

Upstream `std_nbdcache` runs an AMO by **flushing the whole cache** and sending the AMO to memory. With two caches that is slow and wrong: the other cache could hold a stale or dirty copy. We moved cacheable AMOs and LR/SC **into the L1**:
1. `AMO_BUS_REQ`: take a **GetM tenure** for the line, which invalidates the other copy.
2. `AMO_LOOKUP` / `AMO_EXEC`: if the line is not here in M, fetch it in M under the same tenure; then do the read-modify-write in one step with `amo_alu.sv`.
3. Release the tenure.

No snoop can arrive while a cache holds a tenure, so the look-up and the write in `AMO_EXEC` are atomic with respect to the other core.

**LR/SC:** LR records a reservation. A GetM snoop on that line, its eviction, a flush, or any SC clears it. SC succeeds only if the reservation is still there. **The livelock fix:** after an LR, the cache stays in `LR_HOLD` and **keeps its tenure** for up to 64 cycles (`LrHoldCycles`), during which only the SC to the reserved line may run. So an LR followed soon by its SC always succeeds, which is the forward-progress guarantee the RISC-V spec asks for.

**`cwrite` reuses this path** as a new AMO type, `AMO_CWRITE`. That is what makes it atomic (section 7.4).

---

## 7. The CA unit and the pipeline

### 7.1 Encodings and decoding (`core/decoder.sv`)
| Instruction | Opcode | funct3 | Format | Unit / operation |
|---|---|---|---|---|
| `cread rd, imm(rs1)` | custom-0 `0x0B` | 0 | I | LOAD / `CREAD` |
| `cwrite rs2, imm(rs1)` | custom-0 `0x0B` | 1 | S | STORE / `CWRITE` |
| `untagOne rs1` | custom-1 `0x2B` | 0 | I | LOAD / `UNTAG_ONE` |
| `untagAll` | custom-1 `0x2B` | 1 | I | LOAD / `UNTAG_ALL` |
| `bcafail label` | custom-1 `0x2B` | 2 | B (rs1 = rs2 = x0) | CTRL_FLOW / `BCAFAIL` |

Custom-0 and custom-1 are opcode spaces the RISC-V spec reserves for extensions, so no standard instruction is displaced. Other funct3 values, and `bcafail` with a nonzero register, stay illegal. The assembler does not know these names, so we write them with `.insn` (`.insn i 0x0B, 0, rd, rs1, off` for `cread`), and in C through inline-assembly wrappers in `bench.c`.

**The CSR 0xCC0** (`CSR_CAFAIL`, read-only): bit 0 = CAFAIL, bit 1 = accessRevokedBit. Writing it is illegal; `untagAll` is the only way to clear it.

### 7.2 The CA unit (`core/cache_subsystem/ca_tag_set.sv`)
One per core, inside `std_nbdcache`:

| Structure | Size | Purpose |
|---|---|---|
| **tagSet** | 8 entries: line address + valid | lines tagged by **committed** `cread`s |
| **pending table** | 8 entries, one per `trans_id`: {operation, line address, invalidated, failed} | CA operations the cache has seen but that have **not committed yet** |
| `revoked` | 1 bit | accessRevokedBit |
| `cafail` | 1 bit | CAFAIL |

It is all flip-flops and comparators, no memory blocks: about 1,000 LUTs and 540 registers per core.

### 7.3 Speculation: record at issue, apply at commit
CVA6 runs loads speculatively: a `cread` may execute in the cache and then be **squashed** (a mispredicted branch, an exception in an older instruction). If a squashed `cread` had tagged a line, the program would later see failures without a cause. Worse, if a squashed `untagAll` had cleared the revoked bit, a real revocation would be lost. So CA state changes **only at commit**:
1. **Issue.** When a CA operation reaches the cache with its address, it is written into the pending table at its `trans_id`.
2. **Answer.** A `cread` is answered like a load but checked at that moment. If it fails, it returns all ones (`0xFFFF_FFFF`) and is marked *failed* in the pending table. `untagOne`/`untagAll` do no memory access and return at once.
3. **While pending:** if the line of a pending `cread` is invalidated, its entry is marked *invalidated*.
4. **Commit** (`ca_commit_valid_i`/`ca_commit_id_i`, driven from `cva6.sv` for each commit port, in program order):
   - a committed failed `cread` sets CAFAIL;
   - a committed `cread` whose line was invalidated while pending sets revoked;
   - a committed successful `cread` adds its line to the tagSet; if the tagSet is full, it sets revoked (**overflow**);
   - `untagOne` removes one line; `untagAll` clears the tagSet, revoked and CAFAIL.
5. **Flush:** on any pipeline flush, all pending entries are dropped.

**When a `cread` fails** (`ca_tag_set.sv`):
```systemverilog
cread_revoked_o = revoked_q || tag_hit_now || pending_lost;
```
- `revoked_q`: access is already revoked;
- `tag_hit_now`: a tagged line is being invalidated **in this very cycle**;
- `pending_lost`: an **older `cread` that has not committed yet** already lost its line.

**Two ordering rules the paper did not need** (its model has no speculation):
1. **untagAll hold-off.** While an `untagAll` is pending, the cache accepts **no new CA operation**. Without this, the usual retry loop `untagAll; cread ...` would check the `cread` against the *old* revoked bit (the `untagAll` that clears it has not committed yet), fail, retry, and fail forever.
2. **Pending-lost rule.** Take `cread A; cread B`, both executed before either commits. If A's line is invalidated after A ran but before B runs, B must fail: when A commits it will set revoked anyway, and B's data may already come from a freed node (the write to A may have been the unlink of B).

### 7.4 `cwrite`: atomic at commit
`cwrite` must check "tagged and not revoked" **and** store, with no gap in between. Our first prototype (on the write-through cache) decided early and stored later, so another core could slip in. Now (`store_unit.sv`, `commit_stage.sv`, `miss_handler.sv`):
1. `cwrite` takes the **AMO path**: it waits until it is the oldest instruction and the store buffer is empty, like `amoswap`.
2. In `IDLE`, the miss handler checks `ca_cwrite_allowed` (line tagged, access not revoked). If not: **fail at once, without a tenure**, and set CAFAIL.
3. Otherwise take a **GetM tenure**, fetching the line in M if needed.
4. In `AMO_EXEC`, **check again**: while this core waited for its tenure, the other core may have written a tagged line. Then store. While the tenure is held no snoop can arrive, so check and store are atomic.

The re-check in step 4 matters: removing it (injected bug c4) is caught by the testbench.

### 7.5 What revokes access, and where it comes from
| Source | Signal | Origin |
|---|---|---|
| another core's write | `snoop_invalidate_valid_i` | `miss_handler.sv`, `SNOOP_UPDATE` on a GetM |
| eviction of a tagged line, a flush | `invalidate_valid_i`, `invalidate_all_i` | `miss_handler.sv` |
| a directory eviction | (arrives as a GetM snoop) | `cc_directory.sv` |
| tagSet overflow | internal | commit of a `cread` with a full tagSet |
| trap or interrupt | `ca_trap_i` | `cva6.sv`, **registered one cycle** in `std_nbdcache.sv` |

**Why eviction must revoke:** a line that is no longer in the cache will not be snooped, so a later remote write to it would go unnoticed. Revoking is the safe choice (the paper does the same). It means CA can only watch as many lines as the cache can keep: the BST sees about 27 failures per run even with one thread, because the tree does not fit in the L1.

**Why the trap revocation is one cycle late:** at first a trap revoked in the same cycle. But the commit stage decides about traps using the `cwrite`'s acknowledge, which depended on the revoked bit, which depended on the trap: a **combinational loop**, which Vivado refused. Registering the trap breaks it. It is safe because a trap flushes the pipeline, so nothing tagged can commit in between.

---

## 8. Checking for failure: CSR, fast check, `bcafail`

After every `cread`, software has to know whether it failed before it uses the value. The paper assumes a **flag register** that a conditional jump can test, like EFLAGS on x86: the check is free. RISC-V has no flags, so we needed something else, and this turned out to matter a lot for performance.

### 8.1 The CSR (first version)
CAFAIL is bit 0 of CSR 0xCC0: `csrr t0, 0xCC0; andi t0, t0, 1; bnez t0, retry`. The problem: **CVA6 executes CSR reads only at commit, not speculatively.** Right after a `cread`, the `csrr` waits until the `cread` has completed and committed, and everything younger waits behind it. So `cread` + check costs **7 cycles**, against 2 for the `cread` alone (a `csrr` by itself costs 1). A list hop does two of these. This was the main reason CA was much slower than in the paper on read-heavy work.

### 8.2 The fast check
A failed `cread` returns **all ones** (`0xFFFF_FFFF`). Software first compares the value; only if it equals all ones does it read the CSR to be sure (a real value can be all ones too, just rarely):
```c
#define CA_FAILED(v) ((uint32_t)(v) == 0xFFFFFFFFu && cafail())
```
This is a one-line hardware change (`cache_ctrl.sv`). `cread` + check: **5 cycles**. Benchmark scheme `cafast`.

### 8.3 `bcafail`: a branch on CA failure
`bcafail label` jumps if CAFAIL is set. It is the closest RISC-V equivalent of testing the paper's flag. The hard part is that it must not wait for commit (that is what made the CSR slow), yet it must never give a different answer from the CSR.

How it works (`issue_read_operands.sv`, `ca_tag_set.sv`, `alu.sv`):
1. **Wait for what matters, not for commit.** In the issue stage, `bcafail` is held until every **older `cread` has its answer** from the cache, and every older `cwrite` and `untagAll` has **committed**. Unrelated older instructions do not hold it up.
2. **Read a speculative flag.** It then reads `cafail_spec_o` from the CA unit: CAFAIL, OR any older `cread` in the pending table that failed but has not committed yet. That is exactly what CAFAIL will be once those `cread`s commit.
3. **Branch.** The value goes to the ALU as an operand, and the branch is taken on bit 0. It is predicted not taken, so a failure costs a redirect, like a mispredicted branch.

`cread` + `bcafail` costs **4 cycles**. After a `cwrite` it is 1 cycle slower than the CSR (18 against 17), because it waits for the `cwrite` to commit and then resolves as a branch. It costs 17 LUTs. Benchmark scheme `cabr`.

**Is it always right?** The CSR is unchanged and stays the reference. `verif/tests/custom/ca_2core/bcafail.S` checks `bcafail` in each situation we could think of: a clean state, a cold miss, a failed `cread` that has not committed yet, right after `untagAll`, after a failed `cwrite`, and an illegal encoding. It then runs 2,000 rounds while the other core writes the watched line, comparing every outcome with the CSR. On the board: 754 rounds taken, 1,246 not taken, no mismatch.

### 8.4 What it bought
| | `cread` + check | best-case CA throughput gain over the CSR |
|---|---|---|
| CSR | 7 cycles | – |
| fast check | 5 cycles | up to 1.5× (list) |
| `bcafail` | 4 cycles | up to 1.5× (list), and the best results under contention |

---

## 9. The shared L2

### 9.1 Why
Our first system sent every L1 miss straight to the ARM side's DDR4. The paper's platform has a **shared 256 KiB L2**, and the difference changed results: a dirty miss cost 97 cycles and a core-to-core handoff 151, because data went out to DDR and back. Slow misses also hid part of CA's per-read cost. We wanted the comparison with the paper to be about CA, not about missing hardware.

### 9.2 Design (`corev_apu/fpga/kr260/src/axi_l2_cache.sv`)
It sits between the cores' AXI mux and DDR, so all memory traffic passes through it.
- **Geometry:** 256 KiB, 64-byte lines, 8 ways, write-back and write-allocate, tree pseudo-LRU replacement. The paper does not give the associativity; 8 ways is our choice.
- **Storage:** data in UltraRAM, tags and dirty bits in block RAM, valid bits and LRU state in flip-flops.
- **Non-blocking:** 4 MSHRs. Each runs its own refill (and the write-back of a dirty victim) towards DDR, while hits to other lines are served. A request to a line that has a miss in flight waits, and responses to one AXI ID stay in order. `L2NonBlocking = 0` gives a blocking version.
- **Bypass:** addresses outside DDR (the mailbox) pass straight through.

### 9.3 Why it needs no coherence logic
The L1s already write dirty data back, and wait for the B response, before they answer a snoop or refill a line. The L2 sends B only once the data is in its array. So whenever a cache reads a line after a tenure, the latest data is in the L2 or in DDR, and the L2 returns it. The L2 is just a faster memory to the coherence protocol.

### 9.4 Reset
Before every program, the ARM side writes the new program straight into DDR, bypassing the L2. So the L2 resets with the cores and **drops everything**, including dirty lines, so that it never writes stale data over the new program.

### 9.5 The bug only the board found
The first L2 passed its randomized testbench and the full-system simulation, then **hung on the board**: the benchmark programs timed out, and the micro-benchmark wrote its result to the wrong place.
- **Cause:** AXI says that once a request is offered (`valid` high), it must not change until it is accepted (`ready`). The L2's arbiter towards DDR could switch to a different request while waiting. The simulated DDR always accepted at once, so this never happened in simulation; the real interconnect sometimes makes you wait.
- **Why our checks missed it:** we had assertions for exactly this rule. But Verilator only checks assertions when built with `--assert`, and we had not used it.
- **Fix:** the arbiter now holds its choice until the request is accepted. The testbench's DDR model stalls at random, every L2 build uses `--assert`, and 200/200 randomized runs pass.

### 9.6 What it changed
Read miss 54 → 33 cycles, read of a line the other core holds dirty 97 → 32, a handoff between the cores 151 → 59. Never-free throughput went up to 2.26× on the contended stack. CA's ratios to `none` dropped a little, because cheaper misses no longer hide its extra work, but the fastest scheme for each workload stayed the same ([section 12](#12-evaluation)).

---

## 10. The system on the KR260

**Board:** AMD Kria KR260 with the K26 module, a Zynq UltraScale+ (`xck26-sfvc784-2LV-c`). The chip has two halves:
- **PS (processing system):** ARM cores and 4 GB of DDR4. We use only its DDR and its debug access.
- **PL (programmable logic):** the FPGA fabric: 117,120 LUTs, 234,240 flip-flops, 144 block RAMs, 64 UltraRAMs. Our design goes here.

**Top level** (`corev_apu/fpga/kr260/src/cva6_kr260_top.sv`):
- two `cva6` instances, hart IDs 0 and 1, both starting at `0x8000_0000`;
- the directory (or the bus), connecting their snoop and tenure ports;
- one register slice (`axi_cut`) per core, then an `axi_mux` merging the two AXI masters (the cut breaks a combinational loop between the two cores' arbiters);
- the shared L2;
- an address remap: core `0x8000_0000–0xBFFF_FFFF` (cacheable) → PS DDR `0x4000_0000`; core `0xC000_0000` → the mailbox (uncached).

**Block design** (`scripts/kr260_bd.tcl`): the Zynq PS with the KR260 preset. The cores' traffic enters DDR through the PS's `S_AXI_HP0_FPD` port. The PS reaches an 8 KiB **mailbox** BRAM and a **run bit** (a GPIO) through `M_AXI_HPM0_FPD`. The PL clock is 50 MHz.

### 10.1 How a program runs
There is no operating system and no SD card.
1. A C program (`bench.c`) or an assembly test is **cross-compiled** for RV32IMA, bare metal (`crt.S` gives each hart a stack and calls `main(hartid)`), and linked with `sw/link_kr260.ld`: code at `0x8000_0000`, `tohost` in the mailbox at `0xC000_0000`. `objcopy` turns the ELF into a raw binary.
2. **Vivado** turns the RTL into a bitstream (`kr260_build.sh`; Vivado runs on Windows, driven from WSL).
3. On the PC, **`kr260_run.sh`** calls AMD's `xsdb` over the JTAG cable (the micro-USB port), which runs `scripts/run_test.tcl`:
   1. program the PL with the bitstream and initialize the PS (`psu_init`, taken from the `.xsa`), only on the first run;
   2. hold the cores in reset (run bit = 0); this also empties the L2;
   3. clear the mailbox, write the seed to mailbox word 2, copy the binary into DDR at `0x4000_0000`;
   4. set the run bit; both cores start at `0x8000_0000`;
   5. poll `tohost` (mailbox word 0) until the program writes `1` (pass) or `(code << 1) | 1` (fail);
   6. print `RESULT` and the mailbox words 16 and up (`MBOX`), where programs put their measurements.

**Why the mailbox:** the caches are write-back, so a result stored to DDR may stay in a cache indefinitely, invisible to the PC. The mailbox is outside the cacheable range, so stores go straight out.

### 10.2 Resources (`prebuilt/reports/`)
| Resource | Used | Of | % |
|---|---|---|---|
| LUTs | 78,120 | 117,120 | 67 |
| Flip-flops | 46,128 | 234,240 | 20 |
| Block RAM tiles | 78 | 144 | 54 |
| UltraRAM | 10 | 64 | 16 |

| Block | LUTs | Memory |
|---|---|---|
| one CVA6 core with its caches | about 25,000 | – |
| CA unit, per core | about 1,000 | none |
| `bcafail` | 17 in total | none |
| directory | 676 | 2 UltraRAM |
| shared L2 | 18,508 | 8 UltraRAM, 8 small block RAMs |

Timing is met at 50 MHz with 2.86 ns to spare. A third core might fit; a fourth would not with these cache sizes.

---

## 11. Verification

We tested from small to large, and each level passed before we moved on. At each level we also checked that the tests **can fail**.

### 11.1 One cache (`core/cache_subsystem/test/std_nbdcache_msi_tb.sv`)
Drives one `std_nbdcache` with random loads, stores and **snoops** (playing the other cache and the interconnect), against a byte-accurate reference memory and an AXI memory model. It checks every load, the line states after each snoop, and that dirty data is written back before an ack. 300/300 seeds pass.

### 11.2 Two caches + interconnect + CA (`std_nbdcache_2core_tb.sv`)
Two caches, the real directory (or bus), the CA units, and the testbench playing both pipelines, including the commit stage (it commits, squashes and raises traps).
- **Every cycle:** the single-writer invariant on every line in use (millions of checks per run).
- **Loads:** checked against the history of written values.
- **AMOs:** exact; two AMOs on a counter never return the same old value.
- **Liveness:** watchdogs for deadlock, timeouts and fairness.
- **A model of the paper's CA rules**, checked after every operation:
  - a successful `cread` means no tagged line was invalidated or written by the other core since it was tagged;
  - a successful `cwrite` hit a tagged line under the same condition, and a failed one wrote nothing;
  - `cread` values are linearizable;
  - CAFAIL is set after a committed failure and cleared by `untagAll`;
  - every failure has a cause (no spurious failures).
- **11 directed CA tests:** basic success; remote write revokes; remote read does not; `cwrite` to an untagged line; `untagOne`; overflow; eviction; trap (with and without tags); squashed `cread`; `untagAll` hold-off; older pending `cread` lost.
- **Runs:** 400 when MSI was added, 400 more after CA was added (200 seeds × {normal, `+hot`} each, on the bus), and 400 over the directory, tiny directories that keep evicting (2 and 16 sets) and the bus. Together with the 300 single-cache runs, that is 1,500 randomized runs, all passing.

### 11.3 Is the testbench any good? Injected bugs
We put bugs into the RTL one at a time and checked that the testbenches fail (40 seeds each). **26 of 27 were caught:**

| Group | Bugs | Caught |
|---|---|---|
| One cache (m1–m9): snoop skips the dirty write-back; ack before the B response; GetM does not invalidate; snoop does not hold off stores; no refill on upgrade; the stale-hit race re-introduced; store without ownership; flush releases the tenure before B; GetS fill marked M | 9 | 9 (m8 was missed at first; we added flush-race tests until it was caught) |
| Two caches (p1–p7): grant before the snoop acks; no snoop on GetS; SC ignores the reservation; GetM keeps the reservation; no LR hold (livelock); AMO without a tenure; no round-robin | 7 | 6 |
| CA (c1–c11): snoop does not revoke; eviction does not revoke; `cwrite` ignores the tag; `cwrite` without the re-check; no `untagAll` hold-off; no pending-lost rule; failed `cread` returns data; trap does not revoke; `untagAll` keeps revoked; GetS revokes; overflow does not revoke | 11 | 11 |

The one missed, **p7 (no round-robin)**, cannot change behaviour with two caches: after a tenure the bus always spends a cycle idle, and by then the other waiting cache is the only requester.

### 11.4 The L2 on its own (`corev_apu/fpga/kr260/sim/axi_l2_cache_tb.sv`)
A random master (line refills and write-backs like an L1's, single beats with random byte enables, mailbox accesses, several IDs, several requests in flight) against a reference memory. Behind the L2, a DDR model with random latency, responses reordered between IDs, and random stalls on every channel. Halfway, a reset with dirty lines in the L2, which must be dropped. It also checks per-ID response order and the AXI handshake rules. Built with `--assert`; 50 seeds × {real size, a tiny 512-byte L2} × {non-blocking, blocking} = 200/200 pass.

### 11.5 The full processor
CVA6's Verilator testharness, one core and two cores (`defines=CVA6_2CORE`):
- **RISC-V ISA tests** (rv32ui, um, ua, uc, mi, si): 72/73 pass, including all atomic tests through the new in-L1 path. The one failure, `rv32mi-p-breakpoint`, is disabled upstream for 32-bit configs too.
- **`msi_2core.S`:** counters with `amoadd` and with LR/SC from both harts, turn-taking ping-pong with plain loads and stores, false sharing, message passing with fences.
- **`ca_2core.S`:** every instruction and the CSR; trap revocation; **reclamation**: hart 1 unlinks and poisons nodes while hart 0 walks the list with `cread`s, and a successful `cread` must never see a poisoned node; **the paper's try-lock** guarding a plain counter, which must reach exactly 2N.
- **`bcafail.S`:** section 8.3.

### 11.6 Negative controls
A test that always passes proves nothing. Variants of `ca_2core.S` in `verif/tests/custom/ca_2core/controls/`:

| Variant | Expected and observed |
|---|---|
| plain `lw` instead of `cread` in the reader | **fails** (code 30): reads a freed node |
| plain `sw` instead of `cwrite` in the try-lock | **fails** (code 32): two threads in the lock |
| additionally require at least one revoked `cread` | **passes**: revocations really happen |

So the reclamation test really detects use-after-free, and CA really prevents it.

### 11.7 The exact FPGA design, then the board
`sim/kr260_bd_wrapper_sim.sv` replaces the Vivado block design with a behavioural model (DDR loaded from a binary, the mailbox, the run bit), so Verilator simulates **exactly the RTL that goes into Vivado**. Before every Vivado run we also lint for combinational loops (`-Wwarn-UNOPTFLAT`), because Vivado refuses to build with one. Then on the board: all the tests above give the same result as in simulation, and every benchmark run checks its data structure at the end: 1,800 runs over all our designs, all valid.

### 11.8 Simulation vs. board
We ran the whole benchmark campaign in simulation too (`sim/run_bench_sim.sh`), to see whether a simulator can stand in for the board. Without the L2, the simulated DDR needed an extra latency of 34 cycles (calibrated with `micro_coh.c`) and still differed by up to 13% in a few contended configurations. With the L2, most misses never reach DDR, and the simulation matches the board **cycle for cycle** in all 144 configurations. So anyone can study this system, with exact numbers, without a board.

---

## 12. Evaluation

### 12.1 Setup (after the paper's section 6)
| | |
|---|---|
| Data structures | lazy list (1K keys), external BST (10K keys), Treiber stack, hash table (128 buckets of lazy lists) |
| Schemes | `none` (never frees), `ca` (CSR check), `cafast` (fast check), `cabr` (`bcafail`), `hp` (hazard pointers, scan every 30 removals), `qsbr` (epoch advanced every 150 allocations) |
| Retire lists | at most 512 removed nodes per thread for `hp` and `qsbr`; a full `qsbr` list waits for the other thread's quiescent state (this never happened in our runs) |
| Workload | 0, 10 and 100% updates (inserts and deletes 50/50), random keys, 50% prefill, 3,000 operations per thread |
| Threads, seeds | 1 and 2 threads; seeds 1, 2, 3 |
| Total | 4 × 6 × 3 × 2 = 144 configurations × 3 seeds = **432 runs**, all valid |

**Throughput** = total operations / the slowest thread's time. **Unreclaimed** = nodes removed but not yet freed at the end of a run. A node is exactly one 16-byte line (key, next, lock, mark), so there is no false sharing between nodes. Freeing a node really reuses it: `free_node` overwrites it and puts it on a per-thread free list.

**How the schemes are implemented.** `none`, `hp` and `qsbr` use the standard lazy list with spin locks, and a compare-and-swap for the stack, which compiles to an LR/SC loop on RV32IMA. HP publishes each pointer with a store, `fence rw,rw` and a re-check. CA follows the paper's algorithms (section 3.3); the three CA schemes differ only in how they check for failure.

### 12.2 Memory
Nodes removed but not yet freed at the end of a run (2 threads, 100% updates):

| | `none` | `ca` (all three) | `hp` | `qsbr` |
|---|---|---|---|---|
| list | 1,489 | **0** | 20 | 118 |
| BST | 3,028 | **0** | 32 | 141 |
| stack | 2,972 | **0** | 34 | 202 |
| hash | 1,485 | **0** | 23 | 102 |

This is the paper's central claim, on real hardware: **with CA, memory use is that of a sequential data structure.**

### 12.3 Throughput
Relative to `none` (2 threads; 1.00 = as fast as never freeing):

| | `ca` | `cafast` | `cabr` | `hp` | `qsbr` |
|---|---|---|---|---|---|
| list 0% | 0.34 | 0.50 | 0.50 | 0.25 | **1.00** |
| list 100% | 0.41 | 0.59 | 0.58 | 0.31 | **0.99** |
| BST 0% | 0.46 | 0.62 | 0.59 | 0.38 | **1.00** |
| BST 100% | 0.59 | 0.76 | 0.74 | 0.47 | **0.90** |
| stack 0% | 0.37 | 0.43 | 0.42 | 0.50 | **0.92** |
| stack 100% | 1.20 | 1.25 | **1.27** | 0.99 | 1.03 |
| hash 0% | 0.48 | 0.56 | 0.64 | 0.47 | **0.99** |
| hash 100% | 0.81 | 0.87 | **0.99** | 0.69 | 0.91 |

**Read-heavy work: epochs win.** Their read path is plain loads, so they match `none`. CA pays on every protected read: even with `bcafail`, `cread` + check is 4 cycles against 1 for a plain load, and a list hop does two of them. The list (long traversals) suffers most, the BST (short paths) least. **HP is slower still**: each hop pays a store, a fence (6 cycles) and a re-check.

**Under contention: CA wins.** On the stack at 100% updates, CA with `bcafail` reaches 1.27× `none`; epochs 1.03×, HP 0.99×. Both threads hammer one line (`top`). Our explanation, which we did not measure piece by piece:
- The CAS-based versions retry with LR/SC loops (22 cycles per attempt, and the LR holds its tenure).
- A failed `cwrite` gives up without even taking a tenure.
- `none` keeps allocating fresh nodes that miss in the cache, while CA reuses nodes it just freed. This part shrank when the L2 made those misses cheaper.

On the hash table, where contention is spread over 128 buckets, CA with `bcafail` is ahead of epochs (0.99 against 0.91).

**The three CA checks.** The fast check and `bcafail` each lift CA by up to 1.5× over the CSR. `bcafail` wins where failures are common (stack and hash at 100% updates). The fast check is slightly ahead on the list and BST, which do long chains of reads with few failures.

### 12.4 What the L2 changed
| | `none` faster with the L2 by | best CA vs `none`: no L2 → L2 | fastest scheme: no L2 → L2 |
|---|---|---|---|
| list 100% | 1.10× | 0.61 → 0.59 | qsbr → qsbr |
| BST 0% | 1.48× | 0.71 → 0.62 | qsbr → qsbr |
| BST 100% | 1.46× | 0.83 → 0.76 | qsbr → qsbr |
| stack 100% | 2.26× | 1.37 → 1.27 | cafast → cabr |
| hash 100% | 1.70× | 1.01 → 0.99 | cabr → cabr |

The platform matters: the L2 changed every absolute number and moved CA's ratios by up to 0.10, but not the conclusions.

### 12.5 Instruction latency (`micro.c`, one core, L1 hits)
| Operation | Cycles |
|---|---|
| plain load / plain store | 1.0 / 1.0 |
| `cread` | 2.0 |
| `cread` + CSR check / fast check / `bcafail` | 7.0 / 5.0 / 4.0 |
| `csrr 0xCC0` alone | 1.0 |
| `untagOne` / `untagAll` | 0 (hidden) / 4.0 |
| `cread` + `cwrite` (try-lock) | 15 |
| `cread` + `cwrite` + CSR check / + `bcafail` | 17 / 18 |
| `amoswap.w` (atomic in the L1) | 12 |
| `lr.w` + `sc.w` | 22 |
| `fence rw,rw` | 6 |

### 12.6 Coherence cost (`micro_coh.c`, two cores)
One hart measures while the other prepares the remote state; each test uses 256 fresh lines; values include about 6.5 cycles of loop overhead.

| Access | with L2 | without L2 |
|---|---|---|
| read miss, no other copy | 32.8 | 53.7 |
| read miss, the other core holds the line M | 32.1 | 96.9 |
| write to S, the other core also has S | 20.0 | 50.4 |
| write to S, nobody else has it | 16.2 | 49.5 |
| one-way handoff (ping-pong) | 59.0 | 150.6 |
| read hit | 6.3 | 6.5 |

Two things to notice:
- **Invalidating a clean copy costs only a few cycles** more than an upgrade nobody else shares (about 1 without the L2, about 4 with it). That invalidation is exactly the event CA listens to, so CA's signal is almost free.
- Without the L2, a dirty remote line cost about 43 extra cycles because its data went through DDR. With the L2 it costs no more than a plain miss.

---

## 13. Compared with the paper

### 13.1 Differences in setup
| | Paper | This work | Effect |
|---|---|---|---|
| Platform | Graphite simulator | real RTL on an FPGA, plus an exact simulation of it | ours includes every real pipeline effect |
| Threads | up to 32 | 2 | the paper's largest CA wins (16–32 threads) are out of reach |
| Cores | simulated | in-order CVA6, 50 MHz | compare ratios, not absolute numbers |
| Coherence | directory MSI | directory MSI (or bus), no cache-to-cache transfer | |
| Caches | 64 B lines, shared 256 KiB L2 | 16 B L1 lines, shared 256 KiB L2 (64 B lines) | no false sharing between our nodes |
| Failure check | a flag register (free) | `bcafail` (2 cycles after a `cread`) | CA a bit slower on read-heavy work |
| Baselines | none, rcu, qsbr, ibr, hp, he | none, qsbr, hp | `qsbr` stands in for the epoch family |

### 13.2 The numbers
The paper reports its results only as plots, and has no 2-thread point. We read its plots with scripts. For CA vs `none` at 100% updates, we take the paper's plotted line between its 1- and 4-thread points at x = 2 (`paper_interp_2t.py`, about ±15%):

| | paper, 2 threads (estimated) | our simulator | our board |
|---|---|---|---|
| list | 0.67 | 0.59 | 0.59 |
| BST | 0.97 | 0.76 | 0.76 |
| stack | 0.57 | 1.27 | 1.27 |
| hash | 1.08 | 0.99 | 0.99 |

- On the list and the hash table we are close to the paper.
- On the BST we are lower, which fits our more expensive failure check.
- The stack is the big difference: in the paper CA is slower than never freeing, on our in-order cores it is faster.

What carries over: CA frees immediately, and it does best under contention. What does not: the paper's big speed-ups appear at 16–32 threads, where hazard pointers and epochs scale badly, and two cores cannot test that.

**A caveat on reading plots.** Our first plot reader (`paper_digitize.py`) averaged each marker with the line running into it. That reads steep curves too low at 4 threads: list 0.96 instead of about 0.76, BST 1.10 instead of about 0.89. The 2-thread estimates above use a careful marker reader; the full table in [`results/paper_comparison.md`](../results/paper_comparison.md) notes the bias.

---

## 14. What is new in this project
1. **A hardware implementation of Conditional Access** on a real RISC-V pipeline, running real benchmarks on an FPGA.
2. **A coherent two-core CVA6 without OpenPiton:** MSI on CVA6's write-back cache, a deadlock-free bus and a directory, AMOs and LR/SC in the L1 with a livelock fix, and a shared non-blocking L2. Useful beyond CA.
3. **CA in a speculative pipeline:** record at issue and apply at commit, an atomic `cwrite` at commit, and two ordering rules the paper's model did not need.
4. **`bcafail`:** a RISC-V answer to the paper's flag register, correct under speculation, for 17 LUTs.
5. **Measured costs a simulator cannot give:** instruction latencies, coherence costs, area, and how much the platform (the L2, the failure check) changes CA's results.
6. **Evidence for correctness:** reference models, injected bugs, negative controls, and a simulation that matches the board cycle for cycle.

---

## 15. FAQ

### The idea
**Why can't software alone do this?**
Software can only notice that another core wrote a line it read by paying on every read (HP's fence) or by delaying frees (epochs). The coherence protocol notices for free; CA passes that on.

**Is it really safe to free right away?**
Yes, if the CA rules are followed: every value comes from a `cread` checked after the node before it was tagged, and freeing a node first needs a write to a line the reader has tagged (the unlink), which revokes the reader (section 3.3). The `ca_2core` reclamation test and the `plain_reads` control show it on the board.

**What if the freed memory is reused before the reader notices?**
Reusing writes the node, which again invalidates any copy the reader has, so its next `cread` fails. The reader never acts on a value from a failed `cread`.

**Why does a remote read not revoke?**
A read does not change the data, so the watched values are still valid. Revoking on reads would only cause pointless retries. Injected bug c10 ("GetS revokes") is caught by the check that every failure must have a cause.

**Why 8 tags?**
The paper's algorithms keep only a few lines tagged at a time (list: `pred` and `curr`; BST: grandparent, parent, leaf), dropping lines behind them with `untagOne`. 8 leaves headroom. It is a parameter (`DEPTH`). Overflow revokes, so correctness never depends on it.

**What happens on an interrupt or a context switch?**
A trap revokes access, so after returning the program's next CA operation fails and it retries. The tagSet is not saved. Under an operating system one could save it, or simply rely on revoke and retry; this is an open question.

### The hardware
**Why a directory, if the bus does the job for two cores?**
The bus was the right place to start: simple and easy to prove correct. We added the directory because the paper uses one, because anything beyond two cores needs one, and because it lets misses to different lines proceed at the same time (up to 17% faster on the board). CA itself only needs the invalidation, which both provide.

**Why not OpenPiton, the usual multicore CVA6?**
It pins a 2022 CVA6 with a different configuration system. Our CA changes conflicted in 7 of 9 files; it brings its own heavy framework (build tools, an old Verilator); and it would need a new adapter to its L1.5. Building our own two-core system on current CVA6 was less work and gave us full control ([challenges](07_challenges.md)).

**How do you know it cannot deadlock or livelock?**
- **Deadlock:** snoops are accepted only when a cache holds no tenure, and answering one never needs the interconnect (section 5.7).
- **LR/SC livelock:** the LR hold.
- **Starvation:** round-robin on the bus, and a guaranteed eviction slot in the directory.

The testbench's watchdogs check all three on every run, and the "no LR hold" bug is always caught.

**Is `cwrite` really atomic?**
Yes. It runs at commit on the AMO path, under a GetM tenure, and the check is repeated where no snoop can arrive; check and store happen in the same step (section 7.4). The `plain_lock` control shows the try-lock breaks without it.

**What about memory ordering?**
Loads and stores follow CVA6's ordering; CA does not weaken it. The algorithms use explicit `fence`s where they publish data (for example before linking a new node). `cwrite` is ordered like an AMO. A `cread` is a load whose success is checked against the coherence state at the moment it is answered.

**Why does `bcafail` not just read the CSR value early?**
Because the CSR is only up to date once older CA instructions commit. `bcafail` instead waits until older `cread`s have their answers and older `cwrite`/`untagAll` have committed. Then it reads CAFAIL together with the failed-but-uncommitted `cread`s, which is exactly what the CSR will show (section 8.3).

**Could a `cread` report failure in a register instead?**
Yes, for example by writing its success to a second destination register, so no separate check is needed. RISC-V instructions write only one register, so this needs a different encoding or two instructions. We chose a branch, which fits the existing pipeline. It is an open idea in [PLAN.md](../PLAN.md).

**Why does the L2 not need to take part in coherence?**
The L1s write dirty data back, and wait for the B response, before they answer a snoop, and the L2 answers a write only once the data is stored. So a cache reading a line after a tenure always gets the latest data (section 9.3).

**Why is the clock only 50 MHz?**
It is a safe target for bring-up. Timing has 2.86 ns of slack, so about 55–60 MHz should work as is. The critical paths are in CVA6 itself, not in our logic. Throughput ratios are what matter here.

**Does the FPGA behave like the simulation?**
Yes. Every test gave the same result, and with the L2 the benchmark cycle counts are identical. We simulated the exact FPGA RTL before every Vivado run.

### The results
**If epochs are faster on read-heavy work, what is CA for?**
- **Memory:** CA leaves no removed node waiting, while epochs keep 100–200. With epochs that number has no bound if a thread stalls, so CA's memory bound is the thing epochs cannot give.
- **Contention:** CA is the fastest scheme on the contended stack and hash table.
- **Scale:** the paper's large speed-ups appear at 16–32 threads, which two cores cannot show.

**Why is CA faster than never freeing on the stack?**
See section 12.3: the CAS versions spin in LR/SC loops on one line, a failed `cwrite` gives up without a tenure, and CA reuses warm nodes. The measured result is 1.27×; the split between these causes is our explanation, not separately measured.

**Why does CA fail even with one thread on the BST?**
Evictions. The tree does not fit in the L1, and an evicted tagged line must revoke access. Larger lines and a larger cache would mostly remove this.

**Are 2 cores and 3,000 operations enough to conclude anything?**
They are enough to reproduce the paper's qualitative findings (memory, contention, the cost of reads) and to measure costs a simulator cannot give; the spread between seeds is small. They are not enough to say anything about scaling, and we do not.

**What does "1.27×" mean exactly?**
Total operations divided by the slowest thread's time, for `cabr`, divided by the same for `none`, both with 2 threads at 100% updates, mean of 3 seeds.

### Tools and process
**What was the hardest part?**
- Getting coherence right under every interleaving: two real races were found only by the randomized testbench.
- Making CA correct in a speculative pipeline, which needed the two ordering rules and the design of `bcafail`.
- On the FPGA side: two combinational loops that only Vivado found, and the L2 handshake bug that only the board found.

**Which tools are needed?**
- RISC-V GCC (cross-compiler), Verilator (5.032 for most testbenches, 5.008 for CVA6's testharness) and Spike, all in WSL or Linux.
- Vivado 2023.2 or newer for the KR260; the free Standard edition supports its chip.
- A KR260 board, with the JTAG cable (its micro-USB port).

[Getting started](00_getting_started.md) has the steps.

**Why both Windows and WSL?**
Vivado ran on Windows on our PC, and everything else (compilers, Verilator) runs best in Linux. The scripts call Vivado and `xsdb` through `cmd.exe` and copy sources to a Windows folder, because Windows tools work badly inside the WSL file system. On a Linux PC with Linux Vivado the same Tcl scripts work directly ([FPGA guide](04_fpga_kr260.md)).

**Where should I start reading the code?**
Follow one load: `core/load_unit.sv` → `std_nbdcache.sv` → `cache_ctrl.sv` → `miss_handler.sv`. Then read `ca_tag_set.sv` and the CA parts of `decoder.sv` and `issue_read_operands.sv`. Run the two-cache testbench with `+catrace` and follow a few CA operations in the trace. [Challenges](07_challenges.md) has a full learning path.

**What could be done next?**
More cores, CA under an operating system, a `cread` that reports failure in a register, 64-byte L1 lines, cache-to-cache transfers, and the paper's other baselines. See [PLAN.md](../PLAN.md).

---

## 16. Glossary
| Term | Meaning |
|---|---|
| **AMO** | atomic memory operation (`amoadd`, `amoswap`, …) |
| **AXI** | ARM's on-chip bus protocol; the cores reach memory through it |
| **B response** | the AXI write acknowledgement: the data has arrived |
| **`bcafail`** | our branch instruction: jump if CAFAIL is set |
| **CAFAIL / accessRevokedBit** | CA's failure flag and revoked flag, in CSR 0xCC0 |
| **commit** | the pipeline stage where an instruction's effect becomes permanent |
| **directory** | a table recording which caches hold each line, so only those are snooped |
| **GetS / GetM / PutM** | coherence requests: read shared, get exclusive, write back |
| **L2** | the second-level cache, shared by both cores, in front of DDR |
| **LR/SC** | load-reserved / store-conditional, RISC-V's other atomic primitive |
| **MSHR** | miss status holding register: one miss being served |
| **PL / PS** | programmable logic (FPGA fabric) / processing system (ARM side) of the Zynq |
| **QSBR / EBR** | quiescent-state / epoch-based reclamation |
| **snoop** | a request the interconnect forwards to another cache |
| **SWMR** | single writer / multiple readers, the coherence invariant |
| **tagSet** | the lines a core is watching with CA |
| **tenure** | the right to use memory for one coherence transaction |
| **`trans_id`** | CVA6's scoreboard index; it follows an instruction from issue to commit |
| **WNS** | worst negative slack; positive means timing is met |
