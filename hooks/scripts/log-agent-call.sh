#!/usr/bin/env bash
# PreToolUse (Agent): record every subagent the skill delegates to.
#
# The point is evidence. "The skill calls agents" is otherwise only visible by
# parsing session JSONL; this leaves a plain-text trail next to audit-log.txt that
# names the agent, why it was called, and the head of the instruction it was given.
#
# Note the matcher is `Agent`, not `Task` — that is the tool's name in Claude Code
# 2.x. Exits 0 always: this observes, it never blocks.
input="$(cat)"
log="${CLAUDE_PROJECT_DIR:-.}/agent-invocations.log"
python3 - "$input" "$log" <<'PY'
import json, sys, datetime
try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)
log = sys.argv[2]
ti = data.get("tool_input", {}) or {}
agent = ti.get("subagent_type", "") or "(unspecified)"
desc = (ti.get("description", "") or "").replace("\t", " ").replace("\n", " ")
prompt = (ti.get("prompt", "") or "").replace("\t", " ").replace("\n", " ")
head = prompt[:240] + ("…" if len(prompt) > 240 else "")
with open(log, "a") as f:
    f.write(f"{datetime.datetime.now().isoformat()}\t{agent}\t{desc}\t{head}\n")
PY
exit 0
