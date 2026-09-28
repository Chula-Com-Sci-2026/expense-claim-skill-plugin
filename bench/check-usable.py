"""Exit 3 if a run's stream shows the session was never really usable.

    python3 bench/check-usable.py <stream.jsonl>

A run killed by a usage limit or a login failure still exits 0 and still writes a
terminal `result` event — it just does nothing, in about a second, for $0. Without
this check the matrix cheerfully burns every remaining session the same way and
leaves a results tree full of zeros that looks like data until you read it.
"""

import json
import sys

SIGNS = ("session limit", "usage limit", "rate limit", "please run /login",
         "not logged in", "credit balance", "overloaded")


def main():
    if len(sys.argv) < 2:
        return 0
    try:
        lines = open(sys.argv[1]).read().splitlines()
    except OSError:
        return 0

    for line in lines:
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if d.get("type") != "result":
            continue
        txt = (d.get("result") or "").strip()
        low = txt.lower()
        if d.get("terminal_reason") == "api_error" or any(s in low for s in SIGNS):
            first = txt.splitlines()[0][:160] if txt else "api_error, no message"
            print(first)
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
