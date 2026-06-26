---
name: reflect
description: Consolidate the project's memory inbox (raw observation lines from the observe-turn hook) into curated memory files with proper Why/How-to-apply structure, and update MEMORY.md index. Use when the user says "/reflect", "consolidate memory", "process the inbox", or when the inbox has accumulated entries worth curating.
---

# /reflect — consolidate memory inbox

The `observe-turn.sh` Stop hook appends correction-shaped user utterances to `~/.claude/projects/-Users-wmu-workspace-toastmasters-vpemaster/memory/inbox.md` after every turn. This skill turns that raw signal into durable memories.

## Workflow

1. **Read the inbox.** Path: `$HOME/.claude/projects/-Users-wmu-workspace-toastmasters-vpemaster/memory/inbox.md`. If empty or missing, tell the user "inbox is empty" and stop.

2. **Read existing memory.** Read `MEMORY.md` (the index) and any feedback/project/user memory files it points to. Understand what's already captured so you don't duplicate.

3. **Cluster the inbox.** Group related entries. Two entries are "related" when they describe the same rule, pitfall, preference, or project fact. Ignore entries that are obvious false positives (tool artifacts, quoted text, etc.) — but only after reading them; err on the side of keeping.

4. **For each cluster, decide:**
   - **feedback** — a rule the user wants me to follow. Body: rule, then `**Why:**` and `**How to apply:**`. Save as `feedback_<slug>.md`.
   - **project** — a fact about vpemaster (architecture, convention, deadline). Body: fact, then `**Why:**` and `**How to apply:**`. Save as `project_<slug>.md`.
   - **user** — a preference about how to work. Save as `user_<slug>.md`.
   - **skip** — too vague, a duplicate of an existing memory, or a transient task detail. Just don't write anything.

5. **Write each memory file** at `$HOME/.claude/projects/-Users-wmu-workspace-toastmasters-vpemaster/memory/<type>_<slug>.md` with the frontmatter format from the auto-memory spec:
   ```
   ---
   name: <slug>
   description: <one-line summary — used to decide relevance>
   metadata:
     type: <feedback|project|user>
   ---

   <body>

   **Why:** ...
   **How to apply:** ...
   ```

   Body should be terse — 1–4 sentences plus the Why/How-to-apply lines. Link related memories with `[[their-slug]]`.

6. **Update MEMORY.md.** Add one line per new memory under the index, in the form `- [Title](<file>.md) — <one-line hook>`. Keep entries under ~150 chars. If you update an existing memory (because the inbox added new signal), just edit the description line — don't duplicate the file.

7. **Clear the inbox.** After successful consolidation, truncate `inbox.md` (delete the contents but keep the file). Don't move entries to an archive — if the user wants history, they can read this skill and grep their history themselves.

8. **Tell the user.** One short summary: "Wrote N memories, skipped M, updated K existing." List the new memory titles. Don't dump the full content.

## Quality bar

- **Bad memory:** "user said don't do X" (no rule, no why, applies to nothing)
- **Good memory:** "Always use `make test-fast` for full test suites. **Why:** parallel pytest is ~4× faster than serial and is the canonical entry point. **How to apply:** any time you'd reach for `python -m pytest` or `pytest`, use `make test-fast` instead."

A memory is only worth writing if a future Claude session, reading it cold, would behave differently. If the rule is obvious from the codebase, don't write it. If it's already in `CLAUDE.md`, don't duplicate — reference `[[claude-md]]` instead.

## Edge cases

- **Inbox has 50+ entries from a long session.** Cluster aggressively. Two entries about the same rule → one memory. If the inbox mentions a single rule 10 times, that's signal it's important — write a strong memory for it.
- **Inbox contains a contradiction with existing memory.** Surface it to the user before writing. Ask which wins.
- **User invokes /reflect mid-task.** Finish the in-progress task first, then consolidate.