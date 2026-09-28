"""Render the benchmark results as a single self-contained HTML report.

    python3 bench/report.py [results-dir]     # default: bench/results/latest
    -> bench/REPORT.html

Reads metrics.json and scores.json. No network, no build step, no dependencies:
the charts are inline SVG generated here, so the file opens from disk and can be
committed next to the code it measures.
"""

import html
import json
import os
import sys
from collections import defaultdict

BENCH = os.path.dirname(os.path.abspath(__file__))

ARM_LABEL = {
    "base-strict": "Baseline (no ledger)",
    "base-fair": "Baseline (+ ledger)",
    "skill": "Plugin skill",
    "skill-noagents": "Plugin, agents off",
}
ARM_NOTE = {
    "base-strict": "Policy pasted into the prompt. No prior-claims ledger — the arm "
                   "as originally specified.",
    "base-fair": "Same, plus the previously approved rows pasted in, so the ledger "
                 "is not the differentiator.",
    "skill": "/setup-expense-policy once, then /expense-review. Stored policy on "
             "disk and a claims.csv ledger carried forward between runs.",
    "skill-noagents": "Identical, with the Agent tool denied.",
}
# Categorical slots 1-3 from the design system's default theme. Validated all-pairs
# in both modes (worst CVD dE 9.2 light / 9.4 dark, normal-vision 24.0 / 20.9).
SERIES = {
    "base-strict": ("--series-1", "#2a78d6", "#3987e5"),
    "base-fair": ("--series-2", "#eb6834", "#d95926"),
    "skill": ("--series-3", "#1baf7a", "#199e70"),
    "skill-noagents": ("--series-4", "#eda100", "#c98500"),
}
ARM_ORDER = ["base-strict", "base-fair", "skill", "skill-noagents"]


def esc(x):
    return html.escape(str(x))


def fmt(n, suffix=""):
    if n is None:
        return "—"
    if isinstance(n, float) and not n.is_integer():
        return f"{n:,.2f}{suffix}"
    return f"{n:,.0f}{suffix}"


def grouped_bars(series, categories, title, subtitle, unit="", fmt_val=fmt):
    """Grouped bar chart. Direct labels on every bar — the light-mode contrast
    WARN on slot 3 makes labels mandatory, not optional."""
    arms = [a for a in ARM_ORDER if a in series]
    if not arms or not categories:
        return ""
    vals = [v for a in arms for v in series[a] if v is not None]
    if not vals:
        return ""
    vmax = max(vals) or 1

    # A wide viewBox keeps the upscale near 1:1 in a ~1000px column, so strokes and
    # labels stay crisp and the bars read thin rather than chunky.
    # A wide viewBox keeps the upscale near 1:1 in a ~1000px column, so strokes and
    # labels stay crisp and the bars read thin rather than chunky. GAP is the pitch
    # between bars in a group: it must exceed the width of a direct label, or equal
    # values collide into "100%100%100%". 2px is the floor for fill separation, not
    # the target here.
    GAP = 8
    pad_l, pad_r, pad_t, pad_b = 10, 10, 16, 40
    gw, h = 260, 230
    w = pad_l + pad_r + gw * len(categories)
    bw = min(24, (gw - 60) / max(1, len(arms)) - GAP)
    plot_h = h - pad_t - pad_b

    parts = [f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" '
             f'aria-label="{esc(title)}">']
    for frac in (0, 0.5, 1.0):
        y = pad_t + plot_h * (1 - frac)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-pad_r}" y2="{y:.1f}" '
                     f'class="grid"/>')
    for ci, cat in enumerate(categories):
        gx = pad_l + gw * ci
        group_w = bw * len(arms) + GAP * (len(arms) - 1)
        x0 = gx + (gw - group_w) / 2
        for ai, arm in enumerate(arms):
            v = series[arm][ci] if ci < len(series[arm]) else None
            if v is None:
                continue
            bh = max(1.5, plot_h * (v / vmax))
            x = x0 + ai * (bw + GAP)
            y = pad_t + plot_h - bh
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                f'rx="4" fill="var({SERIES[arm][0]})"><title>{esc(ARM_LABEL[arm])} · '
                f'{esc(cat)}: {esc(fmt_val(v))}{esc(unit)}</title></rect>')
            parts.append(
                f'<text x="{x + bw/2:.1f}" y="{y - 4:.1f}" class="bar-label">'
                f'{esc(fmt_val(v))}</text>')
        parts.append(f'<text x="{gx + gw/2:.1f}" y="{h - 12}" class="cat-label">'
                     f'{esc(cat)}</text>')
    parts.append("</svg>")

    legend = "".join(
        f'<span class="key"><i style="background:var({SERIES[a][0]})"></i>'
        f'{esc(ARM_LABEL[a])}</span>' for a in arms)
    return (f'<figure class="viz-root"><figcaption><h3>{esc(title)}</h3>'
            f'<p>{esc(subtitle)}</p></figcaption>'
            f'<div class="legend">{legend}</div>'
            f'<div class="chart-wrap">{"".join(parts)}</div></figure>')


