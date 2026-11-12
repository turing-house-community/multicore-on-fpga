# 4. Running on the AMD KR260 FPGA

This page puts the two-core system on a real board and runs programs on it. You need an **AMD Kria KR260** starter kit and a Windows PC with **Vivado 2023.2**. Everything else runs in WSL, as in [getting started](00_getting_started.md).

There is **no operating system** on the board. The ARM cores on the chip only provide DDR memory; our two RISC-V cores in the FPGA fabric run bare-metal programs, which the PC loads over USB (JTAG).

## How it works

```
 PL (FPGA)                                                    PS (ARM side)
 +-------------------------------------------------------+    +--------------+
 | core 0 --cut--+                                       |    |              |
 |               +-- arbiter --> L2 --> addr remap --> HP0 -->| DDR          |
 | core 1 --cut--+        |                              |    | (cores use   |
 |   |      |             +-------> mailbox BRAM <-------+----| 0x4000_0000+)|
 |   +--cc_directory (coherence)    (8 KB, shared)       |    |              |
 |                                  run bit (GPIO) <-----+----| JTAG/debug   |
 +-------------------------------------------------------+    +--------------+
```

| Core address | What | PS (xsdb) address |
|---|---|---|
| `0x8000_0000 – 0xBFFF_FFFF` | DDR, cacheable; programs are linked here | `0x4000_0000` |
| `0xC000_0000` | **mailbox**, uncached (results, `tohost`) | `0xA000_0000` |
| – | **run bit**: cores run while it is 1 | `0xA001_0000` |

The shared L2 (256 KiB) caches DDR only; the mailbox passes through it. It is cleared every time a program is loaded, because the ARM side writes the new program straight into DDR.

**Why a mailbox?** The caches are write-back, so a result a core stores to DDR may stay in its cache, invisible to the PC. The mailbox is uncached: writes go straight out. The linker script `sw/link_kr260.ld` therefore places `tohost` at `0xC000_0000`, and benchmarks write their numbers to mailbox words 16 and up.

