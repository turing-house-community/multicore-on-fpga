"""Figures for the visual (diagram-first) poster. Usage: python3 make_figs_visual.py <out dir>
Values are the measured ones from results/ (see docs/06_results.md)."""
import sys
out = sys.argv[1]
F = "font-family=\"'Times New Roman', Times, serif\""
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, GREEN, YEL, RED, NAVY = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948", "#1f3a5f"
L_BLUE, L_ORANGE, L_GREEN, L_RED, L_GREY, L_YEL = "#e8f1fc", "#fdece4", "#e3f5ee", "#fbe1e1", "#f3f3f0", "#fdf3d9"

def svg(w, h, body):
    arrow = ('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" '
             f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK2}"/></marker></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {F}>'
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>{arrow}{body}</svg>')

def text(x, y, s, size=40, weight=400, fill=INK, anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{s}</text>'

def rect(x, y, w, h, fill, stroke=None, sw=4, rx=8, dash=None):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{st}{d}/>'

def arrow(x1, y1, x2, y2, color=INK2, sw=5, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{d} marker-end="url(#a)"/>'

def lines(x, y, rows, size=36, fill=INK2, anchor="start", gap=1.25, weight=400):
    return "".join(text(x, y + i * size * gap, r, size, weight, fill, anchor) for i, r in enumerate(rows))

# ---------------- existing approaches: HP vs EBR ----------------
def approaches():
    W, H = 1400, 560
    b = ""
    # hazard pointers card
    b += rect(10, 10, 680, 430, L_BLUE, BLUE)
    b += text(40, 70, "Hazard pointers", 46, 700, BLUE)
    for i, (t, x) in enumerate([("announce p", 40), ("fence", 270), ("read *p", 470)]):
        fill = L_YEL if t == "fence" else "#ffffff"
        b += rect(x, 110, 190 if t != "fence" else 160, 90, fill, INK2, 3)
        b += text(x + (95 if t != "fence" else 80), 168, t, 36, 600, INK, "middle")
    b += arrow(232, 155, 266, 155) + arrow(432, 155, 466, 155)
    b += text(345, 245, "on every pointer read", 32, 400, MUTED, "middle")
    b += lines(40, 320, ["Problem: a memory fence on", "every read slows traversals"], 38, RED, weight=600)
    # epoch card
    b += rect(710, 10, 680, 430, L_ORANGE, ORANGE)
    b += text(740, 70, "Epoch-based (EBR)", 46, 700, ORANGE)
    for i in range(6):
        b += rect(750 + i * 62, 110 + (i % 2) * 12, 52, 52, "#ffffff", ORANGE, 3, 4)
    b += text(1150, 148, "removed,", 34, 600, INK)
    b += text(1150, 188, "waiting", 34, 600, INK)
    b += text(1045, 245, "freed only after every thread passes a checkpoint", 30, 400, MUTED, "middle")
    b += lines(740, 320, ["Problem: unfreed memory piles", "up, without bound if a thread stalls"], 38, RED, weight=600)
    # common issue bar
    b += rect(10, 460, 1380, 90, NAVY, rx=8)
    b += text(700, 520, "Both delay reclamation: they trade speed against memory", 42, 700, "#ffffff", "middle")
    return svg(W, H, b)

# ---------------- how a write revokes access ----------------
def revoke():
    W, H = 1400, 600
    b = ""
    b += text(20, 50, "Core 1 (remover)", 38, 700, ORANGE)
    b += text(20, 560, "Core 0 (reader)", 38, 700, BLUE)
    steps_top = [(20, "1. writes node N", "unlink / mark"), (480, "2. needs line in M", "GetM on the bus")]
    for x, t1, t2 in steps_top:
        b += rect(x, 75, 420, 130, L_ORANGE, ORANGE)
        b += text(x + 210, 130, t1, 38, 700, INK, "middle") + text(x + 210, 180, t2, 32, 400, INK2, "middle")
    b += arrow(442, 140, 476, 140)
    # bus
    b += rect(20, 255, 1360, 90, GREEN)
    b += text(700, 312, "coherence bus: snoop GetM(N) to the other cache", 38, 700, "#ffffff", "middle")
    b += arrow(690, 207, 690, 252)
    steps_bot = [(20, "3. copy of N invalidated", "it was tagged by cread"),
                 (480, "4. CA unit: access revoked", "accessRevokedBit = 1"),
                 (940, "5. next cread fails", "reader retries, never uses N")]
    for i, (x, t1, t2) in enumerate(steps_bot):
        fill, st = (L_GREEN, GREEN) if i == 2 else (L_BLUE, BLUE)
        b += rect(x, 395, 420, 130, fill, st)
        b += text(x + 210, 450, t1, 36, 700, INK, "middle") + text(x + 210, 500, t2, 32, 400, INK2, "middle")
    b += arrow(230, 348, 230, 391) + arrow(442, 460, 476, 460) + arrow(902, 460, 936, 460)
    # free immediately
    b += rect(940, 75, 440, 130, L_ORANGE, ORANGE)
    b += text(1160, 130, "free(N) immediately", 38, 700, INK, "middle") + text(1160, 180, "no waiting, no scan", 32, 400, INK2, "middle")
    b += arrow(902, 140, 936, 140)
    return svg(W, H, b)

# ---------------- instructions ----------------
def instrs():
    W, H = 1400, 250
    b = ""
    items = [("cread", "load and watch the line"), ("cwrite", "store if nothing watched changed"),
             ("untagOne", "stop watching one line"), ("untagAll", "stop watching all, clear flags")]
    for i, (n, d) in enumerate(items):
        x = 10 + i * 348
        b += rect(x, 10, 332, 230, L_GREY, AXIS, 3)
        b += f'<text x="{x+166}" y="90" font-size="46" font-weight="700" fill="{NAVY}" text-anchor="middle" font-family="Courier New, monospace">{n}</text>'
        words = d.split()
        mid = (len(words) + 1) // 2
        b += lines(x + 166, 155, [" ".join(words[:mid]), " ".join(words[mid:])], 32, INK2, "middle")
    return svg(W, H, b)

# ---------------- why an FPGA ----------------
def why():
    W, H = 1400, 330
    b = ""
    items = [("Latency?", "how fast are the", "CA instructions?"), ("Coherence cost?", "what do the events", "CA uses cost?"),
             ("Hardware cost?", "how much area, logic", "and memory?")]
    for i, (q, d1, d2) in enumerate(items):
        x = 10 + i * 464
        b += rect(x, 10, 448, 310, L_YEL, YEL)
        b += text(x + 224, 90, q, 48, 700, INK, "middle")
        b += lines(x + 224, 170, [d1, d2], 36, INK2, "middle")
        b += text(x + 224, 290, "measured on the board", 30, 600, "#8a5d00", "middle")
    return svg(W, H, b)

# ---------------- challenges ----------------
def challenges():
    W, H = 1400, 600
    b = ""
    tiles = [("Choosing a base", ["OpenPiton dropped: old CVA6,", "heavy, needs an L1.5 adapter"]),
             ("Fitting the FPGA", ["limited LUTs: moved to", "32-bit RV32 cores"]),
             ("Deadlock freedom", ["a cache answers a snoop", "without needing the bus"]),
             ("Atomic cwrite", ["runs at commit, holding", "the line exclusively"]),
             ("Speculation", ["CA ops recorded at issue,", "applied only at commit"]),
             ("Learning curve", ["CVA6, KR260 and Vivado,", "coherence, reclamation"])]
    for i, (t, d) in enumerate(tiles):
        x, y = 10 + (i % 2) * 700, 10 + (i // 2) * 197
        b += rect(x, y, 680, 182, L_GREY, AXIS, 3)
        b += rect(x, y, 14, 182, NAVY, rx=4)
        b += text(x + 40, y + 56, t, 42, 700, NAVY)
        b += lines(x + 40, y + 108, d, 34, INK2)
    return svg(W, H, b)

# ---------------- verification ladder ----------------
def verification():
    W, H = 1400, 590
    b = ""
    rows = [("One cache", "random traffic vs reference memory", "300 / 300", L_BLUE, BLUE),
            ("Two caches + bus + CA", "models of MSI and of the CA rules", "400 / 400", L_BLUE, BLUE),
            ("Injected bugs", "does the testbench catch them?", "26 / 27", L_YEL, YEL),
            ("Full processor", "RISC-V ISA test suites", "72 / 73", L_GREEN, GREEN),
            ("KR260 board", "two-core programs, same as simulation", "20 / 20", L_ORANGE, ORANGE)]
    for i, (t, d, n, fill, st) in enumerate(rows):
        y = 10 + i * 116
        indent = i * 30
        b += rect(10 + indent, y, 1380 - indent, 104, fill, st)
        b += text(40 + indent, y + 46, t, 40, 700, INK)
        b += text(40 + indent, y + 88, d, 32, 400, INK2)
        b += text(1360, y + 72, n, 60, 700, st, "end")
    return svg(W, H, b)

# ---------------- headline numbers ----------------
def headline():
    W, H = 1400, 300
    b = ""
    items = [("0", "nodes left unfreed", "(epochs: ~140)", GREEN), ("1.33×", "throughput under", "high contention", ORANGE),
             ("4.5%", "of a core for the", "CA unit, no BRAM", BLUE)]
    for i, (n, d1, d2, c) in enumerate(items):
        x = 10 + i * 464
        b += rect(x, 10, 448, 280, "#ffffff", c, 5)
        b += text(x + 224, 135, n, 110, 700, c, "middle")
        b += lines(x + 224, 205, [d1, d2], 34, INK2, "middle")
    return svg(W, H, b)

# ---------------- measured costs: two bar charts ----------------
def hbars(x0, y0, w, title, items, vmax, color, unit="cycles"):
    b = text(x0, y0, title, 40, 700, INK)
    lab_w = 330
    for i, (lab, v, hl) in enumerate(items):
        y = y0 + 40 + i * 78
        bw = (w - lab_w - 120) * v / vmax
        b += text(x0 + lab_w - 15, y + 44, lab, 32, 600 if hl else 400, INK, "end")
        b += rect(x0 + lab_w, y + 10, max(bw, 4), 50, color if hl else AXIS, rx=3)
        b += text(x0 + lab_w + max(bw, 4) + 12, y + 46, f"{v:g}", 32, 700, INK)
    return b

def measured():
    W, H = 1400, 620
    b = hbars(10, 45, 690, "Instruction latency (cycles)",
              [("load", 1, False), ("cread", 2, True), ("cread + check", 7, True), ("amoswap", 14, False),
               ("cread + cwrite", 17, True), ("lr + sc", 24, False)], 24, ORANGE)
    b += f'<line x1="705" y1="20" x2="705" y2="610" stroke="{GRID}" stroke-width="3"/>'
    b += hbars(720, 45, 680, "Coherence cost (cycles per line)",
               [("read hit", 6.5, False), ("read miss", 53.7, False), ("upgrade S to M", 49.5, False),
                ("+ invalidate copy", 50.4, True), ("remote dirty miss", 96.9, True), ("core-to-core", 150.6, True)], 151, GREEN)
    b += text(720, 600, "invalidating the other copy adds only ~1 cycle", 32, 600, "#0d6b4a")
    return svg(W, H, b)


# ---------------- architecture, large type ----------------
def architecture_big():
    W, H = 1400, 860
    b = text(10, 48, "AMD KR260 FPGA, 50 MHz", 40, 700, INK)
    def blk(x, y, w, h, fill, t1, t2, stroke=None):
        r = rect(x, y, w, h, fill, stroke, 3) if stroke else rect(x, y, w, h, fill)
        return r + text(x + w / 2, y + h * 0.45, t1, 36, 700, INK, "middle") + text(x + w / 2, y + h * 0.82, t2, 29, 400, INK2, "middle")
    for i, x in enumerate((10, 710)):
        b += rect(x, 75, 680, 470, "#ffffff", BLUE, 4)
        b += text(x + 25, 128, f"CVA6 core {i} (RV32IMAC)", 38, 700, BLUE)
        b += blk(x + 20, 150, 640, 118, L_BLUE, "In-order pipeline", "+ cread, cwrite, untagOne, untagAll")
        b += blk(x + 20, 283, 640, 118, L_ORANGE, "CA unit (new)", "8-line tag set, revoked on snoop / evict / trap")
        b += blk(x + 20, 416, 640, 118, L_GREEN, "L1 data cache, MSI (new)", "write-back 32 KiB, atomics in the L1")
        b += f'<line x1="{x+340}" y1="547" x2="{x+340}" y2="588" stroke="{INK2}" stroke-width="5" marker-start="url(#a)" marker-end="url(#a)"/>'
    b += rect(10, 590, 1380, 118, GREEN)
    b += text(700, 642, "Coherence bus (new): snooping, one transaction at a time", 38, 700, "#ffffff", "middle")
    b += text(700, 690, "GetS / GetM / PutM; dirty data written back before the grant", 30, 400, "#ffffff", "middle")
    b += arrow(450, 710, 450, 745)
    b += blk(10, 750, 880, 105, L_GREY, "AXI4 to PS DDR4 memory (no L2)", "programs and data", AXIS)
    b += blk(910, 750, 480, 105, L_GREY, "Mailbox + JTAG host", "load programs, read results", AXIS)
    return svg(W, H, b)

# ---------------- throughput, large type ----------------
def throughput_big():
    data = {"Read-only (0% updates)": {"list": (.34, .25, 1.00), "BST": (.64, .56, 1.00), "stack": (.37, .50, .92), "hash": (.49, .48, .99)},
            "Write-heavy (100% updates)": {"list": (.43, .33, 1.00), "BST": (.78, .65, .90), "stack": (1.33, 1.09, 1.05), "hash": (.98, .85, .99)}}
    cols = [("ca", ORANGE), ("hazard pointers", GREEN), ("epochs (qsbr)", YEL)]
    W, H = 1400, 760
    top, bot, ymax = 210, 670, 1.5
    Y = lambda v: bot - (bot - top) * v / ymax
    b = text(10, 46, "Throughput relative to never freeing (2 cores)", 40, 700, INK)
    lx = 10
    for name, c in cols:
        b += rect(lx, 72, 34, 34, c, rx=4) + text(lx + 46, 102, name, 34, 400, INK)
        lx += 46 + len(name) * 17 + 40
    b += f'<line x1="{lx}" y1="89" x2="{lx+50}" y2="89" stroke="{INK}" stroke-width="4" stroke-dasharray="12 7"/>' + text(lx + 62, 102, "never frees = 1.0", 34, 400, INK)
    for v in (0, .5, 1.0, 1.5):
        b += f'<line x1="95" y1="{Y(v)}" x2="{W-10}" y2="{Y(v)}" stroke="{GRID}" stroke-width="2"/>'
        b += text(82, Y(v) + 11, f"{v:.1f}", 30, 400, MUTED, "end")
    pw = (W - 110 - 30) / 2
    for pi, (title, groups) in enumerate(data.items()):
        px = 105 + pi * (pw + 30)
        b += text(px + pw / 2, top - 50, title, 36, 700, INK, "middle")
        b += f'<line x1="{px}" y1="{Y(1)}" x2="{px+pw}" y2="{Y(1)}" stroke="{INK}" stroke-width="4" stroke-dasharray="12 7"/>'
        gw, bw = pw / 4, 44
        for gi, (g, vals) in enumerate(groups.items()):
            gx = px + gi * gw + (gw - 3 * bw - 6) / 2
            for bi, v in enumerate(vals):
                x, y = gx + bi * (bw + 3), Y(v)
                b += rect(x, y, bw, bot - y, cols[bi][1], rx=3)
                if bi == 0:
                    b += (f'<text x="{x+bw/2}" y="{y-12}" text-anchor="middle" font-size="30" font-weight="700" fill="{INK}" '
                          f'stroke="#ffffff" stroke-width="7" paint-order="stroke">{v:.2f}</text>')
            b += text(px + gi * gw + gw / 2, bot + 50, g, 34, 400, INK2, "middle")
    b += f'<line x1="95" y1="{bot}" x2="{W-10}" y2="{bot}" stroke="{AXIS}" stroke-width="2"/>'
    return svg(W, H, b)

figs = {"architecture_big": (architecture_big(), 1400, 860), "throughput_big": (throughput_big(), 1400, 760),
        "approaches": (approaches(), 1400, 560), "revoke_flow": (revoke(), 1400, 600), "instructions": (instrs(), 1400, 250),
        "challenges": (challenges(), 1400, 600), "verification": (verification(), 1400, 590),
        "headline": (headline(), 1400, 300), "measured": (measured(), 1400, 620)}
for n, (s, w, h) in figs.items():
    open(f"{out}/{n}.svg", "w").write(s)
    print(f"{n}:{w},{h}")
