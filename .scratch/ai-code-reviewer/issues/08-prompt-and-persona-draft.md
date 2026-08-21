# First draft of the system prompt and persona YAML

Status: open
Labels: wayfinder:ticket, wayfinder:prototype
Parent: ../MAP.md
Assignee: unassigned
Blocked by: 01-agent-architecture.md

## Question

§4 fixes the prompt's *assembly* — system prompt, plus persona YAML, plus Jira
context, plus the diff — and §3 fixes the persona *schema*. Neither writes a single
word of the actual content, which is the thing that decides whether reviews are any
good.

Make a rough, concrete draft to react to:

- The org-wide system prompt: the non-negotiable rules, the tone, what the bot must
  never claim, and how it says "I found nothing".
- `fast.yaml` — the default budget persona, `blockers_only: true` with a word cap.
- One other persona, `backend` or `frontend`, with real `review_focus` bullets.
- The shape of a finding as it reaches the reader: what an inline comment says, and
  what the summary comment says, including the persona statement and re-run hint
  that §3 requires.

Run it against a real diff and read the output. Cheap and rough is the point — this
exists to be argued with, not shipped. Link the draft files as assets.

Per §4, reference material is inspiration for a human author only. Nothing is fetched
at runtime and nothing is reproduced verbatim.
