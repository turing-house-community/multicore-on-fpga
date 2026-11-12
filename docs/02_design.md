# 2. Hardware design: MSI coherence, the CA unit and the L2

This page explains what we added to CVA6 and why each piece is shaped the way it is. Read [the background](01_background.md) first. File names are relative to `cva6/`; [code_map.md](code_map.md) lists every changed file.

```
   +---------------- KR260 FPGA (PL) ------------------+      +--- ARM side (PS) ---+
   |                                                   |      |                     |
   |  CVA6 core 0            CVA6 core 1               |      |  DDR memory         |
   |  +-----------+          +-----------+             |      |  JTAG / control     |
   |  | pipeline  |          | pipeline  |             |      |                     |
   |  | CA unit   |          | CA unit   |  <- layer 3 |      |                     |
   |  | L1 D$ MSI |<-snoop-->| L1 D$ MSI |  <- layer 1 |      |                     |
   |  +-----+-----+          +-----+-----+             |      |                     |
   |        | directory (cc_directory)  |  <- layer 2  |      |                     |
   |        +------------+-------------+               |      |                     |
   |              shared L2 (256 KiB)  <- layer 4      |      |                     |
   |               memory port (AXI) ------------------+----->|  DDR                |
   |               mailbox (results) <-----------------+------|  read by PC         |
   +---------------------------------------------------+      +---------------------+
```

## Starting point and main decisions

| Decision | Choice | Why |
|---|---|---|
| Base core | CVA6, 32-bit **RV32IMAC**, new config `cv32a6_imac_sv32_wb` | Two 64-bit cores plus tests did not fit the KR260's LUTs comfortably. See [challenges](07_challenges.md). |
| Which cache to extend | the **write-back** cache `std_nbdcache` | MSI needs lines that one core owns and may hold dirty. The write-through cache cannot do that. |
| Coherence protocol | **MSI** | Three states are enough for CA, which only needs to see the invalidations. |
| Interconnect | first a **snooping bus**, now a **directory** (both still selectable) | We started with an atomic bus: simple, and with 2 cores a broadcast reaches exactly the cache a directory would pick. We then added a directory, as in the paper. It lets misses to different lines run at the same time, and it is what a design with more cores would need. |
| L2 cache | **shared, 256 KiB**, as in the paper | Without it every miss went to DDR, which made coherence and CA look different from the paper's platform. Caches write dirty data back before anyone reads it, so the L2 needs no coherence logic of its own. |
| Atomics | AMOs and LR/SC run **inside the L1** | Needed for correctness with two caches, and `cwrite` reuses the same path, which makes it atomic. |
| CA failure flag | a read-only **CSR at 0xCC0**, plus a branch `bcafail` | RISC-V has no flags register. The paper assumes one; `bcafail` is the closest equivalent. |

---

## Layer 1: MSI in the L1 data cache

### Why coherence is needed
Each core has a private L1 data cache. If core 0 writes address X, core 1 might still have an old copy of X. A coherence protocol makes sure every read sees the latest write, and two cores never hold conflicting copies.

### The three states
| State | Meaning | Read? | Write? |
|---|---|---|---|
| **M** (Modified) | only valid copy, possibly newer than memory | yes | yes |
| **S** (Shared) | clean copy; the other cache may have one too | yes | no (upgrade to M first) |
| **I** (Invalid) | not in this cache | miss | miss |

CVA6 already kept `valid` and `dirty` bits per line. We added one bit, **`owned`**, in the cache's status memory:

| State | valid | owned |
|---|---|---|
| I | 0 | – |
| S | 1 | 0 |
| M | 1 | 1 |

**Invariant:** a line is M in at most one cache, and then it is I in the other.

### Requests
| Request | Sent when | Effect on the other cache |
|---|---|---|
| **GetS** | load miss | if it holds the line in M: write it back, M → S |
| **GetM** | store miss, store to an S line, AMO, `cwrite` | write back if dirty, then → I |
| **PutM** | writing back a dirty line on eviction or flush | nothing |

```
          own load miss (GetS)            own store (GetM)
   I  --------------------------->  S  -------------------->  M
   ^                                |                          |
   |      other core's GetM         |   other core's GetS      |
   +--------------------------------+   (write back) M -> S <--+
   ^                                                           |
   +-------------- other core's GetM (write back) -------------+
```

## Layer 2: the directory (`core/cache_subsystem/cc_directory.sv`)

A cache must get a **tenure** from the interconnect before it touches memory for a cacheable line. We built two interconnects with the same interface; `cc_interconnect.sv` picks one (`CcDirectory` on the KR260 top, `+define+CVA6_CC_BUS` in the testharness).

**The directory (default).** For each line it tracks, it records which caches may hold it and whether one holds it Modified. On a request it snoops only those caches:

