#!/usr/bin/env bash
# PreToolUse (Write|Edit): block writing a policy-violating claim into claims.csv.
# Exit 2 blocks the tool call and feeds stderr back to Claude. Exit 0 allows it.
input="$(cat)"
python3 - "$input" <<'PY'
import json, sys
try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)  # not JSON we understand -> don't block
ti = data.get("tool_input", {}) or {}
path = ti.get("file_path", "") or ""
content = ti.get("content", "") or ti.get("new_string", "") or ""
if path.endswith("claims.csv") and "VIOLATION" in content:
    sys.stderr.write(
        "Blocked: a line flagged VIOLATION cannot be written into claims.csv. "
        "Route it to exceptions-queue.csv instead.\n"
    )
    sys.exit(2)
sys.exit(0)
PY
