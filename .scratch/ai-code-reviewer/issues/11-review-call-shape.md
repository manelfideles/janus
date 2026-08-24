# Review call shape: whole diff in one call, or one call per file

Status: open
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: — (10-diff-size-cap.md closed 2026-08-21; its cap was measured and confirmed 2026-08-24)
Blocks: —

## Question

Ticket 01 settled that the review is a single-shot, code-orchestrated call rather
than an agentic loop. It deliberately did not settle how many calls one review
makes. That is a build decision, and it is downstream of the cap.

Does the whole diff go to the model in one request, or does each changed file get
its own request?

- **One call, whole diff.** The model sees cross-file relationships — for example
  that a caller broke when a helper it depends on changed. One cost, one retry, one
  failure comment. The `fast` persona's `max_words` cap applies naturally to a
  single response.
- **One call per file.** No context-window ceiling, and one bad file does not sink
  the whole review. But the model cannot see cross-file effects, and `max_words`
  has no obvious meaning across N independent responses.

Weigh, before choosing:

- **Prompt caching.** N calls sharing one system prompt and one persona may cost far
  less than N× the naive estimate. This materially changes the cost argument against
  per-file, and should be measured rather than assumed.
- **Whether the ceiling can even be reached.** If ticket 10 sets the cap below the
  context window, a whole diff can never overflow by construction, and the per-file
  option solves a problem that cannot occur. This is why this ticket is blocked by
  10.
- **§4's breach behaviour is already decided.** On breach, post a skip comment and
  exit non-blocking. A "chunk instead of skipping" fallback would override that
  decision, so it needs raising explicitly rather than sliding in as an
  implementation detail.
- **Two code paths cost more than one.** For a side-of-desk skeleton, a rare
  fallback path is the path that is never exercised and therefore broken when it is
  finally needed.

Recommendation to argue with: **one call for the whole diff**, on the grounds that
ticket 10's cap should make overflow impossible by construction, and cross-file
findings are among the most valuable a reviewer produces.
