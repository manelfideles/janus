# How GitLab positions inline comments on a diff

Status: open
Labels: wayfinder:ticket, wayfinder:research
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —

## Question

What exactly does the GitLab API v4 need in order to place a comment on a specific
line of an MR diff, and what happens when that line moves or disappears?

Surface the facts a design waits on:

- The discussions endpoint and its `position` parameters — `base_sha`, `head_sha`,
  `start_sha`, `old_path`, `new_path`, `old_line`, `new_line`, `position_type`.
- Which combinations are valid for an added line, a removed line, and an unchanged
  context line.
- How the API behaves when a position no longer exists on the current head — error,
  or a comment that silently becomes an outdated thread.
- Whether commenting on a line *outside* the diff hunk is possible at all.
- Rate limits or payload limits worth knowing before posting many comments at once.

This is a fact-finding ticket, not a decision. Record the findings and cite the
GitLab docs version they came from.
