# Agent architecture: tool loop or single-shot

Status: closed
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —
Blocks: 08-prompt-and-persona-draft.md, 09-incremental-rereview.md

## Question

Does the review job run the model as an agentic loop that calls GitLab tools as it
needs them, or as a single-shot call where code fetches everything first and posts
the result?

`idea.md` §4 lists a hardcoded tool whitelist — get MR diff, get metadata, list
notes, post inline comment, post summary comment, list award-emoji — which reads as
an agentic loop. But the doc never says so outright, and a single-shot design would
use the same list as a plain "what the code is allowed to touch" statement.

The answer sets the shape of nearly everything downstream: prompt structure, how
findings become comments, how failures are caught, how cost is bounded, and whether
a framework (Claude Agent SDK) or a plain API call is the right base.

Decide, and record why.

## Decision

**Single-shot, code-orchestrated review.** The model is a pure function: it takes
the system prompt, the persona content, and the diff, and it returns a list of
findings. It fetches nothing and it posts nothing.

The ticket's one question turned out to be two independent axes, and both resolve
the same way:

| Axis | Decision |
|---|---|
| **A — getting information in** | Code fetches the diff, MR metadata, and (on a re-review) prior notes before the model runs. One model call per review. |
| **B — getting review out** | The model returns findings as structured data. Code renders and posts every comment, and owns the `position` parameters, the correlation markers, and the finding category. |

### How this re-reads §4

§4's hardcoded tool whitelist is **not** a toolbox handed to the model. It is a
statement of what the *application* is permitted to touch — a guardrail on the
program. The ambiguity that created this ticket is resolved in favour of the
plainer reading.

### Why not an agentic loop

Four reasons, strongest first:

1. **§4 requires the diff-size cap to run before any model call.** Code must
   already hold the diff at that point. Once it holds the diff, withholding it
   from the prompt so the model can ask for it is strange.
2. **Every read tool in the whitelist returns something fetched unconditionally
   anyway.** Get MR diff, get MR metadata, and list notes are all needed on every
   run (notes only on a re-review, decided by a flag code already has). List
   award-emoji belongs to the §6 poller, not the review job. A loop would spend
   round-trips asking for what code would have handed over.
3. **There is no `get_file_contents` tool in the whitelist.** That is the one tool
   an agentic loop would genuinely need — to read past a truncated hunk and judge
   whether a finding is real. Its absence removes the loop's only real advantage.
   Granting it is a whitelist change, and per the map's Notes that would be its
   own ticket rather than a quiet redesign.
4. **A variable number of model calls per review fights the `fast` persona.** The
   default persona exists to make an un-tagged MR cheap and predictable. Letting
   the model decide how many calls to make removes the predictability.

### Consequences

- **No agent framework.** The Claude Agent SDK is not the right base. A plain
  Messages API call behind §12's `ModelClient` interface (`BedrockClient` /
  `AnthropicClient`) is sufficient, with structured output enforced by schema.
- **Cost is deterministic** — one model call per review, known before it is made.
- **The diff-cap gate is code-side**, after the fetch and before the model call,
  exactly as §4 requires.
- **Failures are caught in code**, so the §4 "review could not complete" comment
  and the §6 `logs` row have one obvious place to live.
- **The review job is replayable offline.** A pure function can be tested against
  a recorded diff with no GitLab and no real MR. This partly clears the map's
  *Testing approach* fog.
- **Findings exist as data in the program**, which is what gives tickets 06 and 07
  a natural key. Code mints the review id, the persona tag, and the category, so
  feedback attribution does not depend on the model formatting a marker correctly.
- **Finding categories derive from the persona's `review_focus` bullets.** Ticket
  06 asks what a finding category is; this is the answer, and it needs no new
  vocabulary invented.

### Raised, not decided here

Two gaps surfaced while deciding this, and are filed rather than resolved:

- [10-diff-size-cap.md](10-diff-size-cap.md) — the cap's unit and value.
- [11-review-call-shape.md](11-review-call-shape.md) — whole diff in one call, or
  one call per file. Deliberately out of scope for this ticket: it is a build
  decision downstream of the cap, not an architecture decision.
