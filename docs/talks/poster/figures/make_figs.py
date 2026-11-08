import sys
out = sys.argv[1]
F = "font-family=\"'Times New Roman', Times, serif\""
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, GREEN, YEL, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e34948"

def box(x, y, w, h, fill, t1, t2, stroke=None, c2=INK2, b2=False, s1=30, s2=25):
    st = f' stroke="{stroke}" stroke-width="4"' if stroke else ""
    cx = x + w / 2
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}"{st}/>'
            f'<text x="{cx}" y="{y+h*0.44}" text-anchor="middle" font-size="{s1}" font-weight="600" fill="{INK}">{t1}</text>'
            f'<text x="{cx}" y="{y+h*0.80}" text-anchor="middle" font-size="{s2}" fill="{c2}"'
            f'{" font-weight=\"700\"" if b2 else ""}>{t2}</text>')

ARROW = ('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
         f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK2}"/></marker></defs>')

# ---------------- problem ----------------
def panel(x0, title, ca):
    s = f'<text x="{x0}" y="48" font-size="36" font-weight="700" fill="{INK}">{title}</text>'
    s += f'<text x="{x0}" y="112" font-size="28" font-weight="700" fill="{BLUE}">Core 0 (reader)</text>'
    s += f'<text x="{x0}" y="322" font-size="28" font-weight="700" fill="{ORANGE}">Core 1 (remover)</text>'
    if not ca:
        s += box(x0, 130, 290, 96, "#e8f1fc", "p = pred→next", "points to node N")
        s += box(x0 + 150, 340, 250, 96, "#fdece4", "unlink N", "pred→next = …")
        s += box(x0 + 420, 340, 250, 96, "#fdece4", "free(N)", "memory reused")
        s += box(x0 + 380, 130, 290, 96, "#fbe1e1", "v = p→key", "reads freed N", stroke=RED, c2="#a32a2a", b2=True)
    else:
        s += box(x0, 130, 290, 96, "#e8f1fc", "p = cread(…)", "line is tagged")
        s += box(x0 + 150, 340, 250, 96, "#fdece4", "unlink N", "write → GetM")
        s += box(x0 + 420, 340, 250, 96, "#fdece4", "free(N)", "immediately")
        s += box(x0 + 380, 130, 290, 96, "#e3f5ee", "cread(p→key)", "fails, so it retries", stroke=GREEN, c2="#0d6b4a", b2=True)
        s += (f'<path d="M{x0+275},338 C{x0+290},270 {x0+400},250 {x0+500},230" fill="none" stroke="{INK2}" '
              f'stroke-width="4" stroke-dasharray="10 7" marker-end="url(#a)"/>')
        s += f'<text x="{x0+430}" y="305" font-size="26" font-weight="600" fill="{INK2}">access revoked</text>'
    s += (f'<line x1="{x0}" y1="480" x2="{x0+660}" y2="480" stroke="{AXIS}" stroke-width="3" marker-end="url(#a)"/>'
          f'<text x="{x0+670}" y="470" font-size="24" fill="{MUTED}" text-anchor="end" >time</text>')
    return s
p = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="500" viewBox="0 0 1400 500" {F}>'
     f'<rect width="1400" height="500" fill="#ffffff"/>{ARROW}'
     + panel(20, "Without protection", False)
     + f'<line x1="700" y1="20" x2="700" y2="490" stroke="{GRID}" stroke-width="3"/>'
     + panel(725, "With conditional access", True) + '</svg>')
pass  # combined problem figure replaced by problem_without/with

# ---------------- architecture ----------------
def core(x, n):
    s = f'<rect x="{x}" y="70" width="660" height="390" rx="6" fill="#ffffff" stroke="{BLUE}" stroke-width="4"/>'
    s += f'<text x="{x+30}" y="122" font-size="34" font-weight="700" fill="{BLUE}">CVA6 core {n} (RV32IMAC)</text>'
    s += box(x + 25, 145, 610, 92, "#e8f1fc", "In-order pipeline", "adds cread, cwrite, untagOne, untagAll")
    s += box(x + 25, 250, 610, 92, "#fdece4", "CA unit (new)", "8-line tag set; revoked on snoop, eviction, trap")
    s += box(x + 25, 355, 610, 92, "#e3f5ee", "L1 data cache with MSI (new)", "write-back, 32 KiB; atomics run in the L1")
    return s
a = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="770" viewBox="0 0 1400 770" {F}>'
     f'<rect width="1400" height="770" fill="#ffffff"/>{ARROW}'
     f'<text x="20" y="46" font-size="34" font-weight="700" fill="{INK}">AMD KR260 FPGA, 50 MHz</text>'
     + core(20, 0) + core(720, 1)
     + f'<line x1="350" y1="462" x2="350" y2="500" stroke="{INK2}" stroke-width="4" marker-start="url(#a)" marker-end="url(#a)"/>'
     + f'<line x1="1050" y1="462" x2="1050" y2="500" stroke="{INK2}" stroke-width="4" marker-start="url(#a)" marker-end="url(#a)"/>'
     + f'<rect x="20" y="502" width="1360" height="100" rx="6" fill="{GREEN}"/>'
     + f'<text x="700" y="545" text-anchor="middle" font-size="32" font-weight="700" fill="#ffffff">Coherence bus (new): snooping, one transaction at a time</text>'
     + f'<text x="700" y="583" text-anchor="middle" font-size="26" fill="#ffffff">GetS / GetM / PutM; dirty data is written back before the grant</text>'
     + f'<line x1="450" y1="604" x2="450" y2="640" stroke="{INK2}" stroke-width="4" marker-end="url(#a)"/>'
     + box(20, 642, 880, 108, "#f3f3f0", "AXI4 → PS DDR4 memory (no L2)", "core 0x8000_0000 → DDR 0x4000_0000", stroke=AXIS)
     + box(940, 642, 440, 108, "#f3f3f0", "Mailbox and host (JTAG)", "loads programs, reads results", stroke=AXIS)
     + '</svg>')
open(f"{out}/architecture.svg", "w").write(a)

# ---------------- throughput ----------------
data = {
    "Read-only (0% updates)": {"list": (.34, .25, 1.00), "BST": (.64, .56, 1.00), "stack": (.37, .50, .92), "hash": (.49, .48, .99)},
    "Write-heavy (100% updates)": {"list": (.43, .33, 1.00), "BST": (.78, .65, .90), "stack": (1.33, 1.09, 1.05), "hash": (.98, .85, .99)},
}
cols = [("ca (cond. access)", ORANGE), ("hp (hazard pointers)", GREEN), ("qsbr (epochs)", YEL)]
W, H = 1400, 640
top, bot = 150, 560
ymax = 1.5
def Y(v): return bot - (bot - top) * v / ymax
s = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" {F}><rect width="{W}" height="{H}" fill="#ffffff"/>'
# legend
lx = 40
for name, c in cols:
    s += f'<rect x="{lx}" y="22" width="26" height="26" rx="4" fill="{c}"/><text x="{lx+36}" y="45" font-size="28" fill="{INK}">{name}</text>'
    lx += 36 + len(name) * 14 + 34
s += f'<line x1="{lx}" y1="35" x2="{lx+40}" y2="35" stroke="{INK}" stroke-width="3" stroke-dasharray="10 6"/><text x="{lx+52}" y="45" font-size="28" fill="{INK}">none = 1.0× (never frees)</text>'
# y axis
for v in (0, .5, 1.0, 1.5):
    s += f'<line x1="80" y1="{Y(v)}" x2="{W-20}" y2="{Y(v)}" stroke="{GRID}" stroke-width="2"/>'
    s += f'<text x="68" y="{Y(v)+9}" text-anchor="end" font-size="24" fill="{MUTED}">{v:.1f}×</text>'
