# Does the summary comment tell the reader when some findings were not posted?

Status: open
Labels: wayfinder:ticket, wayfinder:grilling, deferred
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —
Blocks: —

## What "a partial post" is

Ticket 02 established that each inline comment is its own API call and there is no
batch-with-rollback. So a review that produced 12 findings makes 12 separate calls,
and any one of them can be refused - most often because the line it points at no
longer exists at the current head, which returns a 400.

The result is a **partial post**: some findings are on the merge request, some are
not. Ticket 12 settled that the job keeps going rather than stopping at the first
refusal, so this is a normal outcome, not a crash.

The open question is only about **what the reader is told.** GitLab stores no
"this review was incomplete" marker anywhere, and the reviewer is forbidden from
editing its own comments (S4), so the summary comment posted at the end is the only
place the fact could live.

## The question

Does that summary comment say something like "9 of 12 findings could not be placed",
or does it stay silent and simply show fewer comments than the reviewer found?

Three positions:

- **Disclose only when it matters** (ticket 12's recommendation): silent when the
  review posted everything, and when it did not, one cause-specific sentence naming
  what the reader should do about it.
- **Never disclose.** The reader sees the comments that landed. Simplest, and it never
  worries anyone about an internal detail they cannot act on.
- **Always state a count**, complete or not. Most transparent, but adds a line to
  every review for the sake of the rare one.

## What has to be true whichever way it goes

- **The sentence is code-generated.** Ticket 08 settled that the summary comment is a
  template except for one model-written sentence on a clean review. A count is exactly
  what a template does well, and the model must never be asked to report it - it has
  no idea what the API did.
- **It must be actionable or absent.** The test is whether a reviewer reading the
  sentence knows what to do. "Some findings could not be placed" tells them nothing
  they can act on and is noise dressed as transparency. "3 findings pointed at lines
  that have since changed - push again to re-review" is actionable.
- **Findings dropped because of a bug in janus are excluded.** Ticket 12 settled that
  telling a reviewer "could not place this finding" for an internal defect sends them
  looking at their own code. Those go to the `logs` table only.

## Why deferred

Deferred on the captain's decision: it is a reader-experience detail with no
dependants, and the honest way to answer it is to see a real partial post on a real
merge request rather than to reason about it in advance.

Revisit once the sandbox (ticket 05) exists and a stale-position rejection has been
observed, or the first time a reviewer asks why a review looked thin.
