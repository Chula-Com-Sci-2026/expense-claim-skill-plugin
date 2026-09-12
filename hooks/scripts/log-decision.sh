#!/usr/bin/env bash
# PostToolUse (Write|Edit): append an audit line for every write the review makes.
input="$(cat)"
log="${CLAUDE_PROJECT_DIR:-.}/audit-log.txt"
python3 - "$input" "$log" <<'PY'
import json, sys, datetime
try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)
log = sys.argv[2]
ti = data.get("tool_input", {}) or {}
path = ti.get("file_path", "") or ""
with open(log, "a") as f:
    f.write(f"{datetime.datetime.now().isoformat()}\t{data.get('tool_name','')}\t{path}\n")
PY
