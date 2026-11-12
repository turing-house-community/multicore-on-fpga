"""Figures for the poster (everything except uaf_steps and problem_with, which
come from make_figs.py).

usage: python3 make_figs_v3.py <out dir>
Writes SVGs; render each one to PNG at 3x in a browser (window size = the SVG's
width x height, listed in <out dir>/v3_sizes.txt).
The numbers are typed in from results/ (board/summary.csv, micro/, and the
Vivado reports in prebuilt/reports/). Some figures it draws are not used by
poster.tex (earlier layouts); they are kept for reuse.
"""
import sys

out = sys.argv[1]
F = "font-family=\"'Times New Roman', Times, serif\""
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, GREEN, YEL, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948"
DKORANGE, NAVY, GREY, BROWN = "#a8431c", "#1f3a5f", "#9a9a94", "#6b2a10"
LTORANGE, DKGREEN, CORE = "#f3a27c", "#0d6b4a", "#7b93b4"
CARD, CARDLINE = "#f6f8fb", "#d5deea"

ARROW = ('<defs>'
         '<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
         f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK2}"/></marker>'
         '<marker id="r" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
         f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{RED}"/></marker>'
         '<marker id="g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
         f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{GREEN}"/></marker>'
         '<marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
         f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker>'
         '<marker id="o" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
         f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{ORANGE}"/></marker>'
         '</defs>')

written = []


PANEL_BG = "#EEF3F9"   # matches \definecolor{statbg} in poster_v3.tex


def save(name, w, h, body, bg="#ffffff"):
    open(f"{out}/{name}.svg", "w").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" {F}>'
        f'<rect width="{w}" height="{h}" fill="{bg}"/>{ARROW}{body}</svg>')
    written.append(f"{name} {w} {h}")


def T(x, y, s, size=26, c=INK, w=None, anchor="start", italic=False):
    fw = f' font-weight="{w}"' if w else ""
    it = ' font-style="italic"' if italic else ""
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" text-anchor="{anchor}"{fw}{it}>{s}</text>'


def box(x, y, w, h, fill, t1, t2="", stroke=None, c2=INK2, s1=30, s2=24, c1=INK, rx=8):
    st = f' stroke="{stroke}" stroke-width="4"' if stroke else ""
    cx = x + w / 2
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{st}/>'
    if t2:
        s += T(cx, y + h * 0.45, t1, s1, c1, 600, "middle") + T(cx, y + h * 0.80, t2, s2, c2, None, "middle")
    else:
        s += T(cx, y + h / 2 + s1 * 0.35, t1, s1, c1, 600, "middle")
    return s


def diamond(cx, cy, w, h, fill, t1, t2, stroke):
    return (f'<path d="M{cx},{cy-h/2} L{cx+w/2},{cy} L{cx},{cy+h/2} L{cx-w/2},{cy} Z" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="4"/>'
            + T(cx, cy - 4, t1, 26, INK, 700, "middle") + T(cx, cy + 26, t2, 24, INK2, None, "middle"))


def arrow(x1, y1, x2, y2, c=INK2, m="a", sw=4, dash=False):
    d = ' stroke-dasharray="10 7"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{sw}"{d} marker-end="url(#{m})"/>'