pw = (W - 100 - 40) / 2
for pi, (title, groups) in enumerate(data.items()):
    px = 90 + pi * (pw + 40)
    s += f'<text x="{px + pw/2}" y="{top-42}" text-anchor="middle" font-size="30" font-weight="700" fill="{INK}">{title}</text>'
    gw = pw / 4
    s += f'<line x1="{px}" y1="{Y(1)}" x2="{px+pw}" y2="{Y(1)}" stroke="{INK}" stroke-width="3" stroke-dasharray="10 6"/>'
    bw = 40
    for gi, (g, vals) in enumerate(groups.items()):
        gx = px + gi * gw + (gw - 3 * bw - 4) / 2
        for bi, v in enumerate(vals):
            x = gx + bi * (bw + 2)
            y = Y(v)
            h = bot - y
            s += (f'<path d="M{x},{bot} V{y+5} Q{x},{y} {x+5},{y} H{x+bw-5} Q{x+bw},{y} {x+bw},{y+5} V{bot} Z" fill="{cols[bi][1]}">'
                  f'<title>{g} {cols[bi][0]}: {v:.2f}× none</title></path>')
            if bi == 0:
                s += f'<text x="{x+bw/2}" y="{y-10}" text-anchor="middle" font-size="24" font-weight="700" fill="{INK}" stroke="#ffffff" stroke-width="6" paint-order="stroke">{v:.2f}</text>'
        s += f'<text x="{px + gi*gw + gw/2}" y="{bot+40}" text-anchor="middle" font-size="28" fill="{INK2}">{g}</text>'
s += f'<line x1="80" y1="{bot}" x2="{W-20}" y2="{bot}" stroke="{AXIS}" stroke-width="2"/>'
s += '</svg>'
open(f"{out}/throughput.svg", "w").write(s)

# ================= narrative figures (poster v3) =================
def panel2(ca):
    W, H = 700, 420
    s = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" {F}><rect width="{W}" height="{H}" fill="#ffffff"/>{ARROW}'
    s += f'<text x="10" y="38" font-size="28" font-weight="700" fill="{BLUE}">Core 0 (reader)</text>'
    s += f'<text x="10" y="232" font-size="28" font-weight="700" fill="{ORANGE}">Core 1 (remover)</text>'
    if not ca:
        s += box(10, 56, 290, 96, "#e8f1fc", "p = pred→next", "points to node N")
        s += box(160, 250, 250, 96, "#fdece4", "unlink N", "pred→next = …")
        s += box(430, 250, 260, 96, "#fdece4", "free(N)", "memory reused")
        s += box(400, 56, 290, 96, "#fbe1e1", "v = p→key", "reads freed N", stroke=RED, c2="#a32a2a", b2=True)
    else:
        s += box(10, 56, 290, 96, "#e8f1fc", "p = cread(…)", "line is watched")
        s += box(160, 250, 250, 96, "#fdece4", "unlink N", "a write to N's line")
        s += box(430, 250, 260, 96, "#fdece4", "free(N)", "immediately")
        s += box(400, 56, 290, 96, "#e3f5ee", "cread(p→key)", "fails, so it retries", stroke=GREEN, c2="#0d6b4a", b2=True)
        s += (f'<path d="M285,248 C300,200 400,175 500,156" fill="none" stroke="{INK2}" '
              f'stroke-width="4" stroke-dasharray="10 7" marker-end="url(#a)"/>')
        s += f'<text x="455" y="222" font-size="26" font-weight="600" fill="{INK2}">access revoked</text>'
    s += (f'<line x1="10" y1="392" x2="690" y2="392" stroke="{AXIS}" stroke-width="3" marker-end="url(#a)"/>'
          f'<text x="680" y="380" font-size="24" fill="{MUTED}" text-anchor="end">time</text></svg>')
    return s
open(f"{out}/problem_without.svg", "w").write(panel2(False))
open(f"{out}/problem_with.svg", "w").write(panel2(True))