| Request | Directory entry | Snoops |
|---|---|---|
| GetS | Modified in the other cache | GetS to the owner (it writes back, keeps S) |
| GetS | otherwise | none |
| GetM | any | GetM to every other holder |
| PutM | any | none |

- It holds 2048 sets × 4 ways = 8192 lines (twice what both L1s hold), in UltraRAM.
- Requests for **different lines run at the same time**; a second request for a line that is busy waits.
- Caches drop clean lines silently, so the directory may think a cache holds a line it no longer has. That is harmless: the snoop is answered at once.
- When a set is full, the directory evicts an entry and invalidates its holders first. For CA that counts like an eviction, so tagged lines lose access.

On the board the directory is up to 17% faster than the bus when both cores miss on different lines at once, and never more than 2% slower ([results](06_results.md)).

**The bus (`cc_bus.sv`).** The first version: one tenure at a time, alternating fairly between the cores, every request forwarded as a snoop to the other cache. With 2 cores it does almost the same job. The steps below describe a tenure on the bus; the directory works the same way, except that it snoops only the recorded holders.

1. A cache asks with GetS, GetM or PutM (`cc_req_o`).
2. The bus forwards the request as a **snoop** to the other cache (`snoop_i`).
3. The other cache looks the line up and, if needed, writes dirty data back. It acknowledges only after memory confirmed the write (the AXI B response).
4. The bus grants the requester (`cc_gnt_i`), which now reads memory knowing it is current.
5. The requester signals done (`cc_done_o`), and the bus moves on.

Caches never send data to each other directly: dirty data goes to memory (the L2) first.

### Why it cannot deadlock
**Rule: a cache can always answer a snoop without needing the bus (or the directory).** Snoops are accepted only while the cache is idle or waiting for the bus, never in the middle of its own memory operation. So when both cores want the bus, the one being snooped can always finish, and the bus always makes progress. **Keep this rule if you change anything.**

### Races found and fixed
| Race | Fix |
|---|---|
| A snoop arrives while our own miss to the same line waits for the bus | the miss re-reads the tags after it gets the bus |
| A store is between tag look-up and write when a snoop takes the line | stores to that set are held off during a snoop |
| A store to an S line: the old S copy is still readable while the upgrade is in flight (*found by our testbench*) | loads may not hit a line the miss unit is fetching |
| Two cores spinning on LR/SC kill each other's reservation forever, a livelock (*found by our testbench*) | after an LR, the cache keeps the bus up to 64 cycles (`LrHoldCycles`) so its SC can succeed |

### Atomics
AMOs (e.g. `amoadd`) used to bypass the cache, which is wrong with two caches. Now they:
1. get the line in M (a GetM tenure),
2. do the read-modify-write in the L1 in one step (`amo_alu.sv`),
3. release the bus.

LR records a reservation. Any snoop or eviction of that line clears it, and SC succeeds only if it is still there.

---

## Layer 3: Conditional Access (`core/cache_subsystem/ca_tag_set.sv`)

A thread **tags** lines it reads with `cread`. If another core writes one of them, or the line leaves the cache, the thread's **accessRevokedBit** is set, and its next `cread`/`cwrite` fails. The CA unit just listens to the GetM snoops and evictions the MSI cache already produces.

### The instructions
| Instruction | Encoding | Behaviour |
|---|---|---|
| `cread rd, imm(rs1)` | custom-0 (`0x0B`), funct3 0, I-type | tag the line, load if access not revoked; on failure return all ones (0xFFFF_FFFF) and set CAFAIL |
| `cwrite rs2, imm(rs1)` | custom-0 (`0x0B`), funct3 1, S-type | store only if the line is tagged and access not revoked; on failure store nothing, set CAFAIL |
| `untagOne rs1` | custom-1 (`0x2B`), funct3 0 | stop watching one line |
| `untagAll` | custom-1 (`0x2B`), funct3 1 | stop watching all; clear accessRevokedBit and CAFAIL |
| `bcafail label` (ours) | custom-1 (`0x2B`), funct3 2, B-type, rs1 = rs2 = x0 | branch if CAFAIL is set |

The assembler does not know these names. Our tests define them with `.insn`:
```asm
#define CREAD(rd, off, rs1)   .insn i 0x0B, 0, rd, rs1, off
#define CWRITE(rs2, off, rs1) .insn s 0x0B, 1, rs2, off(rs1)
#define UNTAG_ONE(rs1)        .insn i 0x2B, 0, x0, rs1, 0
#define UNTAG_ALL             .insn i 0x2B, 1, x0, x0, 0
#define CAFAIL(rd)            csrr rd, 0xCC0; andi rd, rd, 1
#define BCAFAIL(label)        .insn b 0x2B, 2, x0, x0, label
```
In C, `corev_apu/fpga/kr260/sw/bench/bench.c` wraps them in inline-assembly functions.

**CSR 0xCC0** (read-only): bit 0 = **CAFAIL**, bit 1 = accessRevokedBit. Software tests bit 0.

