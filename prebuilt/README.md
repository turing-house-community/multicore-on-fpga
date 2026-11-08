# Prebuilt bitstream for the KR260

Use these files to run programs on an AMD KR260 **without building the FPGA design yourself** (a full Vivado build can take up to an hour).

| File | What it is |
|---|---|
| `cva6_kr260.bit` | the bitstream: two CVA6 cores (RV32IMAC) with MSI-coherent L1 caches and conditional access, 50 MHz |
| `cva6_kr260.xsa` | the exported hardware platform; `kr260_run.sh` takes `psu_init.tcl` (the ARM-side setup) from it |
| `reports/impl_utilization.rpt` | resources used (LUTs, registers, block RAM) |
| `reports/impl_utilization_hier.rpt` | the same, per module (e.g. `ca_tag_set`, `cc_bus`) |
| `reports/impl_timing_summary.rpt` | timing: WNS +2.390 ns at 50 MHz, so timing is met |

**Built from:** the `cva6` submodule at the commit this repository pins (`11ed1527`, branch `ca-snoop`). All 230 RTL files Vivado used were compared with that commit and are identical. Vivado 2023.2, part `xck26-sfvc784-2LV-c`, board `kr260_som:part0:1.1`, built 2026-11-01.

| sha256 | file |
|---|---|
| `641514560e3a60881abf68f244d2f716962ee29d32e17ba0ac972ef147c99f1d` | `cva6_kr260.bit` |
| `5d6fc4a92ff94fcb0ea010f90e10cc49525baedf073a5cdfb0eb6e83beb0c85e` | `cva6_kr260.xsa` |

## How to use them
`kr260_run.sh` expects both files in `$KR260_WIN_DIR/out/`:
```bash
export KR260_WIN_DIR=/mnt/d/cva6_kr260          # any folder on the Windows side, as a WSL path
mkdir -p $KR260_WIN_DIR/out
cp prebuilt/cva6_kr260.bit prebuilt/cva6_kr260.xsa $KR260_WIN_DIR/out/
```
Then follow [docs/04_fpga_kr260.md](../docs/04_fpga_kr260.md#3-run-a-program).

**If you change the RTL**, this bitstream no longer matches. Build a new one ([docs/04_fpga_kr260.md](../docs/04_fpga_kr260.md#2-build-the-bitstream-optional)) and, once it works, replace the files here and update this README.
