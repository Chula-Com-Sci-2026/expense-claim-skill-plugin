import json, random, textwrap

random.seed(7)
def nonce(): return random.randint(1, 2**31)

els = []
NODE = {}

BASE = dict(angle=0, fillStyle="solid", strokeWidth=2, strokeStyle="solid",
            roughness=1, opacity=100, groupIds=[], frameId=None,
            roundness={"type": 3}, isDeleted=False, boundElements=[],
            updated=1, link=None, locked=False)

def wrap(text, width, fs):
    out = []
    for para in text.split("\n"):
        cols = max(6, int((width - 20) / (fs * 0.52)))
        out += textwrap.wrap(para, cols) or [""]
    return out

def node(nid, x, y, w, h, label, stroke, bg, shape="rectangle", fs=16, frame=None):
    tid = nid + "_t"
    lines = wrap(label, w, fs)
    th = len(lines) * fs * 1.25
    els.append(dict(BASE, id=nid, type=shape, x=x, y=y, width=w, height=h,
                    strokeColor=stroke, backgroundColor=bg, seed=nonce(),
                    versionNonce=nonce(), version=1, frameId=frame,
                    boundElements=[{"id": tid, "type": "text"}]))
    els.append(dict(BASE, id=tid, type="text", x=x + 10, y=y + (h - th) / 2,
                    width=w - 20, height=th, strokeColor=stroke,
                    backgroundColor="transparent", seed=nonce(),
                    versionNonce=nonce(), version=1, frameId=frame,
                    roundness=None, boundElements=[],
                    text="\n".join(lines), originalText=label, fontSize=fs,
                    fontFamily=1, textAlign="center", verticalAlign="middle",
                    containerId=nid, lineHeight=1.25, autoResize=False))
    NODE[nid] = (x, y, w, h)

def edge(a, b, label="", dashed=False, stroke="#1e1e1e", bend=None):
    ax, ay, aw, ah = NODE[a]; bx, by, bw, bh = NODE[b]
    acx, acy = ax + aw / 2, ay + ah / 2
    bcx, bcy = bx + bw / 2, by + bh / 2
    if abs(bcy - acy) >= abs(bcx - acx):
        sy = ay + ah if bcy > acy else ay
        ey = by if bcy > acy else by + bh
        sx, ex = acx, bcx
    else:
        sx = ax + aw if bcx > acx else ax
        ex = bx if bcx > acx else bx + bw
        sy, ey = acy, bcy
    aid = f"e_{a}_{b}"
    pts = [[0, 0], [ex - sx, ey - sy]] if not bend else [[0, 0], bend, [ex - sx, ey - sy]]
    arrow = dict(BASE, id=aid, type="arrow", x=sx, y=sy,
                 width=abs(ex - sx), height=abs(ey - sy),
                 strokeColor=stroke, backgroundColor="transparent",
                 strokeStyle="dashed" if dashed else "solid",
                 seed=nonce(), versionNonce=nonce(), version=1,
                 roundness={"type": 2}, points=pts,
                 lastCommittedPoint=None, elbowed=False,
                 startBinding={"elementId": a, "focus": 0, "gap": 4},
                 endBinding={"elementId": b, "focus": 0, "gap": 4},
                 startArrowhead=None, endArrowhead="arrow", boundElements=[])
    if label:
        lid = aid + "_t"
        arrow["boundElements"] = [{"id": lid, "type": "text"}]
        lw, fs = max(70, len(label) * 9), 14
        els.append(arrow)
        els.append(dict(BASE, id=lid, type="text",
                        x=(sx + ex) / 2 - lw / 2, y=(sy + ey) / 2 - 10,
                        width=lw, height=fs * 1.25, strokeColor=stroke,
                        backgroundColor="transparent", seed=nonce(),
                        versionNonce=nonce(), version=1, roundness=None,
                        text=label, originalText=label, fontSize=fs,
                        fontFamily=1, textAlign="center", verticalAlign="middle",
                        containerId=aid, lineHeight=1.25, autoResize=False))
    else:
        els.append(arrow)
    for n, kind in ((a, "arrow"), (b, "arrow")):
        for e in els:
            if e["id"] == n:
                e["boundElements"] = e.get("boundElements", []) + [{"id": aid, "type": kind}]

def frame(fid, x, y, w, h, name):
    els.append(dict(BASE, id=fid, type="frame", x=x, y=y, width=w, height=h,
                    strokeColor="#bbb", backgroundColor="transparent",
                    seed=nonce(), versionNonce=nonce(), version=1,
                    roundness=None, name=name))

