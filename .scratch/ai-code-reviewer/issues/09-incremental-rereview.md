# Incremental re-review semantics

Status: open
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: 01-agent-architecture.md, 03-last-reviewed-sha-storage.md

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
