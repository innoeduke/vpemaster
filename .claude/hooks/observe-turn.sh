#!/usr/bin/env bash
# Quietly observe the just-completed turn and append correction-shaped
# signals to the project memory inbox. Heuristic-only — no LLM call,
# no stdout. Exit 0 always so the agent is never blocked.
set -uo pipefail

HOOK_INPUT="$(cat)"

TRANSCRIPT_PATH="$(printf '%s' "$HOOK_INPUT" | python3 -c 'import json,sys
try:
  print(json.load(sys.stdin).get("transcript_path",""))
except Exception:
  pass' 2>/dev/null)"

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -r "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

INBOX="$HOME/.claude/projects/-Users-wmu-workspace-toastmasters-vpemaster/memory/inbox.md"
mkdir -p "$(dirname "$INBOX")"

python3 - "$TRANSCRIPT_PATH" "$INBOX" <<'PY' 2>/dev/null
import datetime
import json
import re
import sys

transcript_path, inbox = sys.argv[1], sys.argv[2]

try:
    with open(transcript_path, encoding="utf-8") as f:
        content = f.read()
except OSError:
    sys.exit(0)

records = []
try:
    parsed = json.loads(content)
    records = parsed if isinstance(parsed, list) else [parsed]
except json.JSONDecodeError:
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

# Walk the transcript and collect text-bearing user messages. The
# transcript format varies across hook payloads; we just want the last
# non-empty user utterance before the stop.
last_user_text = ""
for r in reversed(records):
    if not isinstance(r, dict):
        continue
    role = r.get("role") or r.get("type")
    if role != "user":
        continue
    msg = r.get("message") or r.get("content") or ""
    if isinstance(msg, list):
        parts = []
        for m in msg:
            if isinstance(m, dict):
                t = m.get("text") or m.get("content") or ""
                if isinstance(t, list):
                    t = " ".join(x.get("text", "") for x in t if isinstance(x, dict))
                parts.append(t if isinstance(t, str) else "")
        msg = " ".join(parts)
    if isinstance(msg, str) and msg.strip():
        last_user_text = msg.strip()
        break

if not last_user_text:
    sys.exit(0)

# Tighter correction heuristics. Word-boundary on tokens that almost
# never appear in non-corrective user utterances, plus a few contextual
# ones. False positives are fine — /reflect filters them.
patterns = [
    r"\bdon['']t\b",
    r"\bdo not\b",
    r"\bstop (using|doing|adding|writing)\b",
    r"\bactually[,.]",
    r"\bwait[,.]",
    r"\bnot that\b",
    r"\binstead of\b",
    r"\binstead[,.]",
    r"\bfrom now on\b",
    r"\bremember (this|that|to|when|that we)\b",
    r"\balways use\b",
    r"\bnever use\b",
    r"\bshouldn['']t\b",
    r"\bthat['']s wrong\b",
    r"\bthis is wrong\b",
    r"\bthe (right|correct|proper) (way|approach|pattern)\b",
    r"\bload[- ]bearing\b",
    r"\bbitten us\b",
    r"\binstead,\s",
    r"\bprefer\b.*\bover\b",
    r"\bnot\s+\w+,\s+(use|do|try|run)\b",
]

text_lc = last_user_text.lower()
if not any(re.search(p, text_lc) for p in patterns):
    sys.exit(0)

# Skip ultra-short turns ("no", "wait") and meta commands.
if len(last_user_text) < 8:
    sys.exit(0)

ts = datetime.datetime.now().isoformat(timespec="seconds")
snippet = re.sub(r"\s+", " ", last_user_text).strip()[:300]

try:
    with open(inbox, "a", encoding="utf-8") as f:
        f.write(f"- [{ts}] {snippet}\n")
except OSError:
    pass

sys.exit(0)
PY

exit 0