# shared linked list between two cores
W, H = 1400, 390
s = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" {F}><rect width="{W}" height="{H}" fill="#ffffff"/>{ARROW}'
s += box(60, 14, 420, 100, "#e8f1fc", "Core 0 (reader)", "searching for key 30", stroke=BLUE)
s += box(920, 14, 420, 100, "#fdece4", "Core 1 (writer)", "deleting key 30", stroke=ORANGE)
xs = [250, 510, 770, 1030]
s += f'<text x="100" y="292" font-size="30" font-weight="600" fill="{INK2}">head</text><line x1="180" y1="282" x2="246" y2="282" stroke="{INK2}" stroke-width="4" marker-end="url(#a)"/>'
for i, (x, k) in enumerate(zip(xs, (10, 20, 30, 40))):
    s += (f'<rect x="{x}" y="240" width="180" height="84" rx="4" fill="#f3f3f0" stroke="{INK2}" stroke-width="3"/>'
          f'<line x1="{x+110}" y1="240" x2="{x+110}" y2="324" stroke="{INK2}" stroke-width="3"/>'
          f'<text x="{x+55}" y="294" text-anchor="middle" font-size="34" font-weight="700" fill="{INK}">{k}</text>'
          f'<circle cx="{x+145}" cy="282" r="7" fill="{INK2}"/>')
    nx = xs[i + 1] if i < 3 else 1270
    s += f'<line x1="{x+145}" y1="282" x2="{nx-4}" y2="282" stroke="{INK2}" stroke-width="4" marker-end="url(#a)"/>'
s += f'<text x="1280" y="292" font-size="30" fill="{MUTED}">null</text>'
s += f'<path d="M270,116 C300,180 560,170 600,236" fill="none" stroke="{BLUE}" stroke-width="4" stroke-dasharray="10 7" marker-end="url(#a)"/>'
s += f'<path d="M1130,116 C1100,180 900,170 860,236" fill="none" stroke="{ORANGE}" stroke-width="4" stroke-dasharray="10 7" marker-end="url(#a)"/>'
s += f'<text x="700" y="372" text-anchor="middle" font-size="28" fill="{INK2}">No locks: both cores work on the same nodes at the same time</text>'
s += '</svg>'
open(f"{out}/setting.svg", "w").write(s)

# unfreed nodes: mean over the 4 structures, 2 threads, 100% updates
rows = [("none (never frees)", 2245, BLUE), ("qsbr (epochs)", 141, YEL), ("hp (hazard pointers)", 26, GREEN), ("ca (conditional access)", 0, ORANGE)]
W, H = 1400, 360
x0, x1, vmax = 400, 1250, 2400
s = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" {F}><rect width="{W}" height="{H}" fill="#ffffff"/>'
for i, (name, v, c) in enumerate(rows):
    y = 20 + i * 84
    s += f'<text x="{x0-20}" y="{y+44}" text-anchor="end" font-size="30" fill="{INK}"{" font-weight=\"700\"" if v == 0 else ""}>{name}</text>'
    w = (x1 - x0) * v / vmax
    if v > 0:
        w = max(w, 8)
        s += f'<path d="M{x0},{y+8} H{x0+w-6} Q{x0+w},{y+8} {x0+w},{y+14} V{y+56} Q{x0+w},{y+62} {x0+w-6},{y+62} H{x0} Z" fill="{c}"/>'
        s += f'<text x="{x0+w+14}" y="{y+46}" font-size="30" font-weight="700" fill="{INK}">{v:,}</text>'
    else:
        s += f'<line x1="{x0}" y1="{y+6}" x2="{x0}" y2="{y+64}" stroke="{c}" stroke-width="8"/>'
        s += f'<text x="{x0+20}" y="{y+46}" font-size="30" font-weight="700" fill="{INK}">0: every node freed immediately</text>'
s += f'<line x1="{x0}" y1="12" x2="{x0}" y2="{20+4*84}" stroke="{AXIS}" stroke-width="2"/>'
s += '</svg>'
open(f"{out}/unfreed.svg", "w").write(s)

