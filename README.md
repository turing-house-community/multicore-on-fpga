# Conditional Access on CVA6
Hardware support for immediate memory reclamation in optimistic data structures, implemented as four custom RISC-V instructions on the CVA6 core.

**Status:** 🔧 in progress
**Maintainers:** [@AceAryan](https://github.com/AceAryan)
**Started:** August 2026

## Why
Concurrent data structures can read memory that another thread has just freed (use-after-free). Existing fixes (hazard pointers, RCU/QSBR, hardware transactional memory) cost per-read overhead, delay reclamation, or are being disabled on modern CPUs. We implement the Conditional Access primitives from *Efficient Hardware Primitives for Immediate Memory Reclamation in Optimistic Data Structures* (Singh, Brown, Spear), which reuse the cache coherence invalidation that already exists to warn a reader when a line it depends on has changed.

## Quickstart
```bash
# TODO: replace with the exact commands from our setup (WSL2 Ubuntu, Verilator 5.008)

# 1. Build the Verilator model for the 64-bit config
make verilate target=cv64a6_imafdc_sv39

# 2. Compile the C test (use -march=rv64imafdc -mabi=lp64d)
riscv64-unknown-elf-gcc ... ca_test.c -o ca_test.elf

# 3. Run it on the model; a pass ends with tohost = 0
make sim target=cv64a6_imafdc_sv39 elf-bin=ca_test.elf
```
Keep the repo inside the WSL filesystem (not `/mnt/c/...`), or builds get very slow.

## Where we are
**The four instructions** (32-bit encodings, custom-0 / custom-1 opcode space):

| Instruction | Encoding | What it does |
|---|---|---|
| `cread` | `0x0001008b` | Read, and tag the cache line for monitoring |
| `cwrite` | `0x0031100b` | Write only if not revoked |
| `untagOne` | `0x0001002b` | Stop monitoring one address |
| `untagAll` | `0x0000102b` | Clear the tag set and the revoked flag |

**What works:** the instructions decode and run through the real pipeline on a single core (`cv64a6_imafdc_sv39`, write-through D-cache, Verilator), covering the non-revoked path. The cache holds an 8-entry tag set, and a revoked `cwrite` is acknowledged but never written.

**What's next:**
- A test where a tagged line is invalidated, checking that `cread` reports revocation and `cwrite` is suppressed.
- Two-core simulation with OpenPiton (baseline first, then our core).
- FPGA bring-up on the Kria KR260.

**Open questions:**
- Speculative `cread`: is the tag undone if the instruction is flushed?
- Eviction: does a tagged line evicted for capacity reasons also revoke?
- `cwrite`: is the revoke re-checked when the write drains from the write buffer?
- How does software see a `cwrite` failure (result bit, CSR, or trap)?
- 32-bit or 64-bit target, and the tag-set depth (8) and overflow policy.

Details live in PLAN.md.

## How to join
1. Read this README, then skim LOG.md to see how we got here.
2. Pick a task marked 🙋 in PLAN.md (or ask a maintainer).
3. Ping us on <channel / contact>.

## Resources
- Singh, Brown, Spear: *Efficient Hardware Primitives for Immediate Memory Reclamation in Optimistic Data Structures*
- [CVA6](https://github.com/openhwgroup/cva6)
- [cva6-platform](https://github.com/openhwgroup/cva6-platform) (multi-core CVA6 with OpenPiton)

---
Part of the [Turing House Community](https://github.com/turing-house-community), IITGN CSE.