def path(d, c=INK2, m="a", sw=4, dash=False):
    da = ' stroke-dasharray="10 7"' if dash else ""
    return f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{sw}"{da} marker-end="url(#{m})"/>'


def bar(x, y0, y, w, c, tip=""):
    if y0 - y < 6:
        y = y0 - 6
    t = f"<title>{tip}</title>" if tip else ""
    return f'<path d="M{x},{y0} V{y+5} Q{x},{y} {x+5},{y} H{x+w-5} Q{x+w},{y} {x+w},{y+5} V{y0} Z" fill="{c}">{t}</path>'


def label(x, y, v, fmt="{:.2f}", size=24, bold=True):
    return (f'<text x="{x}" y="{y}" text-anchor="middle" font-size="{size}"{" font-weight=\"700\"" if bold else ""} '
            f'fill="{INK}" stroke="#ffffff" stroke-width="6" paint-order="stroke">{fmt.format(v)}</text>')


def legend(items, x, y, size=28, gap=34):
    s = ""
    for name, c in items:
        if c == "dash":
            s += (f'<line x1="{x}" y1="{y-9}" x2="{x+40}" y2="{y-9}" stroke="{INK}" stroke-width="3" stroke-dasharray="10 6"/>'
                  + T(x + 50, y, name, size))
            x += 50 + len(name) * size * 0.47 + gap
        else:
            s += f'<rect x="{x}" y="{y-24}" width="26" height="26" rx="4" fill="{c}"/>' + T(x + 36, y, name, size)
            x += 36 + len(name) * size * 0.47 + gap
    return s


def num(cx, cy, n, c=NAVY, r=20):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>' + T(cx, cy + 9, n, 26, "#ffffff", 700, "middle")


# ---------------- icons (drawn in a 100x100 box at x, y, scaled by k) ----------------
def icon(kind, x, y, k=1.0, c=NAVY):
    g = f'<g transform="translate({x},{y}) scale({k})" fill="none" stroke="{c}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">'
    if kind == "check":
        g += f'<circle cx="50" cy="50" r="42"/><path d="M30,52 L45,67 L72,36"/>'
    elif kind == "cross":
        g += f'<circle cx="50" cy="50" r="42"/><path d="M34,34 L66,66 M66,34 L34,66"/>'
    elif kind == "chip":
        g += '<rect x="24" y="24" width="52" height="52" rx="6"/><rect x="38" y="38" width="24" height="24" rx="3"/>'
        for p in (36, 50, 64):
            g += f'<path d="M{p},24 V10 M{p},76 V90 M24,{p} H10 M76,{p} H90"/>'
    elif kind == "bug":
        g += ('<ellipse cx="50" cy="56" rx="20" ry="27"/><circle cx="50" cy="24" r="10"/><path d="M50,32 V82"/>'
              '<path d="M30,46 L14,38 M30,60 H12 M31,74 L16,84 M70,46 L86,38 M70,60 H88 M69,74 L84,84"/>')
    elif kind == "lock":
        g += '<rect x="22" y="46" width="56" height="42" rx="6"/><path d="M34,46 V32 A16,16 0 0 1 66,32 V46"/><path d="M50,62 V72"/>'
    elif kind == "clock":
        g += '<circle cx="50" cy="50" r="40"/><path d="M50,26 V50 L66,62"/>'
    elif kind == "cycle":
        g += ('<path d="M22,44 A30,30 0 0 1 76,34"/><path d="M78,56 A30,30 0 0 1 24,66"/>'
              '<path d="M66,22 L78,34 L64,42"/><path d="M34,78 L22,66 L36,58"/>')
    elif kind == "branch":
        g += '<path d="M30,88 V14"/><path d="M30,60 C30,40 70,46 70,22"/><path d="M58,30 L70,16 L82,30"/><path d="M18,26 L30,12 L42,26"/>'
    elif kind == "network":
        g += ('<circle cx="50" cy="20" r="11"/><circle cx="20" cy="78" r="11"/><circle cx="80" cy="78" r="11"/>'
              '<path d="M44,30 L26,68 M56,30 L74,68 M31,78 H69"/>')
    elif kind == "book":
        g += '<path d="M50,24 C38,16 22,16 12,20 V82 C22,78 38,78 50,86 C62,78 78,78 88,82 V20 C78,16 62,16 50,24 Z"/><path d="M50,24 V86"/>'
    elif kind == "box":
        g += '<path d="M50,12 L86,30 V70 L50,88 L14,70 V30 Z"/><path d="M14,30 L50,48 L86,30 M50,48 V88"/>'
    elif kind == "chart":
        g += '<path d="M12,88 H90"/><rect x="20" y="52" width="14" height="36"/><rect x="44" y="30" width="14" height="58"/><rect x="68" y="14" width="14" height="74"/>'
    elif kind == "zero":
        g += '<path d="M20,30 H80 L72,88 H28 Z"/><path d="M14,30 H86 M40,30 V18 H60 V30"/><path d="M42,46 V74 M58,46 V74"/>'
    elif kind == "bolt":
        g += '<path d="M58,8 L22,56 H48 L40,92 L80,40 H54 Z"/>'
    elif kind == "fence":
        for p in (20, 40, 60, 80):
            g += f'<path d="M{p},88 V26 L{p-6},{34} M{p},26 L{p+6},34"/>'
        g += '<path d="M12,46 H88 M12,72 H88"/>'
    elif kind == "pile":
        g += ('<rect x="14" y="70" width="72" height="18" rx="3"/><rect x="22" y="48" width="56" height="18" rx="3"/>'
              '<rect x="30" y="26" width="40" height="18" rx="3"/><path d="M86,40 V8 M78,18 L86,8 L94,18"/>')
    elif kind == "magnify":
        g += '<circle cx="42" cy="42" r="28"/><path d="M62,62 L88,88"/>'
    return g + "</g>"


# ======================= section 2: small icons =======================
save("icon_hp", 100, 100, icon("fence", 0, 0, 1.0, GREEN))
save("icon_ebr", 100, 100, icon("pile", 0, 0, 1.0, YEL))

# ======================= section 3: how a reader uses CA =======================
W, H = 1400, 400
cy = 215
s = ""
s += box(15, cy - 55, 200, 110, "#f3f3f0", "start", "untagAll", stroke=AXIS)
s += box(265, cy - 55, 220, 110, "#e8f1fc", "cread", "next node", stroke=BLUE)
s += diamond(625, cy, 220, 150, "#fdece4", "bcafail", "failed?", ORANGE)
s += box(785, cy - 55, 200, 110, "#e3f5ee", "use", "the value", stroke=GREEN)
s += diamond(1115, cy, 190, 150, "#f3f3f0", "last", "node?", AXIS)
s += box(1250, cy - 55, 140, 110, "#f3f3f0", "done", "untagAll", stroke=AXIS)
s += arrow(215, cy, 261, cy) + arrow(485, cy, 511, cy) + arrow(735, cy, 781, cy)
s += arrow(985, cy, 1016, cy) + arrow(1210, cy, 1246, cy)
s += T(758, cy - 14, "no", 24, INK2, 600, "middle") + T(1228, cy - 14, "yes", 24, INK2, 600, "middle")
# failed -> retry from the start
s += path(f"M625,{cy-75} V45 H115 V{cy-59}", RED, "r")
s += T(370, 36, "yes: another core changed it, so retry (never reads freed memory)", 26, RED, 700, "middle")
# not last -> next node
s += path(f"M1115,{cy+75} V375 H375 V{cy+59}", INK2, "a")
s += T(745, 366, "no: go to the next node", 26, INK2, 600, "middle")
save("ca_flow", W, H, s)

# ======================= section 4: one design, three answers =======================
W, H = 1400, 300
s = ""
s += box(15, 80, 290, 140, "#fdece4", "Our hardware", "design (RTL)", stroke=ORANGE, s1=32, s2=30, c2=INK)
s += box(420, 10, 420, 110, "#e8f1fc", "Cycle-exact simulator", "Verilator, on a PC", stroke=BLUE)
s += box(420, 180, 420, 110, "#e3f5ee", "Real FPGA board", "AMD KR260, 50 MHz", stroke=GREEN)
s += box(955, 80, 430, 140, NAVY, "Compare with the paper", "simulator · board · paper [1]", c1="#ffffff", c2="#dfe7f1", s1=32, s2=26)
s += path("M305,150 C360,150 360,65 416,65") + path("M305,150 C360,150 360,235 416,235")
s += path("M840,65 C900,65 900,150 951,150") + path("M840,235 C900,235 900,150 951,150")
save("method_flow", W, H, s)


# ======================= section 5: architecture with the L2 =======================
def core(x, n):
    s = f'<rect x="{x}" y="70" width="660" height="390" rx="6" fill="#ffffff" stroke="{BLUE}" stroke-width="4"/>'
    s += T(x + 30, 122, f"CVA6 core {n} (RV32IMAC)", 34, BLUE, 700)
    s += box(x + 25, 145, 610, 92, "#e8f1fc", "In-order pipeline", "+ cread, cwrite, untagOne, untagAll, bcafail", s1=32, s2=28, rx=5)
    s += box(x + 25, 250, 610, 92, "#fdece4", "CA unit", "8-line tag set; revoked on snoop, eviction, trap", s1=32, s2=28, rx=5)
    s += box(x + 25, 355, 610, 92, "#e3f5ee", "L1 data cache with MSI", "write-back, 32 KiB; atomics run in the L1", s1=32, s2=28, rx=5)
    return s


a = (T(20, 46, "AMD KR260 FPGA, 50 MHz", 34, INK, 700)
     + core(20, 0) + core(720, 1)
     + f'<line x1="350" y1="462" x2="350" y2="500" stroke="{INK2}" stroke-width="4" marker-start="url(#a)" marker-end="url(#a)"/>'
     + f'<line x1="1050" y1="462" x2="1050" y2="500" stroke="{INK2}" stroke-width="4" marker-start="url(#a)" marker-end="url(#a)"/>'
     + f'<rect x="20" y="502" width="1360" height="100" rx="6" fill="{GREEN}"/>'
     + T(700, 545, "Coherence directory: records which cache holds each line", 32, "#ffffff", 700, "middle")
     + T(700, 585, "snoops only the holders; misses to different lines proceed in parallel", 28, "#ffffff", None, "middle")
     + arrow(450, 604, 450, 640)
     + f'<rect x="20" y="642" width="1360" height="100" rx="6" fill="{NAVY}"/>'
     + T(700, 685, "Shared L2 cache, 256 KiB", 32, "#ffffff", 700, "middle")
     + T(700, 725, "64 B lines, 8-way, keeps serving hits while misses wait", 28, "#dfe7f1", None, "middle")
     + arrow(450, 744, 450, 780)
     + box(20, 782, 880, 100, "#f3f3f0", "PS DDR4 main memory (the ARM side)", "core 0x8000_0000 → DDR 0x4000_0000", stroke=AXIS, rx=6, s2=27)
     + box(940, 782, 440, 100, "#f3f3f0", "Mailbox + host (JTAG)", "loads programs, reads results", stroke=AXIS, rx=6, s2=27))
save("architecture_v3", 1400, 900, a, bg=PANEL_BG)

# ======================= section 5: how CA reuses coherence =======================
W, H = 1400, 500
X0, XD, X1 = 190, 700, 1210
s = ""
for x, t, c, f in ((X0, "Core 0 (reader)", BLUE, "#e8f1fc"), (XD, "Directory", DKGREEN, "#e3f5ee"), (X1, "Core 1 (remover)", ORANGE, "#fdece4")):
    s += box(x - 170, 6, 340, 64, f, t, "", stroke=c, s1=30)
    s += f'<line x1="{x}" y1="70" x2="{x}" y2="{H-10}" stroke="{AXIS}" stroke-width="3" stroke-dasharray="4 8"/>'
y = 118
s += num(X0 - 150, y - 8, "1") + arrow(X0, y, XD - 4, y, BLUE, "b") + T((X0 + XD) / 2, y - 14, "cread(N): read and watch N", 26, INK, 600, "middle")
s += T(XD + 16, y + 30, "notes: core 0 has a copy of N", 24, INK2, None, "start", True)
y = 196
s += num(X1 + 150, y - 8, "2") + arrow(X1, y, XD + 4, y, ORANGE, "o") + T((X1 + XD) / 2, y - 14, "unlink N: wants to write N", 26, INK, 600, "middle")
y = 272
s += num(X0 - 150, y - 8, "3") + arrow(XD, y, X0 + 4, y, RED, "r") + T((X0 + XD) / 2, y - 14, "invalidate your copy of N", 26, RED, 700, "middle")
s += box(X0 - 175, y + 14, 350, 66, "#fbe1e1", "access revoked", "the CA unit remembers", stroke=RED, s1=26, s2=22)
y = 350
s += arrow(XD, y, X1 - 4, y, DKGREEN, "g") + T((X1 + XD) / 2, y - 14, "go ahead", 26, DKGREEN, 600, "middle")
s += box(X1 - 150, y + 14, 300, 58, "#fdece4", "free(N), at once", "", stroke=ORANGE, s1=26)
y = 450
s += num(X0 - 150, y, "4") + box(X0 - 120, y - 32, 560, 64, "#e3f5ee", "next cread / bcafail fails → retry", "", stroke=GREEN, s1=27)
s += T(X0 + 460, y + 10, "never touches freed N", 26, DKGREEN, 700)
save("revoke_seq", W, H, s, bg=PANEL_BG)

# ======================= section 6: challenges as cards =======================
cards = [("network", "Coherence from scratch", ["We designed our own MSI caches", "and a directory for two cores."]),
         ("cycle", "Deadlock", ["A cache always answers the other", "cache without waiting itself."]),
         ("lock", "Atomic cwrite", ["Check and store happen together,", "at commit, line held exclusively."]),
         ("clock", "Speculation", ["CA operations take effect only", "when the instruction commits."]),
         ("branch", "Fast failure check", ["RISC-V has no flag register, so we", "added a branch: bcafail."]),
         ("bug", "Bug only the board showed", ["The L2 broke an AXI handshake rule;", "we fixed it and the simulator."])]
W, H = 1400, 440
cw, ch = 448, 205
s = ""
for i, (ic, title, lines) in enumerate(cards):
    x, y = 4 + (i % 3) * (cw + 18), 4 + (i // 3) * (ch + 22)
    s += f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="16" fill="{CARD}" stroke="{CARDLINE}" stroke-width="2"/>'
    s += icon(ic, x + 18, y + 22, 0.62, NAVY if i < 4 else (DKORANGE if i == 4 else RED))
    s += T(x + 96, y + 62, title, 29, NAVY, 700)
    for j, ln in enumerate(lines):
        s += T(x + 22, y + 120 + j * 36, ln, 25, INK2)
save("challenges", W, H, s)

# ======================= section 7a: verification pipeline =======================
stages = [("Cache unit tests", "1,500/1,500", ["random two-cache", "simulations pass"]),
          ("L2 unit tests", "200/200", ["random, with slow", "and stalling DDR"]),
          ("Full-system sim", "72/73", ["RISC-V ISA tests*,", "all CA tests pass"]),
          ("KR260 board", "1,800", ["benchmark runs, no", "structure corrupted"])]
W, H = 1400, 212
cw = 305
s = ""
for i, (t, big, ls) in enumerate(stages):
    x = 4 + i * (cw + 60)
    s += f'<rect x="{x}" y="6" width="{cw}" height="{H-12}" rx="16" fill="#f4f8f6" stroke="#cfe6dc" stroke-width="2"/>'
    s += T(x + cw / 2, 40, t, 28, NAVY, 700, "middle")
    s += icon("check", x + 18, 56, 0.56, GREEN)
    s += T(x + 90, 102, big, 40, NAVY, 700)
    s += T(x + cw / 2, 152, ls[0], 24, INK2, None, "middle") + T(x + cw / 2, 182, ls[1], 24, INK2, None, "middle")
    if i < 3:
        s += arrow(x + cw + 6, H / 2, x + cw + 54, H / 2, INK2)
save("verify_flow", W, H, s)

# ======================= section 7b: the four benchmarks as pictures =======================
W, H = 1400, 200
s = ""
pw = 350
# lazy list
x = 20
for i in range(4):
    s += f'<circle cx="{x+30+i*80}" cy="70" r="24" fill="#e8f1fc" stroke="{BLUE}" stroke-width="4"/>'
    if i < 3:
        s += arrow(x + 54 + i * 80, 70, x + 82 + i * 80, 70, BLUE, "b", 3)
s += T(x + 150, 175, "lazy list", 28, INK, 600, "middle")
# BST
x = 380
pts = [(150, 30), (90, 80), (210, 80), (60, 125), (120, 125)]
for (a1, b1), (a2, b2) in ((pts[0], pts[1]), (pts[0], pts[2]), (pts[1], pts[3]), (pts[1], pts[4])):
    s += f'<line x1="{x+a1}" y1="{b1}" x2="{x+a2}" y2="{b2}" stroke="{GREEN}" stroke-width="4"/>'
for a1, b1 in pts:
    s += f'<circle cx="{x+a1}" cy="{b1}" r="17" fill="#e3f5ee" stroke="{GREEN}" stroke-width="4"/>'
s += T(x + 135, 175, "binary search tree", 28, INK, 600, "middle")
# stack
x = 760
for i in range(4):
    s += f'<rect x="{x+70}" y="{28+i*30}" width="120" height="26" rx="4" fill="#fdece4" stroke="{ORANGE}" stroke-width="3"/>'
s += path(f"M{x+240},70 H{x+200}", ORANGE, "a") + T(x + 246, 78, "top", 24, INK2)
s += T(x + 130, 175, "stack", 28, INK, 600, "middle")
# hash
x = 1100
for i in range(4):
    yy = 26 + i * 32
    s += f'<rect x="{x+30}" y="{yy}" width="44" height="26" rx="4" fill="#fdf3dc" stroke="{YEL}" stroke-width="3"/>'
    for j in range(i % 3):
        s += f'<circle cx="{x+110+j*50}" cy="{yy+13}" r="11" fill="#fdf3dc" stroke="{YEL}" stroke-width="3"/>'
        s += f'<line x1="{x+76+j*50}" y1="{yy+13}" x2="{x+97+j*50}" y2="{yy+13}" stroke="{YEL}" stroke-width="3"/>'
s += T(x + 130, 175, "hash table", 28, INK, 600, "middle")
save("bench_icons", W, H, s)


# ======================= section 7c: throughput (2 threads, board with the L2) =======================
def grouped(name, data, cols, ymax, ticks, labelled, bw, W=1400, H=500, lsize=27):
    top, bot = 130, H - 64
    Y = lambda v: bot - (bot - top) * v / ymax
    s = legend(cols + [("never free = 1.0×", "dash")], 40, 48, size=lsize, gap=26)
    for v in ticks:
        s += f'<line x1="80" y1="{Y(v)}" x2="{W-20}" y2="{Y(v)}" stroke="{GRID}" stroke-width="2"/>'
        s += T(68, Y(v) + 9, f"{v:.1f}×", 24, MUTED, None, "end")
    pw = (W - 100 - 40) / 2
    n = len(cols)
    for pi, (title, groups) in enumerate(data.items()):
        px = 90 + pi * (pw + 40)
        s += T(px + pw / 2, top - 30, title, 30, INK, 700, "middle")
        gw = pw / 4
        for gi, (g, vals) in enumerate(groups.items()):
            gx = px + gi * gw + (gw - n * bw - 2 * (n - 1)) / 2
            for bi, v in enumerate(vals):
                x = gx + bi * (bw + 2)
                s += bar(x, bot, Y(v), bw, cols[bi][1], f"{g} {cols[bi][0]}: {v:.2f}")
                if bi in labelled:
                    ly = Y(v) - 10
                    if abs(ly - Y(1)) < 26:
                        ly = min(ly, Y(1) - 12)
                    s += label(x + bw / 2, ly, v, size=21 if len(labelled) > 1 else 24)
            s += T(px + gi * gw + gw / 2, bot + 36, g, 28, INK2, None, "middle")
        s += f'<line x1="{px}" y1="{Y(1)}" x2="{px+pw}" y2="{Y(1)}" stroke="{INK}" stroke-width="3" stroke-dasharray="10 6"/>'
    s += f'<line x1="80" y1="{bot}" x2="{W-20}" y2="{bot}" stroke="{AXIS}" stroke-width="2"/>'
    save(name, W, H, s)


# board_l2 summary.csv, 2 threads, mops / none mops
# (ca, cafast, cabr, hp, qsbr)
B = {"Read-only (0% updates)": {"list": (.34, .50, .50, .25, 1.00), "BST": (.46, .62, .59, .38, 1.00),
                                "stack": (.37, .43, .42, .50, .92), "hash": (.48, .56, .64, .47, .99)},
     "Write-heavy (100% updates)": {"list": (.41, .59, .58, .31, .99), "BST": (.59, .76, .74, .47, .90),
                                    "stack": (1.20, 1.25, 1.27, .99, 1.03), "hash": (.81, .87, .99, .69, .91)}}
best = {p: {g: (max(v[1], v[2]), v[3], v[4]) for g, v in d.items()} for p, d in B.items()}
grouped("throughput_v3", best, [("CA (best check)", ORANGE), ("hazard pointers", GREEN), ("epochs (QSBR)", YEL)],
        1.5, (0, .5, 1.0, 1.5), (0, 1, 2), 46)
var = {p: {g: v[:3] for g, v in d.items()} for p, d in B.items()}
grouped("ca_variants", var, [("CA + status-register check", LTORANGE), ("CA + fast check", DKORANGE), ("CA + bcafail", BROWN)],
        1.5, (0, .5, 1.0, 1.5), (0, 1, 2), 44, lsize=26)

# ---------------- cost of one protected read (cycles; phase 7 micro, board) ----------------
rows = [("plain load", 1, GREY, False), ("cread", 2, LTORANGE, False),
        ("cread + status-register check", 7, LTORANGE, False),
        ("cread + fast check", 5, DKORANGE, False), ("cread + bcafail (ours)", 4, BROWN, True)]
W, H = 700, 372
x0, x1, vmax = 20, 600, 7.6
s = ""
for i, (name, v, c, b) in enumerate(rows):
    y = 4 + i * 73
    s += T(x0, y + 26, name, 27, INK, 700 if b else None)
    w = (x1 - x0) * v / vmax
    s += f'<rect x="{x0}" y="{y+34}" width="{w}" height="32" rx="5" fill="{c}"/>'
    s += T(x0 + w + 12, y + 61, f'{v} cycle{"s" if v > 1 else ""}', 28, INK, 700)
save("read_cost_v3", W, H, s)

# ---------------- paper vs simulator vs board (best CA, 100% updates) ----------------
three = {"list": (.96, .59, .59), "BST": (1.10, .76, .76), "stack": (.72, 1.27, 1.27), "hash": (1.37, .99, .99)}
# paper at 2 threads, estimated on its plotted line between the 1- and 4-thread points
# (sw/bench/paper_interp_2t.py), next to our 2-core simulator and board
three2 = {"list": (.67, .59, .59), "BST": (.97, .76, .76), "stack": (.57, 1.27, 1.27), "hash": (1.08, .99, .99)}
cols3 = [("paper [1], 4 threads", GREY), ("our simulator, 2 cores", BLUE), ("KR260 board, 2 cores", ORANGE)]
W, H = 1400, 440
top, bot, ymax = 90, 390, 1.6
Y = lambda v: bot - (bot - top) * v / ymax
s = legend(cols3, 40, 46, size=27, gap=30)
for v in (0, .5, 1.0, 1.5):
    s += f'<line x1="80" y1="{Y(v)}" x2="{W-20}" y2="{Y(v)}" stroke="{GRID}" stroke-width="2"/>'
    s += T(68, Y(v) + 9, f"{v:.1f}×", 24, MUTED, None, "end")
gw = (W - 110) / 4
bw = 78
for gi, (g, vals) in enumerate(three.items()):
    gx = 90 + gi * gw + (gw - 3 * bw - 8) / 2
    for bi, v in enumerate(vals):
        x = gx + bi * (bw + 4)
        s += bar(x, bot, Y(v), bw, cols3[bi][1], f"{g} {cols3[bi][0]}: {v:.2f}")
        ly = Y(v) - 10
        if abs(ly - Y(1)) < 30:
            ly = min(ly, Y(1) - 14)
        s += label(x + bw / 2, ly, v, size=23)
    s += T(90 + gi * gw + gw / 2, bot + 42, g, 30, INK2, None, "middle")
s += f'<line x1="80" y1="{Y(1)}" x2="{W-20}" y2="{Y(1)}" stroke="{INK}" stroke-width="3" stroke-dasharray="10 6"/>'
s += f'<line x1="80" y1="{bot}" x2="{W-20}" y2="{bot}" stroke="{AXIS}" stroke-width="2"/>'
save("paper_sim_board_v3", W, H, s)

# ---------------- effect of the shared L2: never-free speed-up, 100% updates, 2 threads ----------------
spd = [("list", 1.10), ("BST", 1.46), ("stack", 2.26), ("hash", 1.70)]
W, H = 700, 400
s = ""
px0, px1 = 0, 690
top, bot, ymax = 40, 340, 2.5
Y = lambda v: bot - (bot - top) * v / ymax
for v in (0, 1, 2):
    s += f'<line x1="{px0+50}" y1="{Y(v)}" x2="{px1}" y2="{Y(v)}" stroke="{GRID}" stroke-width="2"/>'
    s += T(px0 + 42, Y(v) + 9, f"{v}×", 26, MUTED, None, "end")
gw = (px1 - px0 - 60) / 4
for i, (g, v) in enumerate(spd):
    x = px0 + 60 + i * gw + (gw - 90) / 2
    s += bar(x, bot, Y(v), 90, NAVY) + label(x + 45, Y(v) - 10, v, "{:.2f}×", 28)
    s += T(x + 45, bot + 40, g, 30, INK2, None, "middle")
s += f'<line x1="{px0+50}" y1="{Y(1)}" x2="{px1}" y2="{Y(1)}" stroke="{INK}" stroke-width="3" stroke-dasharray="10 6"/>'
save("l2_speedup", W, H, s)


# ---------------- hardware cost: waffle, one square = 1% of the FPGA's LUTs ----------------
# impl_utilization_hier.rpt (phase 8): total 78,120 of 117,120; L2 18,508; CA units 976 + 1,095;
# directory 676; the rest (cores, L1s, AXI) 56,865.
parts = [("two CVA6 cores, L1 caches, AXI", 48, CORE, "56.9k LUTs"),
         ("CA units (ours)", 2, ORANGE, "2.1k LUTs, ≈1% per core"),
         ("coherence directory (ours)", 1, GREEN, "676 LUTs + 2 UltraRAM"),
         ("shared L2 cache (ours)", 16, NAVY, "18.5k LUTs + 8 UltraRAM"),
         ("free", 33, "#ecebe6", "39k LUTs left")]
W, H = 1400, 360
cell, gap, gx0, gy0 = 30, 4, 10, 10
s = ""
k = 0
for name, n, c, _ in parts:
    for _ in range(n):
        r, q = divmod(k, 10)
        s += f'<rect x="{gx0 + q*(cell+gap)}" y="{gy0 + r*(cell+gap)}" width="{cell}" height="{cell}" rx="6" fill="{c}"/>'
        k += 1
lx = 400
s += T(lx, 36, "One square = 1% of the FPGA's logic (117,120 LUTs)", 28, INK, 700)
for i, (name, n, c, sub) in enumerate(parts):
    y = 62 + i * 50
    s += f'<rect x="{lx}" y="{y}" width="34" height="34" rx="6" fill="{c}" stroke="{AXIS if c == "#ecebe6" else c}" stroke-width="2"/>'
    s += T(lx + 50, y + 27, f"{name}: {n}%", 28, INK, 600)
    s += T(1385, y + 27, sub, 24, INK2, None, "end")
s += f'<rect x="{lx}" y="318" width="985" height="40" rx="20" fill="#e3f5ee"/>'
s += T(lx + 492, 347, "bcafail: +17 LUTs  ·  timing met at 50 MHz", 28, DKGREEN, 700, "middle")
save("hardware_cost_v3", W, H, s)

# ======================= section 8: how a program runs on the board =======================
W, H = 1400, 760
s = ""
r1, r2 = 30, 165
s += box(20, r1, 270, 100, "#e8f1fc", "bench.c, tests", "C / assembly", stroke=BLUE)
s += box(350, r1, 300, 100, "#e8f1fc", "RISC-V cross-compiler", "gcc, rv32ima, bare metal", stroke=BLUE, s1=28)
s += box(710, r1, 250, 100, "#e8f1fc", "program", "ELF → raw binary", stroke=BLUE)
s += box(20, r2, 270, 100, "#fdece4", "our hardware", "SystemVerilog", stroke=ORANGE)
s += box(350, r2, 300, 100, "#fdece4", "Vivado", "synthesis, place, route", stroke=ORANGE)
s += box(710, r2, 250, 100, "#fdece4", "bitstream", "the circuit", stroke=ORANGE)
for y in (r1, r2):
    s += arrow(290, y + 50, 346, y + 50) + arrow(650, y + 50, 706, y + 50)
s += box(1060, 70, 320, 160, "#f3f3f0", "Laptop: xsdb", "JTAG over USB cable", stroke=AXIS)
s += path(f"M960,{r1+50} H1010 V130 H1056") + path(f"M960,{r2+50} H1010 V170 H1056")
# the board
s += f'<rect x="20" y="330" width="1360" height="410" rx="14" fill="#fbfbf9" stroke="{INK2}" stroke-width="4"/>'
s += T(44, 374, "AMD KR260 board", 32, INK, 700)
s += f'<rect x="44" y="396" width="560" height="320" rx="10" fill="#fdf5f0" stroke="{ORANGE}" stroke-width="3"/>'
s += T(64, 436, "PL: programmable logic", 28, DKORANGE, 700)
s += box(74, 460, 500, 100, "#ffffff", "2 CVA6 cores + caches", "directory, CA units", stroke=ORANGE)
s += box(74, 590, 500, 100, "#ffffff", "shared L2 cache", "256 KiB", stroke=ORANGE)
s += f'<rect x="796" y="396" width="544" height="320" rx="10" fill="#f0f4fa" stroke="{BLUE}" stroke-width="3"/>'
s += T(816, 436, "PS: ARM side", 28, BLUE, 700)
s += box(826, 460, 484, 100, "#ffffff", "DDR4 main memory", "program + data live here", stroke=BLUE)
s += box(826, 590, 484, 100, "#ffffff", "mailbox", "pass/fail + benchmark counters", stroke=BLUE)
s += f'<line x1="578" y1="640" x2="822" y2="530" stroke="{INK2}" stroke-width="5" marker-start="url(#a)" marker-end="url(#a)"/>'
s += T(700, 615, "AXI", 26, INK2, 700, "middle")
# numbered steps between the laptop and the board
s += path("M1110,230 V290 H480 V456", NAVY, "a")
s += num(540, 290, "1") + T(570, 280, "load the bitstream", 25, NAVY, 700)
s += num(830, 290, "3") + T(860, 280, "start the cores", 25, NAVY, 700)
s += path("M1200,230 V456", NAVY, "a") + num(1200, 300, "2") + T(1182, 358, "copy binary", 25, NAVY, 700, "end")
s += path("M1310,640 H1360 V234", NAVY, "a")
s += num(1360, 300, "4", NAVY, 18) + T(1342, 358, "read results", 25, NAVY, 700, "end")
save("board_flow", W, H, s)

# ======================= section 8: what we learned, four cards =======================
cards = [("book", "Research to hardware", NAVY,
          ["Read a paper for the big picture first.",
           "Its x86 flag register has no RISC-V twin,",
           "  so we designed bcafail.",
           "Concurrent data structures: lazy list, BST."]),
         ("box", "Building on open source", NAVY,
          ["Learning a large real codebase: CVA6.",
           "OpenPiton (old, unmaintained) failed us:",
           "  don't trust stale repositories.",
           "So we built our own MSI caches and L2."]),
         ("chip", "Hardware is finite", NAVY,
          ["117k LUTs fit only 2 cores: 32-bit RISC-V.",
           "PL ↔ PS: our cores use the ARM side's DDR4.",
           "Tooling: Vivado 2023.2 licence (we had 2019.2),",
           "  JTAG adapter, board login, Linux, WSL."]),
         ("chart", "Results and testing", NAVY,
          ["Faster is not always better: epochs win",
           "  read-heavy work, CA leaves 0 nodes waiting.",
           "Simulators can hide bugs: the L2 bug",
           "  appeared only on the board.",
           "The platform changes the answer (L2)."])]
cw = 685
rowh = [96 + 36 * max(len(cards[2 * r][3]), len(cards[2 * r + 1][3])) for r in range(2)]
W, H = 1400, 8 + rowh[0] + 22 + rowh[1]
s = ""
for i, (ic, title, c, lines) in enumerate(cards):
    ch = rowh[i // 2]
    x, y = 4 + (i % 2) * (cw + 22), 4 + (0 if i < 2 else rowh[0] + 22)
    s += f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="16" fill="{CARD}" stroke="{CARDLINE}" stroke-width="2"/>'
    s += icon(ic, x + 20, y + 16, 0.6, c)
    s += T(x + 96, y + 56, title, 31, NAVY, 700)
    yy = y + 110
    for ln in lines:
        if ln.startswith("  "):
            s += T(x + 50, yy, ln.strip(), 25, INK2)
        else:
            s += f'<circle cx="{x+34}" cy="{yy-8}" r="5" fill="{ORANGE}"/>' + T(x + 50, yy, ln, 25, INK2)
        yy += 36
save("learnings", W, H, s)

# ======================= section 9: three takeaways =======================
tk = [("check", GREEN, "Works on real hardware", "2 cores, KR260, 1,800 runs"),
      ("zero", ORANGE, "Frees memory at once", "0 nodes left waiting"),
      ("bolt", NAVY, "Fastest under contention", "1.27× on the stack, ≈1% area")]
W, H = 1400, 170
s = ""
for i, (ic, c, t1, t2) in enumerate(tk):
    x = 4 + i * 467
    s += f'<rect x="{x}" y="6" width="450" height="158" rx="16" fill="{CARD}" stroke="{CARDLINE}" stroke-width="2"/>'
    s += icon(ic, x + 16, 45, 0.8, c)
    s += T(x + 106, 74, t1, 27, NAVY, 700) + T(x + 106, 116, t2, 22, INK2)
save("takeaways", W, H, s)

# ---------------- half-width grouped bars (one panel, 4 groups) ----------------
def half(name, groups, cols, ymax, ticks, W=700, H=400, leg_rows=None, fmt="{:.2f}"):
    s = ""
    rows = leg_rows or [cols]
    for r, items in enumerate(rows):
        s += legend(items, 10, 32 + r * 38, size=25, gap=18)
    top = 32 + len(rows) * 38 + 16
    bot = H - 50
    Y = lambda v: bot - (bot - top) * v / ymax
    for v in ticks:
        s += f'<line x1="56" y1="{Y(v)}" x2="{W-6}" y2="{Y(v)}" stroke="{GRID}" stroke-width="2"/>'
        s += T(48, Y(v) + 8, f"{v:.1f}×", 22, MUTED, None, "end")
    n = len(cols)
    gw = (W - 66) / 4
    bw = min(46, (gw - 14) / n - 2)
    for gi, (g, vals) in enumerate(groups.items()):
        gx = 62 + gi * gw + (gw - n * bw - 2 * (n - 1)) / 2
        for bi, v in enumerate(vals):
            x = gx + bi * (bw + 2)
            s += bar(x, bot, Y(v), bw, cols[bi][1], f"{g} {cols[bi][0]}: {v:.2f}")
            ly = Y(v) - 8
            if abs(ly - Y(1)) < 22:
                ly = min(ly, Y(1) - 10)
            s += label(x + bw / 2, ly, v, fmt, size=19)
        s += T(62 + gi * gw + gw / 2, bot + 34, g, 27, INK2, None, "middle")
    s += f'<line x1="56" y1="{Y(1)}" x2="{W-6}" y2="{Y(1)}" stroke="{INK}" stroke-width="3" stroke-dasharray="10 6"/>'
    s += f'<line x1="56" y1="{bot}" x2="{W-6}" y2="{bot}" stroke="{AXIS}" stroke-width="2"/>'
    save(name, W, H, s)


vc = [("status-register check", LTORANGE), ("fast check", DKORANGE), ("bcafail", BROWN)]
half("ca_variants_half", var["Write-heavy (100% updates)"], vc, 1.5, (0, .5, 1.0, 1.5),
     leg_rows=[vc[:2], vc[2:] + [("never free", "dash")]])
pc = [("paper [1], 2 threads*", GREY), ("our simulator", BLUE), ("KR260 board", ORANGE)]
half("paper_sim_board_half", three2, pc, 1.6, (0, .5, 1.0, 1.5),
     leg_rows=[pc[:2], pc[2:] + [("never free", "dash")]])

# ======================= challenges and lessons, one figure =======================
left = [("cycle", "Deadlock", ["A cache always answers the other cache", "without waiting for anything itself."]),
        ("lock", "Atomic cwrite", ["Check and store happen together, at commit,", "with the line held exclusively."]),
        ("clock", "Speculation", ["CA operations take effect only when", "the instruction commits."]),
        ("branch", "No flag register in RISC-V", ["The paper assumes x86 EFLAGS; we added a", "branch instruction instead: bcafail."])]
right = [("box", "Don't trust stale repositories", ["OpenPiton (an old CVA6) failed us, so we built", "our own MSI caches, directory and L2."]),
         ("chip", "Hardware is finite", ["117k LUTs fit 2 cores, so 32-bit RISC-V. Tooling:", "Vivado 2023.2 licence, JTAG, Windows + WSL."]),
         ("bug", "Simulators can hide bugs", ["An L2 handshake bug showed only on the board;", "after the fix, simulator = board exactly."]),
         ("chart", "Faster is not always better", ["Epochs win read-heavy speed, CA keeps 0 nodes", "waiting; adding the L2 changed the answer."])]
W, cw, ch, gap = 1400, 688, 108, 12
H = 66 + 4 * (ch + gap) - gap + 4
s = ""
for col, (head, cards, c, bg) in enumerate((("What we had to solve", left, NAVY, CARD),
                                            ("What we learned", right, DKORANGE, "#fdf6f2"))):
    x = 4 + col * (cw + 20)
    s += f'<rect x="{x}" y="4" width="{cw}" height="52" rx="26" fill="{c}"/>'
    s += T(x + cw / 2, 40, head, 30, "#ffffff", 700, "middle")
    for i, (ic, title, lines) in enumerate(cards):
        y = 66 + i * (ch + gap)
        s += f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="14" fill="{bg}" stroke="{CARDLINE}" stroke-width="2"/>'
        s += icon(ic, x + 16, y + 16, 0.5, c)
        s += T(x + 82, y + 36, title, 27, c, 700)
        s += T(x + 82, y + 68, lines[0], 24, INK2) + T(x + 82, y + 96, lines[1], 24, INK2)
save("challenges_lessons", W, H, s)

open(f"{out}/v3_sizes.txt", "w").write("\n".join(written) + "\n")
print("wrote", ", ".join(w.split()[0] for w in written))
