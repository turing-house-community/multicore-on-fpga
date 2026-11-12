# Prebuilt bitstream for the KR260

Use these files to run programs on an AMD KR260 **without building the FPGA design yourself** (a full Vivado build can take up to an hour).

| File | What it is |
|---|---|
| `cva6_kr260.bit` | the bitstream: two CVA6 cores (RV32IMAC) with MSI-coherent L1 caches (directory), conditional access with `bcafail`, and a shared 256 KiB L2, 50 MHz |
| `cva6_kr260.xsa` | the exported hardware platform; `kr260_run.sh` takes `psu_init.tcl` (the ARM-side setup) from it |
| `reports/impl_utilization.rpt` | resources used (LUTs, registers, block RAM) |
| `reports/impl_utilization_hier.rpt` | the same, per module (e.g. `ca_tag_set`, `cc_directory`, `axi_l2_cache`) |
| `reports/impl_timing_summary.rpt` | timing: WNS +2.863 ns at 50 MHz, so timing is met |

**Built from:** the `cva6` submodule at commit `29be58b2` (branch `ca-snoop`); the RTL has not changed since. All 243 RTL files Vivado used were compared with that commit and are identical. Vivado 2023.2, part `xck26-sfvc784-2LV-c`, board `kr260_som:part0:1.1`, built 2026-11-12. It uses 78,120 LUTs (67%), 78 block RAMs and 10 UltraRAMs.

| sha256 | file |
|---|---|
| `48bb793f61c804aa489a07cef356970cae95936995979eeaee64967c13967f4e` | `cva6_kr260.bit` |
| `a7f16259bf916287d40b2b18f2c7377aaa4a1fe45e6fec40dfb0a922e6d99b44` | `cva6_kr260.xsa` |

## How to use them
`kr260_run.sh` expects both files in `$KR260_WIN_DIR/out/`:
```bash
export KR260_WIN_DIR=/mnt/d/cva6_kr260          # any folder on the Windows side, as a WSL path
mkdir -p $KR260_WIN_DIR/out
cp prebuilt/cva6_kr260.bit prebuilt/cva6_kr260.xsa $KR260_WIN_DIR/out/
```
Then follow [docs/04_fpga_kr260.md](../docs/04_fpga_kr260.md#3-run-a-program).

**If you change the RTL**, this bitstream no longer matches. Build a new one ([docs/04_fpga_kr260.md](../docs/04_fpga_kr260.md#2-build-the-bitstream-optional)) and, once it works, replace the files here and update this README.

**Older bitstreams.** The first version (snooping bus, no L2, no `bcafail`) is in the git history of this folder, at the commit "Add the prebuilt KR260 bitstream and the FPGA guide". The results in `results/no_l2/` and `results/phase5/` were measured on older designs; see [results/README.md](../results/README.md).
