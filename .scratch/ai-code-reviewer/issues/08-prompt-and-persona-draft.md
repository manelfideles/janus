# First draft of the system prompt and persona YAML

Status: closed
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

## Draft produced, exercised, and argued with

Artefacts (in the firstmate home, `data/janus-prompt-t8/`): `system-prompt.md`,
`fast.yaml`, `backend.yaml`, `output-schema.md`, `rendered-comments.md`, `validate.py`,
plus `diffs/` and `runs/` holding four test diffs and eight verbatim runs.
Full write-up: `report.md`.

**Running the draft found three defects in it.** That is the ticket working as
intended - a draft nobody exercised would have shipped them. All three became
decisions below.

The report is explicit that it is **self-graded**: the same author wrote the prompt,
the test diffs, the outputs, and the scoring. An independent pass is scheduled as part
of landing (see the last decision).

## Decisions

### Captain's calls

**1. Linter overlap - assume every repo already lints, and its CI applies it.**
No detection, on simplicity grounds. The reviewer proceeds as though lint-class
findings are covered by a prior pipeline step, which is what S4 already says.
Firstmate additionally kept a one-sentence carve-out in the system prompt: stay silent
on what a linter owns **unless the consequence is data loss, a security hole, or a
broken interface** - because the run-1/run-2 miss (a mutable default argument later
persisted; ruff owns the cause, no linter owns the consequence) is a demonstrated bug,
and the carve-out needs no plumbing.
The assumption is recorded as an assumption; where it fails, lint-class issues nothing
else catches will go unreported. Acceptable for the skeleton and the S11 pilot; worth
revisiting before wider rollout.

**2. Clarity and naming nits - per-persona.** `fast` stays defects-only; `backend` and
`frontend` gain a clarity category. The default pass on an untagged merge request stays
quiet; a deliberately chosen persona may comment on readability, which is the thing an
LLM reviewer can do that a linter cannot.

**3. `fast` may report a performance blocker, at blocker severity only.** Run 8 showed
`fast` dropping an unbounded query that run 7 rated `backend`'s top blocker, so the
default persona could not report a classic production incident. `fast` is already
`blockers_only`, so this is consistent rather than a widening.

**4. Summary prose - template when findings exist, one model-written sentence when the
review is clean.** Over-claiming risk is highest when there ARE findings; the
zero-finding case has nothing to over-claim about and is exactly where a bare count
reads as the bot not having tried. The output schema keeps a summary string but code
consumes it **only** on the zero-finding path, and the prompt must say so or the model
will write it every time and have it silently discarded. S3's persona statement and
re-run hint stay template-owned in both cases.

### Settled by firstmate as consequences of decisions already accepted

**5. Category vocabulary - add `categories`, leave `review_focus` exactly as S3
describes it.** Tickets 03, 06, 07 and 12 all already assume a machine-readable
category that reaches a DuckDB column, so an id set is forced rather than newly chosen.
Parsing the prose bullets was rejected because reformatting a bullet would silently
change a category id and orphan historical feedback rows. S3's "not parsed
programmatically" line stays true as written.

**6. No `instructions` key.** Guidance like "silence is your normal output" is prompt
content addressed to the model, and `review_focus` is already exactly that. Net schema
change across decisions 5 and 6 is **one added field, not two.**

**7. No `confidence` field** in the skeleton. The prompt already tells the model to drop
what it is unsure of; a confidence field converts that suppression rule into a labelling
rule and the noise arrives anyway. Self-reported confidence from a language model is
weakly calibrated, and reviewer reactions are the better signal the feedback loop
already exists to capture. Additive if wanted later.

**8. The untrusted-diff gap became [14-diff-as-untrusted-input.md](14-diff-as-untrusted-input.md)** -
a gap to file rather than a choice to make. Does not block the skeleton.

**9. Independent evaluation is folded into the landing work**, not a separate project:
a second worker writes its own test diffs, runs the landed files, and scores them
against the prompt's own stated rules. Removes the self-grading problem for the part
that matters. It does not measure whether reviewers find reviews *useful* - only S11's
pilot can.

## Carried to ticket 06

The report recommends a **fixed org-wide category registry** rather than per-persona
vocabularies, on the grounds that per-persona lists make S6's cross-persona curator
query meaningless. Ticket 06 owns that decision.
