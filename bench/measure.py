"""Turn each benchmark run into a metrics record.

    python3 bench/measure.py [results-dir]      # default: bench/results/latest

Two independent sources, deliberately:

  the `result` event   at the end of stream.jsonl — Claude Code's own totals for
                       cost, turns and duration. Authoritative, cheap.
  the session JSONL    ~/.claude/projects/<slug>/<session-id>.jsonl plus
                       <session-id>/subagents/*.jsonl — needed for the per-subagent
                       breakdown the result event does not carry.

Writes metrics.json next to each run and a combined metrics.json at the root.

Three traps this file exists to get right:

1. Assistant usage rows are duplicated per content block. Group by message.id and
   keep the row with the highest apiBlockIndex — input and cache fields are stable
   across blocks, but output_tokens only reaches its final value on the last one.
   Summing raw double-counts input ~2x; taking the first block can undercount
   output by orders of magnitude.
2. Subagent tokens live in separate files under <session-id>/subagents/. A parent
   transcript alone omits every delegated call, which would understate the arm that
   actually delegates.
3. The subagent-spawning tool is named `Agent`, not `Task`.
"""

import glob
import json
import os
import sys
from collections import defaultdict

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")
BENCH = os.path.dirname(os.path.abspath(__file__))

USAGE_FIELDS = ("input_tokens", "output_tokens",
                "cache_creation_input_tokens", "cache_read_input_tokens")


def read_jsonl(path):
    out = []
    try:
        with open(path) as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return out


def dedupe_usage(rows):
    """Sum usage across assistant lines, one row per API message."""
    best = {}
    for r in rows:
        if r.get("type") != "assistant":
            continue
        msg = r.get("message") or {}
        usage = msg.get("usage")
        mid = msg.get("id")
        if not usage or not mid:
            continue
        # Prefer apiBlockIndex; fall back to output_tokens for older transcripts
        # that predate the field. Both pick the final block.
        rank = (r.get("apiBlockIndex", -1), usage.get("output_tokens", 0))
        if mid not in best or rank > best[mid][0]:
            best[mid] = (rank, usage, msg.get("model"))

    totals = dict.fromkeys(USAGE_FIELDS, 0)
    by_model = defaultdict(lambda: dict.fromkeys(USAGE_FIELDS, 0))
    for _, usage, model in best.values():
        for k in USAGE_FIELDS:
            v = usage.get(k) or 0
            totals[k] += v
            by_model[model or "unknown"][k] += v
    totals["messages"] = len(best)
    totals["total_tokens"] = sum(totals[k] for k in USAGE_FIELDS)
    return totals, {m: dict(v) for m, v in by_model.items()}


def find_session_file(session_id):
    hits = glob.glob(os.path.join(PROJECTS, "*", session_id + ".jsonl"))
    return hits[0] if hits else None