# ================= use-after-free in three steps (poster v5) =================
def uaf_panel(x0, step):
    s = ""
    titles = {1: "1. Both cores use node N", 2: "2. Core 1 unlinks and frees N", 3: "3. Core 0 reads freed N"}
    s += f'<text x="{x0+225}" y="40" text-anchor="middle" font-size="30" font-weight="700" fill="{INK}">{titles[step]}</text>'
    # cores
    s += box(x0 + 10, 70, 190, 70, "#e8f1fc", "Core 0", "reading", stroke=BLUE, s1=28, s2=24)
    s += box(x0 + 250, 70, 190, 70, "#fdece4", "Core 1", "removing" if step == 1 else "freed N", stroke=ORANGE, s1=28, s2=24)
    # nodes A, N, B
    ny = 240
    xs = {"A": x0 + 20, "N": x0 + 175, "B": x0 + 330}
    for k, x in xs.items():
        if k == "N" and step >= 2:
            col = RED if step == 3 else MUTED
            fill = "#fbe1e1" if step == 3 else "#f3f3f0"
            s += f'<rect x="{x}" y="{ny}" width="100" height="64" rx="5" fill="{fill}" stroke="{col}" stroke-width="3" stroke-dasharray="9 6"/>'
            s += f'<text x="{x+50}" y="{ny+32}" text-anchor="middle" font-size="28" font-weight="700" fill="{col}">N</text>'
            s += f'<text x="{x+50}" y="{ny+56}" text-anchor="middle" font-size="20" fill="{col}">freed</text>'
        else:
            s += f'<rect x="{x}" y="{ny}" width="100" height="64" rx="5" fill="#f3f3f0" stroke="{INK2}" stroke-width="3"/>'
            s += f'<text x="{x+50}" y="{ny+42}" text-anchor="middle" font-size="30" font-weight="700" fill="{INK}">{k}</text>'
    if step == 1:
        s += f'<line x1="{xs["A"]+100}" y1="{ny+32}" x2="{xs["N"]-4}" y2="{ny+32}" stroke="{INK2}" stroke-width="3" marker-end="url(#a)"/>'
        s += f'<line x1="{xs["N"]+100}" y1="{ny+32}" x2="{xs["B"]-4}" y2="{ny+32}" stroke="{INK2}" stroke-width="3" marker-end="url(#a)"/>'
    else:
        s += f'<path d="M{xs["A"]+50},{ny+64} C{xs["A"]+80},{ny+130} {xs["B"]+20},{ny+130} {xs["B"]+50},{ny+70}" fill="none" stroke="{INK2}" stroke-width="3" marker-end="url(#a)"/>'
        s += f'<text x="{x0+225}" y="{ny+140}" text-anchor="middle" font-size="24" fill="{INK2}">A now points to B</text>'
    # core pointers
    c0 = RED if step == 3 else BLUE
    s += f'<path d="M{x0+105},142 C{x0+120},190 {x0+200},190 {x0+215},236" fill="none" stroke="{c0}" stroke-width="{5 if step == 3 else 3}" stroke-dasharray="9 6" marker-end="url(#a)"/>'
    if step == 1:
        s += f'<path d="M{x0+345},142 C{x0+330},190 {x0+250},190 {x0+235},236" fill="none" stroke="{ORANGE}" stroke-width="3" stroke-dasharray="9 6" marker-end="url(#a)"/>'
    if step == 3:
        s += f'<text x="{x0+225}" y="{ny+175}" text-anchor="middle" font-size="28" font-weight="700" fill="#a32a2a">use-after-free: crash or wrong data</text>'
    return s
W, H = 1400, 440
s = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" {F}><rect width="{W}" height="{H}" fill="#ffffff"/>{ARROW}'
for i in range(3):
    s += uaf_panel(10 + i * 465, i + 1)
    if i < 2:
        s += f'<line x1="{470 + i*465}" y1="20" x2="{470 + i*465}" y2="{H-20}" stroke="{GRID}" stroke-width="3"/>'
s += '</svg>'
open(f"{out}/uaf_steps.svg", "w").write(s)
