# Incremental re-review semantics

Status: open
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —

## Question

§2 says a push to an already-reviewed MR triggers a "diff-only" review. What does
that mean precisely?

- Which diff — last-reviewed SHA against new head, or the merge-base against new head
  restricted to files that changed since the last review?
- Does the model see the prior review's comments, so it neither repeats itself nor
  contradicts itself? That costs tokens the `fast` persona is trying to save.
- What happens on a force-push, when the last-reviewed SHA is no longer an ancestor
  of head?
- What happens when the diff-only slice is empty, or when the incremental diff alone
  breaches the size cap.
- §9 keeps stale inline comments and posts a fresh summary every time. Confirm the
  incremental summary makes clear it covers only the new commits.

## Input from tickets 01 and 03 (both closed)

**Where the last-reviewed SHA comes from.** The newest bot summary comment's
HTML-comment marker carries `head_sha`. Read cost is one API call in the typical case.
The SHA is **absent** on a first review and after a human deletes the bot's comment,
and in both cases the correct behaviour is a full review - so "no marker found" is a
normal state this ticket must handle, not an error.

**Prior-review context is now a plain cost decision.** Ticket 01 made the review a
single-shot call where code assembles the whole prompt, so whether the model sees the
prior review's comments is just a question of what code chooses to pass. It is not an
architecture question. The `fast` persona's budget is the thing to weigh.

**Force-push is the sharp case.** When the last-reviewed SHA is no longer an ancestor
of head, the marker still exists and still names a commit - it is simply no longer
usable as a diff base. This ticket must decide whether that degrades to a full review
or to merge-base-against-head. Note that this is detectable cheaply, and that GitLab's
own `diff_refs` / `/versions` data is the place to detect it.

**A corroborating signal, not a mechanism.** Inline notes the bot created carry
`position.head_sha`, so the SHA can sometimes be recovered from them with no marker at
all. It fails whenever a review produced zero inline findings - exactly what the `fast`
persona is built to produce - so it cannot be relied on.

Evidence: `data/janus-shastore-t3/report.md` and `data/janus-mrpos-t2/report.md` in the
firstmate home.
