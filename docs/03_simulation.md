# 3. Simulation: check everything without a board

Every result in this project was first checked in simulation. This page reproduces those checks in four levels, from fast and small to slow and complete. Finish [getting started](00_getting_started.md) first, and run everything from `multicore-on-fpga/cva6` with your `env.sh` sourced.

| Level | What runs | Build time | Needs |
|---|---|---|---|
| 1. One cache | `std_nbdcache` + reference memory | ~1 min | Verilator 5.032 |
| 2. Two caches | 2 × `std_nbdcache` + directory (or bus) + CA units | ~2 min | Verilator 5.032 |
| 3. Full processor | 1 or 2 complete CVA6 cores running RISC-V programs | ~10 min each | Verilator 5.008, Spike |
| 4. Exact FPGA design | the KR260 top level (cores, directory, L2), with a stand-in for the ARM side; also the L2 on its own, and the full benchmark campaign | ~10 min | Verilator 5.032 |

Build outputs go to `build/` (not tracked by git). Create it once: `mkdir -p build`.

---

## 1. One cache: the MSI testbench

`core/cache_subsystem/test/std_nbdcache_msi_tb.sv` drives a single cache with random loads, stores and **snoops** (as if from another core), and checks every load against a reference memory model.
```bash
verilator --binary --timing -j 8 -Wno-fatal -Wno-lint -Wno-style -Wno-UNOPTFLAT \
  --top-module std_nbdcache_msi_tb -Mdir build/tb1 -f core/cache_subsystem/test/std_nbdcache_msi_tb.f
build/tb1/Vstd_nbdcache_msi_tb +seed=1 +nrandom=4000
```
**Expected:** `PASSED`, followed by Verilator's simulation report.

| Option | Effect |
|---|---|
| `+seed=N` | a different random sequence; try many: `for s in $(seq 1 20); do build/tb1/Vstd_nbdcache_msi_tb +seed=$s +nrandom=4000 \| grep -a -E 'PASSED\|FAILED'; done` |
| `+nrandom=N` | number of random operations |
| `+debug` | per-cycle trace of the cache state machines |
| `+axidebug` | every AXI beat to memory |
| `+watch=<hex addr>` | every event on one address |

## 2. Two caches: the MSI + CA testbench

`core/cache_subsystem/test/std_nbdcache_2core_tb.sv` is the most important testbench. It connects two caches through the real directory (or, with `-GDIR=0`, the bus), and checks every cycle that:
- no line is Modified in both caches (the **single-writer** invariant),
- every load returns a value that was really written,
- atomics are exact (two AMOs on a counter never return the same old value),
- CA follows the paper's rules: a successful `cread`/`cwrite` means no watched line was taken since it was tagged, a failed `cwrite` wrote nothing, and no failure happens without a cause,
- nothing deadlocks or starves (watchdogs).

