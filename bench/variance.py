"""Summarise repeated runs of one trip: mean, spread, and whether arms differ.

    python3 bench/variance.py [results-dir]    # default: bench/results/latest

The sequence mode gives one observation per cell, so a 100%-vs-88% gap there is a
single line and could be nothing. This reads a `--repeat` batch, where every run of
an arm faced the identical task and the identical seed ledger, and reports the range
alongside the mean — so a difference can be judged against the noise instead of
asserted over it.

Deliberately no p-values. Five runs of a deterministic-ish task is not a sample that
supports significance testing, and dressing it up as one would overstate it. What
this prints is: the spread within each arm, the gap between arms, and whether those
overlap. If they overlap, the honest summary is "not distinguishable at n=5".
"""

import json
import os
import statistics
import sys
from collections import defaultdict

BENCH = os.path.dirname(os.path.abspath(__file__))
ARMS = ["base-strict", "base-fair", "skill"]
LABEL = {"base-strict": "Baseline (no ledger)", "base-fair": "Baseline (+ ledger)",
         "skill": "Plugin skill"}


def spread(vals):
    if not vals:
        return "—"
    lo, hi = min(vals), max(vals)
    mean = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return f"{mean:7.1f}  ±{sd:5.1f}   [{lo:g} – {hi:g}]"


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BENCH, "results", "latest")
    root = os.path.abspath(root)
    metrics = json.load(open(os.path.join(root, "metrics.json")))
    scores = json.load(open(os.path.join(root, "scores.json")))

    runs = [m for m in metrics if "run" in m and m.get("usable", True)]
    by = {(s["arm"], s["run"]): s for s in scores}

    trips = {m["trip"] for m in runs}
    n = max((m["run"] for m in runs), default=0)
    print(f"Repeated-runs summary — trip(s): {', '.join(sorted(trips))}, "
          f"n={n} per arm\n")

    acc, per_line = {}, defaultdict(lambda: defaultdict(list))
    print(f"{'arm':<22}{'verdict accuracy %':>32}")
    for a in ARMS:
        vals = []
        for m in [x for x in runs if x["arm"] == a]:
            s = by.get((a, m["run"]))
            if not s or not s["lines"]:
                continue
            vals.append(100.0 * sum(1 for l in s["lines"] if l["verdict_ok"])
                        / len(s["lines"]))
            for l in s["lines"]:
                per_line[a][l["id"]].append(l["verdict_ok"])
        acc[a] = vals
        print(f"{LABEL[a]:<22}{spread(vals):>32}")

    # The money figure. A reviewer that varies here varies in what it actually pays,
    # which matters more than the accuracy percentage.
    print(f"\n{'arm':<22}{'THB approved (same input!)':>36}")
    for a in ARMS:
        vals = [by[(a, m["run"])]["total_claimable"] for m in runs
                if m["arm"] == a and (a, m["run"]) in by]
        line = spread(vals)
        if vals and min(vals) > 0 and max(vals) / min(vals) >= 2:
            line += f"   <-- {max(vals)/min(vals):.0f}x spread"
        print(f"{LABEL[a]:<22}{line:>36}")

    print(f"\n{'arm':<22}{'total tokens':>30}{'cost USD':>26}")
    for a in ARMS:
        rs = [x for x in runs if x["arm"] == a]
        print(f"{LABEL[a]:<22}"
              f"{spread([x['tokens_total']['total_tokens'] for x in rs]):>30}"
              f"{spread([x['cost_usd'] for x in rs if x.get('cost_usd')]):>26}")

    print(f"\n{'arm':<22}{'wall seconds':>30}{'Agent calls':>22}")
    for a in ARMS:
        rs = [x for x in runs if x["arm"] == a]
        print(f"{LABEL[a]:<22}"
              f"{spread([(x.get('duration_ms') or 0)/1000 for x in rs]):>30}"
              f"{spread([x['agent_call_count'] for x in rs]):>22}")

    # Do the arms actually separate, or do their ranges overlap?
    print("\nDoes the accuracy gap survive the spread?")
    for i, a in enumerate(ARMS):
        for b in ARMS[i+1:]:
            va, vb = acc.get(a, []), acc.get(b, [])
            if not va or not vb:
                continue
            gap = statistics.mean(vb) - statistics.mean(va)
            overlap = not (max(va) < min(vb) or max(vb) < min(va))
            verdict = ("RANGES OVERLAP — not distinguishable at this n"
                       if overlap else "ranges are disjoint — a real difference")
            print(f"  {LABEL[a]} vs {LABEL[b]}: {gap:+.1f} pts — {verdict}")

    # Which specific lines are unstable? That is where the noise lives.
    print("\nPer-line stability (lines that did not answer the same way every time):")
    any_flap = False
    for a in ARMS:
        for lid, oks in sorted(per_line[a].items()):
            if len(set(oks)) > 1:
                any_flap = True
                print(f"  {LABEL[a]:<22} {lid:<8} "
                      f"{sum(oks)}/{len(oks)} runs correct  -> unstable")
    if not any_flap:
        print("  none — every line answered identically across all repetitions.")


if __name__ == "__main__":
    main()