def build(root):
    metrics = json.load(open(os.path.join(root, "metrics.json")))
    scores_path = os.path.join(root, "scores.json")
    scores = json.load(open(scores_path)) if os.path.exists(scores_path) else []
    by_key = {(s["arm"], s["run"]): s for s in scores}

    # A run killed by a usage limit has a result event and zero of everything;
    # charting it would show a real arm collapsing to nothing.
    metrics = [m for m in metrics if m.get("usable", True)]
    runs = [m for m in metrics if "run" in m]
    setups = [m for m in metrics if "run" not in m]
    arms = [a for a in ARM_ORDER if any(r["arm"] == a for r in runs)]
    run_nums = sorted({r["run"] for r in runs})
    cats = [f"Run {n}" for n in run_nums]

    def series_of(fn):
        out = {}
        for a in arms:
            row = []
            for n in run_nums:
                rec = next((r for r in runs if r["arm"] == a and r["run"] == n), None)
                row.append(fn(rec) if rec else None)
            out[a] = row
        return out

    tok = series_of(lambda r: r["tokens_total"]["total_tokens"])
    out_tok = series_of(lambda r: r["tokens_total"]["output_tokens"])
    cost = series_of(lambda r: r.get("cost_usd"))
    secs = series_of(lambda r: (r.get("duration_ms") or 0) / 1000)
    agents = series_of(lambda r: r["agent_call_count"])

    def acc(r):
        s = by_key.get((r["arm"], r["run"]))
        if not s or not s["lines"]:
            return None
        return 100.0 * sum(1 for l in s["lines"] if l["verdict_ok"]) / len(s["lines"])
    accuracy = series_of(acc)

    def checks(r):
        s = by_key.get((r["arm"], r["run"]))
        if not s:
            return None
        return 100.0 * s["summary"]["passed"] / max(1, s["summary"]["total"])
    checkpct = series_of(checks)

    meta = runs[0] if runs else {}
    setup_cost = sum(s.get("cost_usd") or 0 for s in setups)
    setup_tok = sum(s["tokens_total"]["total_tokens"] for s in setups)

    # ---- headline deltas ----------------------------------------------------
    def total(d, a):
        return sum(v for v in d.get(a, []) if v is not None)

    cards = []
    if "skill" in arms and "base-strict" in arms:
        t_sk, t_bs = total(tok, "skill"), total(tok, "base-strict")
        c_sk, c_bs = total(cost, "skill"), total(cost, "base-strict")
        a_sk = [v for v in accuracy.get("skill", []) if v is not None]
        a_bs = [v for v in accuracy.get("base-strict", []) if v is not None]
        cards = [
            ("Verdict accuracy", f"{sum(a_sk)/len(a_sk):.0f}%" if a_sk else "—",
             f"vs {sum(a_bs)/len(a_bs):.0f}% baseline" if a_bs else "",
             "good" if a_sk and a_bs and sum(a_sk)/len(a_sk) > sum(a_bs)/len(a_bs) else ""),
            ("Tokens, all runs", fmt(t_sk),
             f"{(t_sk/t_bs - 1)*100:+.0f}% vs baseline" if t_bs else "", ""),
            ("Cost, all runs", f"${c_sk:,.2f}",
             f"${c_bs:,.2f} baseline" + (f" · +${setup_cost:,.2f} one-off setup"
                                         if setup_cost else ""), ""),
            ("Subagents called", fmt(sum(v or 0 for v in agents.get("skill", []))),
             f"{fmt(sum(v or 0 for v in agents.get('base-strict', [])))} in baseline", ""),
        ]

    figs = [
        grouped_bars(accuracy, cats, "Verdict accuracy per run",
                     "Share of submitted lines given an acceptable verdict, judged "
                     "from claims.csv and exceptions-queue.csv.", "%",
                     lambda v: f"{v:.0f}%"),
        grouped_bars(checkpct, cats, "All graded checks passed",
                     "Format conformance, ledger hygiene, per-line verdicts and "
                     "amounts, totals, arithmetic and invariants.", "%",
                     lambda v: f"{v:.0f}%"),
        grouped_bars(tok, cats, "Total tokens per run",
                     "Input + output + cache, parent session and every subagent "
                     "transcript, deduplicated per API message."),
        grouped_bars(out_tok, cats, "Output tokens per run",
                     "Generated tokens only — the part that is not cache-discounted."),
        grouped_bars(cost, cats, "Cost per run (USD)",
                     "From each run's result event, at list prices.", "",
                     lambda v: f"${v:,.2f}"),
        grouped_bars(secs, cats, "Wall-clock seconds per run",
                     "End to end, as reported by the run's result event.", "s",
                     lambda v: f"{v:,.0f}"),
        grouped_bars(agents, cats, "Subagent invocations per run",
                     "Count of Agent tool calls in the session transcript. A baseline "
                     "has no agents to call."),
    ]

    # ---- per-line detail ----------------------------------------------------
    line_tables = []
    for n in run_nums:
        any_s = next((by_key.get((a, n)) for a in arms if by_key.get((a, n))), None)
        if not any_s:
            continue
        trip = any_s["trip"]
        head = "".join(f"<th>{esc(ARM_LABEL[a])}</th>" for a in arms)
        body = []
        for i, ln in enumerate(any_s["lines"]):
            cells = []
            for a in arms:
                s = by_key.get((a, n))
                l = s["lines"][i] if s and i < len(s["lines"]) else None
                if not l:
                    cells.append('<td class="na">—</td>')
                    continue
                mark = "✓" if l["verdict_ok"] else "✗"
                cls = "ok" if l["verdict_ok"] else "bad"
                got = "/".join(l["found"]) or "no decision"
                cells.append(f'<td class="{cls}"><b>{mark}</b> <span>{esc(got)}</span></td>')
            probe = " probe" if "PROBE" in (ln.get("why") or "") else ""
            body.append(
                f'<tr class="line{probe}"><td class="id">{esc(ln["id"])}</td>'
                f'<td class="exp">{esc("/".join(ln["expected"]))}</td>'
                f'{"".join(cells)}</tr>'
                f'<tr class="why"><td></td><td colspan="{len(arms)+1}">'
                f'{esc(ln.get("why") or "")}</td></tr>')
        line_tables.append(
            f'<h3>Run {n} — {esc(trip)}</h3>'
            f'<table class="lines"><thead><tr><th>Line</th><th>Expected</th>{head}</tr>'
            f'</thead><tbody>{"".join(body)}</tbody></table>')

    # ---- invariants ---------------------------------------------------------
    inv_names = sorted({k for s in scores for k in s["invariants"]})
    inv_rows = []
    for a in arms:
        cells = []
        for k in inv_names:
            vals = [s["invariants"][k] for s in scores
                    if s["arm"] == a and k in s["invariants"]]
            if not vals:
                cells.append('<td class="na">—</td>')
                continue
            bad = [v for v in vals if not v["ok"]]
            ev = "; ".join(str(e) for v in bad for e in (v["evidence"] or []))[:200]
            cells.append(
                f'<td class="{"ok" if not bad else "bad"}">'
                f'<b>{len(vals)-len(bad)}/{len(vals)}</b>'
                + (f'<span class="ev">{esc(ev)}</span>' if ev else "") + "</td>")
        inv_rows.append(f'<tr><th>{esc(ARM_LABEL[a])}</th>{"".join(cells)}</tr>')
    inv_head = "".join(f'<th>{esc(k.replace("_", " "))}</th>' for k in inv_names)

    # ---- agent evidence -----------------------------------------------------
    agent_ev = []
    for r in runs:
        if not r["agent_calls"] and not r["hook_agent_log"]:
            continue
        calls = "".join(
            f'<li><code>{esc(c["subagent_type"])}</code> — {esc(c["description"])}'
            f'<div class="prompt">{esc(c["prompt_head"])}…</div></li>'
            for c in r["agent_calls"])
        subs = "".join(
            f'<tr><td><code>{esc(s["agent_type"] or "?")}</code></td>'
            f'<td>{fmt(s["usage"]["total_tokens"])}</td>'
            f'<td>{fmt(s["usage"]["output_tokens"])}</td>'
            f'<td>{fmt((s["turn_ms"] or 0)/1000, "s")}</td></tr>'
            for s in r["subagent_detail"])
        agent_ev.append(
            f'<details open><summary><b>{esc(ARM_LABEL[r["arm"]])}</b>, run '
            f'{r["run"]} — {r["agent_call_count"]} Agent call(s), '
            f'{r["hook_agent_log_lines"]} logged by the hook</summary>'
            f'<ol class="calls">{calls}</ol>'
            + (f'<table class="sub"><thead><tr><th>Subagent</th><th>Total tokens</th>'
               f'<th>Output</th><th>Active</th></tr></thead><tbody>{subs}</tbody>'
               f'</table>' if subs else "")
            + "</details>")

    # ---- raw table ----------------------------------------------------------
    raw_rows = []
    for a in arms:
        for n in run_nums:
            r = next((x for x in runs if x["arm"] == a and x["run"] == n), None)
            if not r:
                continue
            s = by_key.get((a, n))
            t = r["tokens_total"]
            raw_rows.append(
                f'<tr><td>{esc(ARM_LABEL[a])}</td><td>{n}</td><td>{esc(r["trip"])}</td>'
                f'<td>{fmt(t["input_tokens"])}</td><td>{fmt(t["output_tokens"])}</td>'
                f'<td>{fmt(t["cache_read_input_tokens"])}</td>'
                f'<td>{fmt(t["cache_creation_input_tokens"])}</td>'
                f'<td><b>{fmt(t["total_tokens"])}</b></td>'
                f'<td>{"$%.3f" % r["cost_usd"] if r.get("cost_usd") else "—"}</td>'
                f'<td>{fmt(r.get("num_turns"))}</td>'
                f'<td>{fmt((r.get("duration_ms") or 0)/1000, "s")}</td>'
                f'<td>{r["agent_call_count"]}</td>'
                f'<td>{fmt(s["total_claimable"]) if s else "—"}</td>'
                f'<td>{s["summary"]["passed"]}/{s["summary"]["total"]}'
                f'</td><td>{r.get("permission_denials", 0)}</td></tr>')

    arm_cards = "".join(
        f'<div class="arm"><i style="background:var({SERIES[a][0]})"></i>'
        f'<b>{esc(ARM_LABEL[a])}</b><p>{esc(ARM_NOTE[a])}</p></div>' for a in arms)

    kpi = "".join(
        f'<div class="kpi {cls}"><span class="k">{esc(k)}</span>'
        f'<span class="v">{esc(v)}</span><span class="s">{esc(s)}</span></div>'
        for k, v, s, cls in cards)

    return TEMPLATE.format(
        kpi=kpi, arm_cards=arm_cards, figs="".join(f for f in figs if f),
        line_tables="".join(line_tables),
        inv_head=inv_head, inv_rows="".join(inv_rows),
        agent_ev="".join(agent_ev) or "<p class='na'>No subagent activity recorded.</p>",
        raw_rows="".join(raw_rows),
        model=esc(meta.get("model", "?")), effort=esc(meta.get("effort", "?")),
        policy=esc(str(meta.get("policy", "a")).upper()),
        filing=esc(meta.get("filing_date", "")),
        stamp=esc(meta.get("stamp", "")),
        n_runs=len(runs),
        setup_line=(f"Plugin setup ran once before run 1: {fmt(setup_tok)} tokens, "
                    f"${setup_cost:,.2f}. That cost is not repeated per run."
                    if setups else ""),
    )


TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Expense Review Benchmark</title>
<style>
:root {{
  color-scheme: light;
  --bg: #fcfcfb; --panel: #ffffff; --line: #e4e3df;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #77756f;
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --series-4: #eda100;
  --good: #0ca30c; --critical: #d03b3b;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --bg: #1a1a19; --panel: #232322; --line: #383835;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #96948c;
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
    --good: #0ca30c; --critical: #d03b3b;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --bg: #1a1a19; --panel: #232322; --line: #383835;
  --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #96948c;
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #c98500;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--text-primary);
  font: 15px/1.6 ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 48px 16px 96px; }}
h1 {{ font-size: 30px; line-height: 1.2; margin: 0 0 6px; letter-spacing: -.02em; }}
h2 {{ font-size: 19px; margin: 48px 0 6px; letter-spacing: -.01em; }}
h3 {{ font-size: 15px; margin: 24px 0 4px; }}
p.sub {{ color: var(--text-secondary); margin: 0 0 8px; }}
.meta {{ color: var(--text-muted); font-size: 13px; margin: 12px 0 0; }}
.meta code {{ color: var(--text-secondary); }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
         gap: 10px; margin: 28px 0 8px; }}
.kpi {{ background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
        padding: 14px 16px; display: flex; flex-direction: column; gap: 2px; }}