### Checking for failure cheaply
After every `cread`, software must know whether it failed. The paper assumes a flag register, which costs nothing. We have three ways, from slowest to fastest:

| Check | Cost after a `cread` | How |
|---|---|---|
| CSR | 5 cycles | `csrr 0xCC0`. CVA6 executes CSR reads only at commit, so the pipeline drains first. |
| fast check | 3 cycles | A failed `cread` returns all ones, so compare the value first and read the CSR only on a match (rare: few real values are 0xFFFF_FFFF). |
| `bcafail` | 2 cycles | A branch that reads CAFAIL without waiting for commit. |

How `bcafail` stays correct in a speculative pipeline:
- The issue stage holds it until every older `cread` has its answer from the cache, and every older `cwrite`/`untagAll` has committed.
- It then reads CAFAIL together with any older `cread` that failed but has not committed yet (`ca_tag_set.cafail_spec_o`).
- It is predicted not taken; a failure redirects fetch like a mispredicted branch.
- The CSR is unchanged and stays the reference: `verif/tests/custom/ca_2core/bcafail.S` compares every `bcafail` outcome with it.

It costs 17 LUTs.

### What revokes access
- another core's **write** to a tagged line (a GetM snoop hit)
- **evicting** or flushing a tagged line
- **overflow**: more than 8 lines tagged (`DEPTH = 8`)
- a **trap** or interrupt while lines are tagged

A remote **read** does not revoke, as in the paper.

### How CA fits a speculative pipeline
CVA6 executes loads before it knows that an earlier branch or exception will not cancel them. CA state must only change for instructions that really complete:
- **Record at issue, apply at commit.** `cread`, `untagOne`, `untagAll` are recorded in a small pending table keyed by the instruction's scoreboard index (`trans_id`). They take effect when the instruction commits. Cancelled ones leave no trace.
- **`cwrite` runs at commit, like an atomic** (`AMO_CWRITE` in `miss_handler.sv`). It waits until it is the oldest instruction, takes the line in M under a GetM tenure, where no snoop can arrive, then checks the tag and stores in the same step. Nothing can sneak in between the check and the write.
- **Two ordering rules the paper does not need**, because it does not model speculation:
  - While an `untagAll` waits to commit, no new CA request is accepted. Otherwise the retry loop `untagAll; cread` would see the old revoked bit forever.
  - A `cread` also fails if an older, not yet committed `cread` already lost its line.

---

## Layer 4: the shared L2 and the KR260 system

Two cores, the directory, an AXI multiplexer, the shared L2 and an address remap in the FPGA fabric (`corev_apu/fpga/kr260/src/cva6_kr260_top.sv`).

**The L2** (`corev_apu/fpga/kr260/src/axi_l2_cache.sv`) sits between the cores' AXI mux and DDR, like the paper's shared L2:
- 256 KiB, 64-byte lines, 8 ways, write-back. Data in UltraRAM, tags in block RAM.
- Non-blocking: up to 4 misses in flight, and hits are served while they wait.
- It answers a write only once the data is in the L2, so a later read from either core sees it. That is all the L1 coherence protocol needs; the L2 has no coherence logic.
- The mailbox bypasses it. On every program load it resets and drops its contents, because the ARM side writes the new program straight into DDR.
- It cut a read miss from 54 to 33 cycles and a core-to-core handoff from 151 to 59. The ARM side provides DDR and loads programs over JTAG. Programs report results through an uncached **mailbox**. Details in [the FPGA guide](04_fpga_kr260.md).

## Where to look in the code
| Area | Files |
|---|---|
| MSI cache | `core/cache_subsystem/miss_handler.sv` (misses, write-backs, snoops, AMOs, LR/SC, `cwrite`), `cache_ctrl.sv` (hit/miss per port; store to S becomes a miss), `std_nbdcache.sv` (the cache; `owned` bit), `std_cache_subsystem.sv` |
| Coherence | `core/cache_subsystem/cc_directory.sv`, `cc_bus.sv`, `cc_interconnect.sv` |
| Conditional access | `core/cache_subsystem/ca_tag_set.sv`; `core/decoder.sv`, `load_unit.sv`, `store_unit.sv`, `commit_stage.sv`, `csr_regfile.sv`, `cva6.sv` |
| Config | `core/include/cv32a6_imac_sv32_wb_config_pkg.sv` |
| Two-core simulation top | `corev_apu/tb/ariane_testharness.sv` (with `CVA6_2CORE`) |
| `bcafail` | `core/decoder.sv`, `issue_read_operands.sv`, `alu.sv`, `cache_subsystem/ca_tag_set.sv` |
| Shared L2 | `corev_apu/fpga/kr260/src/axi_l2_cache.sv` |
| FPGA | `corev_apu/fpga/kr260/` |

The same explanation, in slightly more detail, is in the fork itself: `cva6/docs/msi_ca_kr260/`.