def agent_calls(rows):
    """Every subagent launched from this transcript, with its instruction."""
    calls = []
    for r in rows:
        if r.get("type") != "assistant":
            continue
        for block in (r.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") != "Agent":
                continue
            inp = block.get("input") or {}
            calls.append({
                "tool_use_id": block.get("id"),
                "subagent_type": inp.get("subagent_type") or "(unspecified)",
                "description": inp.get("description", ""),
                "prompt_head": (inp.get("prompt") or "")[:200],
                "timestamp": r.get("timestamp"),
            })
    return calls


def tool_calls(rows):
    counts = defaultdict(int)
    for r in rows:
        if r.get("type") != "assistant":
            continue
        for block in (r.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                counts[block.get("name", "?")] += 1
    return dict(counts)


def turn_ms(rows):
    return sum(r.get("durationMs", 0) for r in rows
               if r.get("type") == "system" and r.get("subtype") == "turn_duration")


UNUSABLE_SIGNS = ("session limit", "usage limit", "rate limit", "please run /login",
                  "not logged in", "credit balance", "overloaded")


def is_usable(res):
    """False when the session died on a limit or auth failure.

    Such a run still reports subtype "success" and still has a result event; it just
    did nothing. Counting it would drag every average toward zero.
    """
    if not res:
        return False
    txt = (res.get("result") or "").lower()
    if res.get("terminal_reason") == "api_error":
        return False
    return not any(s in txt for s in UNUSABLE_SIGNS)


def result_event(stream_rows):
    for r in reversed(stream_rows):
        if r.get("type") == "result":
            return r
    return {}


def measure_run(run_dir):
    meta_path = os.path.join(run_dir, "meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    sid_path = os.path.join(run_dir, "session-id.txt")
    session_id = open(sid_path).read().strip() if os.path.exists(sid_path) else None

    stream = read_jsonl(os.path.join(run_dir, "stream.jsonl"))
    res = result_event(stream)

    parent_rows, sub_rows_all, subagents = [], [], []
    if session_id:
        sf = find_session_file(session_id)
        if sf:
            parent_rows = read_jsonl(sf)
            sub_dir = os.path.join(os.path.dirname(sf), session_id, "subagents")
            for f in sorted(glob.glob(os.path.join(sub_dir, "*.jsonl"))):
                rows = read_jsonl(f)
                sub_rows_all += rows
                u, _ = dedupe_usage(rows)
                meta_file = f[:-len(".jsonl")] + ".meta.json"
                smeta = {}
                if os.path.exists(meta_file):
                    try:
                        smeta = json.load(open(meta_file))
                    except (OSError, json.JSONDecodeError):
                        pass
                subagents.append({
                    "file": os.path.basename(f),
                    "agent_type": smeta.get("agentType"),
                    "description": smeta.get("description"),
                    "spawn_depth": smeta.get("spawnDepth"),
                    "usage": u,
                    "turn_ms": turn_ms(rows),
                })

    parent_usage, parent_models = dedupe_usage(parent_rows)
    sub_usage, _ = dedupe_usage(sub_rows_all)
    combined = {k: parent_usage.get(k, 0) + sub_usage.get(k, 0)
                for k in list(USAGE_FIELDS) + ["total_tokens", "messages"]}

    calls = agent_calls(parent_rows)
    log_path = os.path.join(run_dir, "workdir", "agent-invocations.log")
    hook_lines = []
    if os.path.exists(log_path):
        hook_lines = [l.rstrip("\n") for l in open(log_path) if l.strip()]

    wd = os.path.join(run_dir, "workdir")
    return {
        **meta,
        "session_id": session_id,
        "ok": res.get("subtype") == "success" if res else None,
        "usable": is_usable(res),
        "unusable_reason": (res.get("result") or "").strip().splitlines()[0][:160]
                           if res and not is_usable(res) else None,
        "cost_usd": res.get("total_cost_usd"),
        "num_turns": res.get("num_turns"),
        "duration_ms": res.get("duration_ms"),
        "duration_api_ms": res.get("duration_api_ms"),
        "permission_denials": len(res.get("permission_denials") or []),
        "result_subagents": res.get("subagents"),
        "tokens_parent": parent_usage,
        "tokens_subagents": sub_usage,
        "tokens_total": combined,
        "by_model": parent_models,
        "turn_ms_parent": turn_ms(parent_rows),
        "agent_calls": calls,
        "agent_call_count": len(calls),
        "agent_types": sorted({c["subagent_type"] for c in calls}),
        "subagent_detail": subagents,
        "hook_agent_log_lines": len(hook_lines),
        "hook_agent_log": hook_lines,
        "tool_calls": tool_calls(parent_rows),
        "outputs_present": {
            name: os.path.exists(os.path.join(wd, name))
            for name in ("EXPENSE_CLAIM_REVIEW.md", "claims.csv",
                         "exceptions-queue.csv", "audit-log.txt")
        },
    }


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BENCH, "results", "latest")
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        sys.exit(f"no results at {root} — run bench/run.sh first")

    records = []
    for run_dir in sorted(glob.glob(os.path.join(root, "*", "*"))):
        if not os.path.exists(os.path.join(run_dir, "stream.jsonl")):
            continue
        rec = measure_run(run_dir)
        rec["run_dir"] = os.path.relpath(run_dir, root)
        with open(os.path.join(run_dir, "metrics.json"), "w") as f:
            json.dump(rec, f, indent=2)
        records.append(rec)

    with open(os.path.join(root, "metrics.json"), "w") as f:
        json.dump(records, f, indent=2)

    print(f"{'run':<22} {'tok in':>9} {'tok out':>8} {'cache rd':>9} "
          f"{'total':>9} {'cost':>7} {'turns':>6} {'agents':>7} {'time':>7}")
    for r in records:
        if not r.get("usable"):
            print(f"{r['run_dir']:<22} UNUSABLE — {r.get('unusable_reason') or 'no result'}")
            continue
        t = r["tokens_total"]
        cost = f"${r['cost_usd']:.3f}" if r.get("cost_usd") is not None else "—"
        secs = f"{r['duration_ms']/1000:.0f}s" if r.get("duration_ms") else "—"
        print(f"{r['run_dir']:<22} {t['input_tokens']:>9,} {t['output_tokens']:>8,} "
              f"{t['cache_read_input_tokens']:>9,} {t['total_tokens']:>9,} "
              f"{cost:>7} {str(r.get('num_turns') or '—'):>6} "
              f"{r['agent_call_count']:>7} {secs:>7}")
    bad = [r for r in records if not r.get("usable")]
    print(f"\nwrote {len(records)} records -> {os.path.join(root, 'metrics.json')}")
    if bad:
        print(f"WARNING: {len(bad)}/{len(records)} runs were unusable and are excluded "
              f"from scoring and the report.")


if __name__ == "__main__":
    main()