**A run, step by step** (`scripts/run_test.tcl`, executed by AMD's `xsdb` tool):
1. Reset the board, program the FPGA with the bitstream, initialize the ARM side (`psu_init`). Only on the first run, or when forced.
2. Hold the cores (run bit = 0), clear the mailbox, copy the program image into DDR.
3. Set the run bit. Both cores start at `0x8000_0000` and read their hart ID.
4. Poll `tohost` until the program writes it: `1` = pass, `(code << 1) | 1` = fail with that code. Print `RESULT` and the mailbox words (`MBOX`).

**Resources and timing** (from [`prebuilt/reports/`](../prebuilt/reports/)):

| Item | Value |
|---|---|
| Clock | 50 MHz (timing met with 2.86 ns to spare) |
| LUTs | 78,120 of 117,120 (67%) |
| Registers | 46,128 of 234,240 (20%) |
| Block RAM | 78 of 144 tiles (54%) |
| UltraRAM | 10 of 64 |
| Per core | about 25K LUTs |
| CA unit (`ca_tag_set`) | about 1,000 LUTs and 540 registers per core, no memory blocks |
| `bcafail` | 17 LUTs in total |
| Directory (`cc_directory`) | 676 LUTs, 2 UltraRAM |
| Shared L2 (`axi_l2_cache`) | 18,508 LUTs, 8 UltraRAM, 8 small block RAMs |

---

## 1. One-time setup

**On Windows:**
1. Install **Vivado ML 2023.2** (the free *Standard* edition supports the KR260's K26 chip). Default path `C:\Xilinx\Vivado\2023.2`; we used `D:\Vivado\2023.2`. Tick **"Install cable drivers"**, or run `<Vivado>\data\xicom\cable_drivers\nt64\install_drivers_wrapper.bat` afterwards as administrator.
2. Install the **KR260 board files**: in Vivado, *Tools → Vivado Store → Boards*, search "KR260", install. Without them the build fails with "board_part kr260_som... not found".
3. Create a working folder on a Windows drive, e.g. `D:\cva6_kr260`. Builds and runs happen there because Vivado on Windows cannot work inside the WSL file system efficiently.

**The board:**
1. Connect the 12 V power supply, and the **micro-USB port** (JTAG + UART) to the PC. No SD card is needed.
2. Power on. Windows should show the FTDI JTAG device (check *Device Manager*, or in Vivado: *Open Hardware Manager → Open Target → Auto Connect* shows `xck26`).

**In WSL**, tell the scripts where things are (add to your `env.sh`):
```bash
export KR260_WIN_DIR=/mnt/d/cva6_kr260                     # the Windows folder, as a WSL path
export VIVADO_BAT='D:\Vivado\2023.2\bin\vivado.bat'       # adjust to your install
export XSDB_BAT='D:\Vivado\2023.2\bin\xsdb.bat'
export OBJCOPY=riscv64-unknown-elf-objcopy
```

## 2. Build the bitstream (optional)

Skip this and use the **prebuilt bitstream**:
```bash
mkdir -p $KR260_WIN_DIR/out && cp ../prebuilt/cva6_kr260.{bit,xsa} $KR260_WIN_DIR/out/
```
(run from `multicore-on-fpga/cva6`). Build it yourself only if you changed the RTL:

1. **Simulate the exact FPGA design first** and check for combinational loops ([simulation guide, level 4](03_simulation.md#4-the-exact-fpga-design)). A Vivado build can take an hour; Verilator finds most mistakes in minutes.
2. Start the build:
   ```bash
   corev_apu/fpga/kr260/kr260_build.sh            # synthesis + implementation + bitstream
   corev_apu/fpga/kr260/kr260_build.sh synth      # synthesis only (faster first check)
   ```
   The script copies the sources to `$KR260_WIN_DIR/src`, then starts Vivado **detached** on Windows, so the build survives closing the terminal.
3. Watch progress: `tail -f $KR260_WIN_DIR/build.log`. The last line becomes `BUILD_DONE impl WNS=...` or `BUILD_FAILED ...`. It takes up to an hour, depending on your PC.
4. Outputs in `$KR260_WIN_DIR/out/`: `cva6_kr260.bit`, `cva6_kr260.xsa`, and `reports/` (utilization, timing). Check that WNS is positive in `reports/impl_timing_summary.rpt`.

## 3. Run a program

Build the test programs, linked for the board:
```bash
corev_apu/fpga/kr260/sw/build_tests.sh build/board
```
Run one. The **first run after power-up** programs the FPGA:
```bash
KR260_PROGRAM=1 corev_apu/fpga/kr260/kr260_run.sh build/board/ca_2core.elf 30
```
**Expected:**
```
LOADED 4872 bytes
RESULT PASS after 21 ms
MBOX 0 0 0 ...
```
Later runs skip the FPGA programming and take a few seconds:
```bash
corev_apu/fpga/kr260/kr260_run.sh build/board/msi_2core.elf 30
corev_apu/fpga/kr260/kr260_run.sh build/board/bcafail.elf 30
corev_apu/fpga/kr260/kr260_run.sh build/board/controls/plain_reads.elf 30    # must FAIL code 30
corev_apu/fpga/kr260/kr260_run.sh build/board/controls/plain_lock.elf 30     # must FAIL code 32
corev_apu/fpga/kr260/kr260_run.sh build/board/controls/need_revoked.elf 30   # PASS
```
Arguments: `kr260_run.sh <program.elf> [timeout in seconds] [seed]`. The seed is written to mailbox word 2 for programs that use one.

**All 73 ISA tests on the board:**
```bash
for t in build/board/isa/*; do
  echo "$(basename $t) $(timeout 100 corev_apu/fpga/kr260/kr260_run.sh $t 10 | grep -a RESULT)"
done | tee board_isa.txt | grep -v PASS
```
**Expected:** only `rv32mi-p-breakpoint` fails, exactly as in simulation.

### Our results
| Test | Board | Simulation |
|---|---|---|
| `msi_2core` | PASS, 10/10 runs | PASS |
| `ca_2core` | PASS, 10/10 runs | PASS |
| `bcafail` | PASS; 2,000 rounds, every outcome equal to the CSR | PASS |
| `plain_reads` (plain loads instead of `cread`) | FAIL code 30, as intended | same |
| `plain_lock` (plain store instead of `cwrite`) | FAIL code 32, as intended | same |
| `need_revoked` | PASS | same |
| rv32 ISA tests | 72/73 | 72/73 |

**No difference between the board and simulation was ever found.**

## 4. Writing your own program
- Start from `corev_apu/fpga/kr260/sw/bench/micro.c` (C) or `verif/tests/custom/ca_2core/ca_2core.S` (assembly).
- C programs: link with `sw/bench/crt.S`, which gives each hart a stack and calls `main(hartid)`; hart 0's return value becomes `tohost` (return 1 for pass). Copy the compiler flags from `sw/bench/build_micro.sh`.
- Report numbers by writing to `((volatile uint32_t *)0xC0000000)[16 + i]`; they appear on the `MBOX` line.
- Read cycle counts with `csrr %0, mcycle`. At 50 MHz, 1 cycle = 20 ns.
- Put shared variables that must start at a known value (flags, barriers) into `.data`, e.g. `__attribute__((section(".data")))`: `.bss` is not part of the loaded image and `crt.S` does not clear it, so it may hold leftovers from the previous run.

## Troubleshooting
| Symptom | Cause and fix |
|---|---|
| `xsdb` prints **"PL reset is active"**, or `RESULT TIMEOUT` right after a power cycle | The board was reset but the script thinks the FPGA is still programmed. Rerun with `KR260_PROGRAM=1`. |
| `RESULT TIMEOUT` on a program that should finish | The program hangs or did not write `tohost`. Simulate it first ([level 4](03_simulation.md#4-the-exact-fpga-design)). |
| No `RESULT` line at all | A JTAG hiccup. Look at `$KR260_WIN_DIR/run/xsdb.log`, unplug/replug USB, rerun. `run_batch.sh` retries such runs automatically. |
| Vivado stops with **DRC LUTLP-1** (combinational loop) | Find it in Verilator with `-Wwarn-UNOPTFLAT` ([simulation guide](03_simulation.md#4-the-exact-fpga-design)). We hit two; see [challenges](07_challenges.md). |
| `cmd.exe` or `powershell.exe` not found | Not running in WSL, or Windows interop is disabled. See below. |
| Board part not found | Install the KR260 board files (step 1). |

## Using native Linux instead of WSL
The scripts call Windows Vivado through `cmd.exe` / `powershell.exe`. On a Linux PC with Vivado for Linux:
- **Build:** `vivado -mode batch -source corev_apu/fpga/kr260/scripts/build.tcl -tclargs <src> <out> impl`, where `<src>` is a folder with the RTL at its repository paths plus `filelist.f`. The first half of `kr260_build.sh` shows how to create it; or simply pass the `cva6` folder itself after writing `filelist.f` into it with `scripts/gen_filelist.sh`.
- **Run:** `xsdb corev_apu/fpga/kr260/scripts/run_test.tcl <bit> <psu_init.tcl> <program.bin> [timeout] [skip_fpga] [seed]`. `kr260_run.sh` shows how to get `psu_init.tcl` out of the `.xsa` and the `.bin` out of the ELF.

Turning this into a `kr260_run_linux.sh` is a good first contribution (🙋 in [PLAN.md](../PLAN.md)).

---

**Next:** [benchmarks](05_benchmarks.md).