# ---- palettes
EMP_S, EMP_B = "#1971c2", "#a5d8ff"
FIN_S, FIN_B = "#2f9e44", "#b2f2bb"
DEC_S, DEC_B = "#f08c00", "#ffec99"
OUT_S, OUT_B = "#1e1e1e", "#ffffff"
HOOK_S, HOOK_B = "#e03131", "#ffc9c9"
CFG_S, CFG_B = "#6741d9", "#d0bfff"

frame("fr_emp", 40, 40, 560, 940, "EMPLOYEE")
frame("fr_fin", 700, 40, 780, 1120, "FINANCE")

# ---- employee lane
node("A", 180, 90, 280, 60, "/expense-submit", EMP_S, EMP_B, frame="fr_emp")
node("B", 180, 200, 280, 90, "Receipts given?", DEC_S, DEC_B, "diamond", frame="fr_emp")
node("C", 80, 200, 90, 90, "Ask: photos, PDFs, or folder path", EMP_S, "#ffffff", fs=12, frame="fr_emp")
node("D", 150, 340, 340, 80, "receipt-reader: extract date, vendor, description, category, price, currency", EMP_S, EMP_B, fs=14, frame="fr_emp")
node("E", 150, 470, 340, 80, "Self-check flags — advisory only, never 'approved'", EMP_S, EMP_B, fs=14, frame="fr_emp")
node("F", 180, 600, 280, 60, "submission.csv", OUT_S, OUT_B, fs=14, frame="fr_emp")
node("G", 150, 710, 340, 70, "Google Sheet:\nExpense Submission", EMP_S, EMP_B, fs=14, frame="fr_emp")

edge("A", "B"); edge("B", "C", "No"); edge("C", "D")
edge("B", "D", "Yes"); edge("D", "E"); edge("E", "F"); edge("F", "G")

# ---- finance lane
node("H", 900, 90, 300, 60, "/expense-review", FIN_S, FIN_B, frame="fr_fin")
node("I", 900, 200, 300, 90, "Policy configured?", DEC_S, DEC_B, "diamond", frame="fr_fin")
node("J", 1250, 205, 200, 80, "/setup-expense-policy — attach PDF or write rules", CFG_S, CFG_B, fs=12, frame="fr_fin")
node("K", 900, 340, 300, 70, "Load ~/.expense-claim-review/policy.md", FIN_S, FIN_B, fs=13, frame="fr_fin")
node("L", 880, 450, 340, 80, "Re-read original receipts — verify, do not trust submission", FIN_S, FIN_B, fs=14, frame="fr_fin")
node("M", 880, 570, 340, 80, "policy-checker: one verdict per line + policy clause", FIN_S, FIN_B, fs=14, frame="fr_fin")
node("N", 930, 690, 240, 60, "claim-writer", FIN_S, FIN_B, fs=14, frame="fr_fin")
node("O", 740, 810, 200, 80, "EXPENSE_CLAIM_REVIEW.md", OUT_S, OUT_B, fs=12, frame="fr_fin")
node("P", 960, 810, 180, 80, "claims.csv (approved only)", OUT_S, OUT_B, fs=12, frame="fr_fin")
node("Q", 1170, 810, 190, 80, "exceptions-queue.csv (human decision)", OUT_S, OUT_B, fs=12, frame="fr_fin")
node("R", 900, 960, 300, 70, "Google Sheet:\nExpense Review", FIN_S, FIN_B, fs=14, frame="fr_fin")
node("S", 1230, 950, 230, 100, "Hooks: block VIOLATION into claims.csv; log every write to audit-log.txt", HOOK_S, HOOK_B, fs=12, frame="fr_fin")

edge("H", "I"); edge("I", "J", "No"); edge("J", "I")
edge("I", "K", "Yes"); edge("K", "L"); edge("L", "M"); edge("M", "N")
edge("N", "O"); edge("N", "P"); edge("N", "Q")
edge("P", "R")
edge("S", "N", dashed=True, stroke=HOOK_S)

# cross-lane handoffs
edge("G", "H", "handoff: submission Sheet", dashed=True, stroke="#868e96")
edge("R", "G", "outcome back to employee", dashed=True, stroke="#868e96")

scene = {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
         "elements": els,
         "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
         "files": {}}
open("docs/flow.excalidraw", "w").write(json.dumps(scene, indent=2))
print("elements:", len(els))
