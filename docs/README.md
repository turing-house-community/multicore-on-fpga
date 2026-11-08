# Docs
Everything that helps people understand and learn from this project.

- Tutorials, notes, design explanations, paper summaries: add as .md files here
  (e.g. `docs/how-the-scheduler-works.md`). List them below.
- `demos/`: whatever shows the project at each phase. A screenshot, whiteboard
  photo, short GIF, terminal output, or a 5-line note. Name them launch.*,
  midpoint.*, completion.*. Big videos: upload elsewhere and link in project.yml.

## Index
Read in this order. Each guide ends with a link to the next.

- [00_getting_started.md](00_getting_started.md): install the tools, clone, and do a first two-minute run
- [01_background.md](01_background.md): the problem (use-after-free), existing fixes, Conditional Access, why an FPGA
- [02_design.md](02_design.md): the hardware: MSI caches, the coherence bus, the CA unit, how it fits the pipeline
- [03_simulation.md](03_simulation.md): verify everything in simulation, from one cache to the exact FPGA design
- [04_fpga_kr260.md](04_fpga_kr260.md): build the bitstream (or use the prebuilt one) and run programs on the KR260
- [05_benchmarks.md](05_benchmarks.md): rerun the paper's benchmarks and the micro-benchmarks on the board
- [06_results.md](06_results.md): what we measured: correctness, memory, throughput, latency, coherence cost, area
- [07_challenges.md](07_challenges.md): what was hard, what we decided and why, and a learning path
- [code_map.md](code_map.md): every file we changed in CVA6, and why

Other material:
- `talks/poster.pdf`: the final poster; its LaTeX source is in `talks/poster/`
- `demos/completion.png`, `demos/completion_board_run.txt`: poster preview and sample board output
- `figures/`: figures used by these docs
- The fork carries shorter design notes too: `../cva6/docs/msi_ca_kr260/`
