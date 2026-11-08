# 0. Getting started: tools and first build

This page takes you from an empty machine to a working setup. Do the steps in order. Each one ends with a check, so you know it worked before you move on.

**What you need:**

| | Needed for | Required? |
|---|---|---|
| A Linux shell (we used **WSL2 on Windows**, Ubuntu 26.04) | everything | yes |
| About 25 GB free disk, 16 GB RAM | building the full-core model | yes |
| RISC-V GCC toolchain | compiling test programs | yes |
| Verilator 5.x | all simulations | yes |
| Spike (built from the repo) | full-core simulation only | for [step 3 of the simulation guide](03_simulation.md#3-the-full-processor) |
| Vivado 2023.2 (Windows) and an AMD KR260 board | running on the FPGA | only for [the FPGA guide](04_fpga_kr260.md) |

> **New to all this?** You can do everything in [the simulation guide](03_simulation.md) without a board. Start there, and read [the background](01_background.md) while things compile.

---

## Step 1: a Linux shell

**On Windows**, install WSL2 with Ubuntu. In PowerShell (as administrator):
```powershell
wsl --install -d Ubuntu
```
Restart, open "Ubuntu" from the Start menu, and create a user.

> **Important:** keep the repository inside the Linux file system, for example `~/multicore-on-fpga`, **not** under `/mnt/c/...`. Builds on `/mnt/c` are 10× slower or worse.

**On native Linux** (Ubuntu/Debian), nothing to do. Only the FPGA scripts assume WSL; [the FPGA guide](04_fpga_kr260.md#using-native-linux-instead-of-wsl) says what to change.

Install the basic packages:
```bash
sudo apt update
sudo apt install -y build-essential git python3 python3-venv curl wget \
  autoconf automake autotools-dev libtool cmake ninja-build bison flex help2man \
  device-tree-compiler libelf-dev libfl-dev libboost-all-dev ccache perl \
  zlib1g-dev libgoogle-perftools-dev numactl gtkwave
```

## Step 2: clone this repository (with the CVA6 code)

The hardware code lives in our CVA6 fork, which this repository includes as the submodule `cva6/`. CVA6 itself has many submodules, so clone **recursively**:
```bash
cd ~
git clone --recursive https://github.com/turing-house-community/multicore-on-fpga.git
cd multicore-on-fpga/cva6
git status          # should say: HEAD detached at <commit>, nothing to commit
```
If you forgot `--recursive`:
```bash
git submodule update --init --recursive
```

From here on, **all commands run inside `multicore-on-fpga/cva6`** unless stated otherwise.

## Step 3: the RISC-V GCC toolchain

We used the riscv-collab prebuilt toolchain, release 2023.11.08 (GCC 13.2). It builds 32-bit programs too (with `-march=rv32... -mabi=ilp32`).
```bash
mkdir -p ~/tools && cd ~/tools
wget https://github.com/riscv-collab/riscv-gnu-toolchain/releases/download/2023.11.08/riscv64-elf-ubuntu-22.04-gcc-nightly-2023.11.08-nightly.tar.gz
tar xf riscv64-elf-ubuntu-22.04-gcc-nightly-2023.11.08-nightly.tar.gz   # creates ~/tools/riscv
echo 'export RISCV=$HOME/tools/riscv' >> ~/.bashrc
echo 'export PATH=$RISCV/bin:$PATH'  >> ~/.bashrc
source ~/.bashrc
```
**Check:**
```bash
riscv64-unknown-elf-gcc --version     # riscv64-unknown-elf-gcc () 13.2.0
```

## Step 4: Verilator

Two versions are used, for historical reasons:

| Version | Used for | How to get it |
|---|---|---|
| **5.032** (or newer 5.x) | cache testbenches, FPGA-exact simulation, lint | your package manager, or build from source |
| **5.008** with CVA6's patch | the full-core testharness (`make verilate`) | CVA6's install script |

**4a. Verilator 5.032.** On Ubuntu 25.04 or newer, `apt` has it:
```bash
sudo apt install -y verilator
verilator --version        # Verilator 5.032 ... or newer
```
If your `apt` version is older than 5.0 (e.g. Ubuntu 22.04 ships 4.038), build it from source:
```bash
git clone https://github.com/verilator/verilator.git -b v5.032 ~/tools/verilator-src
cd ~/tools/verilator-src && autoconf && ./configure && make -j$(nproc) && sudo make install
```

**4b. Verilator 5.008 for the full core** (takes about 15 minutes):
```bash
cd ~/multicore-on-fpga/cva6
export VERILATOR_INSTALL_DIR=$PWD/tmp/verilator-v5.008
NUM_JOBS=$(nproc) bash verif/regress/install-verilator.sh
$VERILATOR_INSTALL_DIR/bin/verilator --version    # Verilator 5.008
```

## Step 5: Spike and the RISC-V tests (for the full core)

The full-core testharness links against Spike's libraries, and the standard ISA tests are cloned from riscv-tests.
```bash
cd ~/multicore-on-fpga/cva6
export SPIKE_INSTALL_DIR=$PWD/tools/spike
NUM_JOBS=$(nproc) bash verif/regress/install-spike.sh
bash verif/regress/install-riscv-tests.sh                 # clones into verif/tests/riscv-tests
make -C verif/tests/riscv-tests/isa XLEN=32 RISCV_PREFIX=riscv64-unknown-elf- \
  rv32ui rv32um rv32ua rv32uc rv32mi rv32si
```
**If the Spike build fails** on a recent Ubuntu, these three workarounds are what we needed:

| Error | Fix |
|---|---|
| CMake complains about `cmake_minimum_required` / policy version | `export CMAKE_POLICY_VERSION_MINIMUM=3.5` and rerun |
| yaml-cpp fails with `uint16_t was not declared` | rerun with `NUM_JOBS=1 CXXFLAGS="-include cstdint"` |
| `svdpi.h: No such file` | `export CPATH=/usr/share/verilator/include/vltstd` (path of your Verilator 5.032 install) |

**Check:**
```bash
ls tools/spike/lib/libfesvr.*                             # exists
ls verif/tests/riscv-tests/isa/rv32ui-p-add               # exists
```

## Step 6: set up the environment in every new shell

Put this in a file, for example `~/multicore-on-fpga/env.sh`, and `source` it in each new terminal:
```bash
cd ~/multicore-on-fpga/cva6
export RISCV=$HOME/tools/riscv
export PATH=$RISCV/bin:$PATH
export SPIKE_INSTALL_DIR=$PWD/tools/spike
export VERILATOR_INSTALL_DIR=$PWD/tmp/verilator-v5.008
```
Do **not** put Verilator 5.008 first in `PATH` globally. The full-core `make` finds it through `VERILATOR_INSTALL_DIR`, and the other commands use Verilator 5.032 from `/usr/bin`.

## Step 7: your first run (2 minutes)

This builds and runs the two-cache testbench: two MSI caches, the coherence bus and the conditional-access unit, driven by random traffic and checked against a reference model.
```bash
mkdir -p build                    # Verilator needs the parent folder to exist
verilator --binary --timing -j 8 -Wno-fatal -Wno-lint -Wno-style -Wno-UNOPTFLAT \
  --top-module std_nbdcache_2core_tb -Mdir build/tb2 -f core/cache_subsystem/test/std_nbdcache_2core_tb.f
build/tb2/Vstd_nbdcache_2core_tb +seed=1 +nrandom=1500
```
It prints `PASSED`, followed by Verilator's short simulation report. If it does, your setup works. Continue with [the simulation guide](03_simulation.md).

## Optional: Vivado and the board

Only needed to build a bitstream or run on the KR260. See [the FPGA guide](04_fpga_kr260.md). A prebuilt bitstream is in [`prebuilt/`](../prebuilt/), so you can run programs on a board without building one.