It runs 11 directed CA tests (remote read does not revoke, untagOne, overflow, eviction, trap, squashed `cread`, …) and then random traffic.
```bash
verilator --binary --timing -j 8 -Wno-fatal -Wno-lint -Wno-style -Wno-UNOPTFLAT \
  --top-module std_nbdcache_2core_tb -Mdir build/tb2 -f core/cache_subsystem/test/std_nbdcache_2core_tb.f
build/tb2/Vstd_nbdcache_2core_tb +seed=1 +nrandom=1500
build/tb2/Vstd_nbdcache_2core_tb +seed=1 +nrandom=1500 +hot     # both cores fight over 2 lines
```
**Expected:** each run prints a coverage line and `PASSED` (then Verilator's report), for example
```
coverage: AXI line writes=1127 reads=1777, SWMR checks=3072550, max times passed over=1
PASSED
```
Options at build time (add to the `verilator` line): `-GDIR=0` uses the bus instead of the directory; `-GDIR_SETS=2` or `16` makes the directory tiny, so it keeps evicting entries and back-invalidating lines.

We ran 200 seeds × {normal, `+hot`} = 400 runs on the first design, and later 400 more over the directory, small directories and the bus. All pass:
```bash
for s in $(seq 1 200); do
  for m in "" "+hot"; do
    r=$(build/tb2/Vstd_nbdcache_2core_tb +seed=$s +nrandom=1500 $m | grep -a -E -o 'PASSED|FAILED.*'); echo "$s $m $r"
  done
done | grep -v PASSED          # prints nothing if all pass
```
Debug options: `+cadebug` (CA unit events), `+catrace` (every CA op and its result), `+lrscdebug`, `+debug`.

> **Is the testbench any good?** We checked by **injecting bugs** (mutants) into the RTL, one at a time, for example "a GetM snoop does not revoke CA access" or "do not write back a dirty line on GetS". The testbench caught 26 of 27; the one it missed cannot change behaviour with two caches. Try it: break something in `ca_tag_set.sv` and watch the run fail.

## 3. The full processor

Now the complete CVA6 cores, running real RISC-V programs. This uses CVA6's own Verilator testharness (`corev_apu/tb/ariane_testharness.sv`) and needs Verilator 5.008 and Spike ([getting started, steps 4b and 5](00_getting_started.md#step-4-verilator)).

### 3a. Build the models (about 10 minutes each)
```bash
make verilate target=cv32a6_imac_sv32_wb ver-library=work-ver NUM_JOBS=$(nproc)
make verilate target=cv32a6_imac_sv32_wb defines=CVA6_2CORE ver-library=work-ver-2core NUM_JOBS=$(nproc)
```
The first is a single core; the second (`CVA6_2CORE`) has two cores and the coherence bus. Both create `<dir>/Variane_testharness`.

> Builds take long. If your terminal might close, run them with `setsid nohup make ... > build.log 2>&1 &` and check `build.log`.

### 3b. Standard RISC-V ISA tests
```bash
export LD_LIBRARY_PATH=$PWD/tools/spike/lib
work-ver/Variane_testharness verif/tests/riscv-tests/isa/rv32ui-p-add
```
**Expected:** `... rv32ui-p-add *** SUCCESS *** (tohost = 0) after ... cycles`. To run all 73 rv32 tests:
```bash
for t in $(ls verif/tests/riscv-tests/isa | grep -E '^rv32(ui|um|ua|uc|mi|si)-p-' | grep -v dump); do
  r=$(timeout 300 work-ver/Variane_testharness verif/tests/riscv-tests/isa/$t 2>&1 | grep -a -o -E 'SUCCESS|FAILED.*')
  echo "$t ${r:-TIMEOUT}"
done | tee isa_results.txt | grep -v SUCCESS
```
**Expected:** 72 of 73 pass. Only `rv32mi-p-breakpoint` fails; upstream CVA6 disables that test for 32-bit configs too. The same works with `work-ver-2core` (the second core parks).

### 3c. Our two-core programs
| Program | What it checks |
|---|---|
| `verif/tests/custom/msi_2core/msi_2core.S` | coherence: AMO and LR/SC counters from both cores, ping-pong, false sharing, message passing |
| `verif/tests/custom/ca_2core/ca_2core.S` | all four CA instructions, CSR 0xCC0, revocation by trap, a reader using `cread` while the other core frees and reuses nodes, and the paper's `cread`/`cwrite` try-lock |
| `verif/tests/custom/ca_2core/bcafail.S` | `bcafail` in every situation we could think of (clean, cold miss, a failed `cread` not yet committed, after `untagAll`, after a failed `cwrite`, illegal encoding), then 2,000 rounds with the other core writing the watched line; every outcome is checked against the CSR |

```bash
mkdir -p build
for p in msi_2core/msi_2core ca_2core/ca_2core ca_2core/bcafail; do
  riscv64-unknown-elf-gcc -march=rv32ima_zicsr -mabi=ilp32 -nostdlib -nostartfiles \
    -T verif/tests/custom/${p%/*}/link.ld verif/tests/custom/$p.S -o build/${p#*/}.elf
  work-ver-2core/Variane_testharness build/${p#*/}.elf | grep -a -E 'SUCCESS|FAILED'
done
```
**Expected:** `*** SUCCESS *** (tohost = 0)` for all three. On failure, `tohost` holds `(code << 1) | 1`; search the `.S` file for `FAIL_IF(<code>` to see which check failed.

### 3d. Negative controls: proving the CA test means something
A test that always passes proves nothing. These variants of `ca_2core.S` remove conditional access, so they **should fail** ([details](../cva6/verif/tests/custom/ca_2core/controls/README.md)):
```bash
for c in plain_reads plain_lock need_revoked; do
  riscv64-unknown-elf-gcc -march=rv32ima_zicsr -mabi=ilp32 -nostdlib -nostartfiles \
    -T verif/tests/custom/ca_2core/link.ld verif/tests/custom/ca_2core/controls/$c.S -o build/$c.elf
  echo "$c: $(work-ver-2core/Variane_testharness build/$c.elf | grep -a -o -E 'SUCCESS|FAILED.*')"
done
```
**Expected:** `plain_reads` fails (code 30: read a freed node), `plain_lock` fails (code 32: two threads in the lock), `need_revoked` passes (revocations really happen).

## 4. The exact FPGA design

Before spending an hour in Vivado, simulate **exactly the RTL that goes on the FPGA**: the KR260 top level with both cores, the directory, the AXI mux, the shared L2 and the address remap. `sim/kr260_bd_wrapper_sim.sv` stands in for the Vivado block design: it models DDR (preloaded from a binary at PS address `0x4000_0000`), the mailbox and the run bit.
```bash
K=corev_apu/fpga/kr260
$K/scripts/gen_filelist.sh < /dev/null > build/kr260.f
verilator --binary --timing -j 8 -O2 -Wno-fatal -Wno-lint -Wno-style -Wno-UNOPTFLAT -Wno-BLKANDNBLK \
  --top-module cva6_kr260_top -Mdir build/kr260 \
  +incdir+core/include +incdir+vendor/pulp-platform/common_cells/include +incdir+vendor/pulp-platform/common_cells/src \
  +incdir+vendor/pulp-platform/axi/include +incdir+common/local/util \
  +incdir+core/cache_subsystem/hpdcache/rtl/src/utils/ecc +incdir+core/cache_subsystem/hpdcache/rtl/include \
  $K/sim/kr260_bd_wrapper_sim.sv -f build/kr260.f
$K/sw/build_tests.sh build/board     # programs linked for the board (ISA tests only if riscv-tests is installed)
riscv64-unknown-elf-objcopy -O binary -R .tohost build/board/ca_2core.elf build/ca_2core.bin
build/kr260/Vcva6_kr260_top +bin=build/ca_2core.bin
```
**Expected:** `loaded ... bytes at PS 0x40000000` and then `RESULT PASS at <time>`.

Useful options for `Vcva6_kr260_top`: `+mem_lat=34` adds DDR-like latency (34 cycles matches the board), `+seed=N` is passed to the program as on the board, `+max_cycles=N` sets the timeout. To try the design without the L2 or with the bus, add `-GL2Enable=0` or `-GCcDirectory=0` to the `verilator` line.

### The L2 on its own
`sim/axi_l2_cache_tb.sv` drives the L2 with random reads and writes from several IDs, against a reference memory. Behind it is a DDR model with random latency, out-of-order responses and random back-pressure. Halfway through it resets the L2 with dirty lines in it, which must be dropped.
```bash
verilator --binary --timing --assert -j 8 -Wno-fatal -Wno-lint -Wno-style --top-module axi_l2_cache_tb \
  -Mdir build/l2tb -GTINY=1 +incdir+vendor/pulp-platform/axi/include \
  vendor/pulp-platform/axi/src/axi_pkg.sv $K/src/axi_l2_cache.sv $K/sim/axi_l2_cache_tb.sv
build/l2tb/Vaxi_l2_cache_tb +seed=1 +n=20000          # L2 TEST PASSED
```
- `-GTINY=1` makes a 512-byte L2 so evictions happen all the time; leave it out for the real size. `-GNB=0` tests the blocking version.
- `+l2stats` prints hits, misses and hits served while a miss was pending. It works in any simulation that contains the L2.
- **Always build with `--assert`.** Without it Verilator silently skips the AXI handshake checks. We learned this the hard way: our first L2 broke an AXI rule and hung on the board, while every simulation without `--assert` passed.

We ran 50 seeds × {real size, tiny} × {non-blocking, blocking} = 200 runs, all passing.

### The benchmarks in simulation
`sim/run_bench_sim.sh` builds the model once and runs a whole folder of benchmark programs in parallel. It writes a `results.txt` in the same format as the board, so `analyze.py` reads both:
```bash
$K/sim/run_bench_sim.sh build build/sim_model
$K/sim/run_bench_sim.sh run build/sim_model build/bench/elf build/bench_sim 8 34    # 8 jobs, mem_lat 34
python3 $K/sw/bench/analyze.py build/bench_sim/raw/results.txt build/bench_sim
```
With the L2, the simulated cycle counts match the board exactly in all 144 configurations. A full campaign (432 runs) takes several hours; finished runs are skipped if you restart it.

**Before a Vivado run, also check for combinational loops.** Vivado refuses to generate a bitstream when it finds one (DRC `LUTLP-1`), and the commands above hide them (`-Wno-UNOPTFLAT`). Rerun the Verilator command with `--lint-only -Wwarn-UNOPTFLAT` instead of `--binary` and read the warnings. Many are false alarms at signal level; Vivado's check is the final word.

---

**Next:** [run it on the board](04_fpga_kr260.md), or go straight to [the benchmarks](05_benchmarks.md).