.kpi .k {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase;
           letter-spacing: .05em; }}
.kpi .v {{ font-size: 27px; font-weight: 640; letter-spacing: -.02em; }}
.kpi .s {{ font-size: 13px; color: var(--text-secondary); }}
.kpi.good .v {{ color: var(--good); }}
.arms {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
         gap: 10px; margin: 14px 0; }}
.arm {{ background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
        padding: 12px 14px; }}
.arm i {{ display: inline-block; width: 10px; height: 10px; border-radius: 3px;
          margin-right: 7px; vertical-align: middle; }}
.arm p {{ margin: 5px 0 0; font-size: 13px; color: var(--text-secondary); }}
figure {{ margin: 22px 0 0; background: var(--panel); border: 1px solid var(--line);
          border-radius: 12px; padding: 16px 16px 8px; }}
figcaption h3 {{ margin: 0; font-size: 15px; }}
figcaption p {{ margin: 3px 0 10px; font-size: 13px; color: var(--text-secondary); }}
.legend {{ display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 8px; }}
.key {{ font-size: 12px; color: var(--text-secondary); display: inline-flex;
        align-items: center; gap: 6px; }}
.key i {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
.chart-wrap {{ overflow-x: auto; }}
.chart {{ width: 100%; min-width: 320px; height: auto; display: block; }}
.grid {{ stroke: var(--line); stroke-width: 1; }}
.bar-label {{ font-size: 11px; fill: var(--text-secondary); text-anchor: middle;
              font-weight: 600; }}
.cat-label {{ font-size: 12px; fill: var(--text-secondary); text-anchor: middle; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin: 8px 0 0; }}
th, td {{ text-align: left; padding: 7px 9px; border-bottom: 1px solid var(--line);
          vertical-align: top; }}
th {{ color: var(--text-muted); font-weight: 600; font-size: 12px;
      text-transform: uppercase; letter-spacing: .04em; }}
tbody tr:hover {{ background: color-mix(in oklab, var(--panel) 80%, var(--line)); }}
td.ok b {{ color: var(--good); }}
td.bad b {{ color: var(--critical); }}
td.ok span, td.bad span {{ color: var(--text-secondary); font-size: 12px; }}
td.na, .na {{ color: var(--text-muted); }}
td.id {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
td.exp {{ color: var(--text-secondary); font-size: 12px; }}
tr.why td {{ border-bottom: 1px solid var(--line); padding-top: 0; font-size: 12px;
             color: var(--text-muted); }}
tr.probe td.id {{ font-weight: 700; }}
tr.probe td.id::after {{ content: " ●"; color: var(--series-2); }}
.scroll {{ overflow-x: auto; }}
.scroll table {{ min-width: 860px; }}
details {{ background: var(--panel); border: 1px solid var(--line);
           border-radius: 10px; padding: 12px 14px; margin: 10px 0; }}
summary {{ cursor: pointer; }}
.calls {{ margin: 10px 0; padding-left: 20px; }}
.calls li {{ margin-bottom: 8px; }}
.prompt {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px;
           color: var(--text-muted); background: var(--bg); border-radius: 6px;
           padding: 7px 9px; margin-top: 4px; white-space: pre-wrap; }}
.ev {{ display: block; font-size: 11px; color: var(--text-muted); margin-top: 3px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; }}
.note {{ background: var(--panel); border: 1px solid var(--line); border-left: 3px solid
         var(--series-2); border-radius: 8px; padding: 12px 14px; margin: 14px 0;
         font-size: 13.5px; color: var(--text-secondary); }}
.note b {{ color: var(--text-primary); }}
footer {{ margin-top: 56px; padding-top: 16px; border-top: 1px solid var(--line);
          font-size: 12.5px; color: var(--text-muted); }}
@media (max-width: 640px) {{ .wrap {{ padding: 28px 16px 64px; }} h1 {{ font-size: 24px; }} }}
</style></head><body><div class="wrap">

<h1>Expense claim review — with the plugin vs. without</h1>
<p class="sub">Finance-side review only. The same three submissions, reviewed three
times by each arm, every run in a fresh session with no shared context.</p>
<p class="meta">Model <code>{model}</code> · effort <code>{effort}</code> ·
policy <code>{policy}</code> · filing date <code>{filing}</code> ·
{n_runs} runs · batch <code>{stamp}</code></p>

<div class="kpis">{kpi}</div>

<h2>The arms</h2>
<div class="arms">{arm_cards}</div>
<div class="note">{setup_line}</div>

<h2>Results</h2>
{figs}

<h2>Line-by-line verdicts</h2>
<p class="sub">Read from <code>claims.csv</code> and <code>exceptions-queue.csv</code>,
not from the prose report, so an arm that has never seen the plugin's vocabulary is
judged on the same footing. Rows marked ● are the designed probes.</p>
{line_tables}

<h2>Invariants — the answers that must never be given</h2>
<p class="sub">A wrong number here is worse than no number. Policy A contains no
digits at all, so any cap it is measured against was invented.</p>
<div class="scroll"><table><thead><tr><th>Arm</th>{inv_head}</tr></thead>
<tbody>{inv_rows}</tbody></table></div>

<h2>Did it really call agents?</h2>
<p class="sub">Two independent records: <code>Agent</code> tool-use blocks in the
session transcript, and the plugin's own <code>PreToolUse</code> hook writing
<code>agent-invocations.log</code>. Subagent tokens come from the separate
<code>subagents/*.jsonl</code> transcripts and would be included in every total above.
<b>No subagent was invoked in any run.</b> The plugin defines four agents, and the
skill ran the whole review inline instead of delegating to them. The negative is
provable rather than assumed: the sibling <code>PostToolUse</code> hook wrote
<code>audit-log.txt</code> in the same runs, so hooks were live and an
<code>Agent</code> call would have been recorded.</p>
{agent_ev}

<h2>All measurements</h2>
<div class="scroll"><table><thead><tr>
<th>Arm</th><th>Run</th><th>Trip</th><th>In</th><th>Out</th><th>Cache read</th>
<th>Cache write</th><th>Total</th><th>Cost</th><th>Turns</th><th>Time</th>
<th>Agents</th><th>Claimed</th><th>Checks</th><th>Denials</th>
</tr></thead><tbody>{raw_rows}</tbody></table></div>

<footer>Generated by <code>bench/report.py</code> from <code>metrics.json</code> and
<code>scores.json</code>. Regenerate with
<code>bash bench/run.sh &amp;&amp; python3 bench/measure.py &amp;&amp;
python3 bench/score.py &amp;&amp; python3 bench/report.py</code>.</footer>
</div></body></html>
"""


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BENCH, "results", "latest")
    root = os.path.abspath(root)
    if not os.path.exists(os.path.join(root, "metrics.json")):
        sys.exit("run bench/measure.py first")
    out = os.path.join(BENCH, "REPORT.html")
    with open(out, "w") as f:
        f.write(build(root))
    print(f"wrote {out}  ({os.path.getsize(out):,} bytes)")


if __name__ == "__main__":
    main()
