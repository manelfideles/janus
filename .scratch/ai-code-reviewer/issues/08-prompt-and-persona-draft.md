# First draft of the system prompt and persona YAML

Status: open
Labels: wayfinder:ticket, wayfinder:prototype
Parent: ../MAP.md
Assignee: unassigned
Blocked by: — (01-agent-architecture.md closed 2026-08-21)

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

## Input from ticket 01 (closed)

Ticket 01 fixed the shape this draft has to take: the review is a **single-shot call
that returns structured data**, not prose and not tool calls.

So the system prompt must ask for a **list of findings as data**, each carrying at
minimum a file path, a line, a finding category, a severity, and the comment body.
Code renders those into comments and owns every `position` payload and metadata
marker. The prompt must not ask the model to format markers, choose line numbers for
the API, or decide what to post.

Two knock-on constraints:

- **`review_focus` bullets are the finding-category vocabulary.** Tickets 03 and 06
  settled that the category rides in the comment marker and is minted by code, and
  ticket 01 established `review_focus` as its natural source. The persona YAML written
  here therefore defines that vocabulary, so the bullets need to read as categories a
  curator would query by, not only as prose instructions.
- **`max_words` applies to one response.** With a single call per review, the `fast`
  persona's word cap is naturally enforceable. Do not draft it as a per-comment cap.

The summary comment still needs its persona statement and re-run hint per S3, and it
is also the only place a partial-post count could be reported - see
[12-comment-posting-policy.md](12-comment-posting-policy.md).
