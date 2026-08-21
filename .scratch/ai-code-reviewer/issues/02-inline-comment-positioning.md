# How GitLab positions inline comments on a diff

Status: closed
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

## Findings

Documentation and source study, 2026-08-21. No live API calls: the sandbox from
[05-provision-local-sandbox.md](05-provision-local-sandbox.md) does not exist yet.
Full evidence, verbatim doc quotations, worked payloads, and a 15-item live-check
list: `data/janus-mrpos-t2/report.md` in the firstmate home.

Evidence is tagged `[DOCS]` (docs.gitlab.com), `[SOURCE]` (gitlab-org/gitlab
master), or `[SILENT]` (docs do not say).

### Endpoint

`POST /projects/:id/merge_requests/:merge_request_iid/discussions` with a
`position` hash. All three SHAs are mandatory whenever `position` is sent. `[DOCS]`

The summary comment is a **different endpoint**:
`POST /projects/:id/merge_requests/:merge_request_iid/notes` with `body` only. `[DOCS]`

### The three line kinds

GitLab infers the line's kind purely from which line numbers are present.

| Line kind | `old_line` | `new_line` | `old_path` | `new_path` |
|---|---|---|---|---|
| Added (green, `+`) | **omit** | set | required | required |
| Removed (red, `-`) | set | **omit** | required | required |
| Unchanged context | set | set | required | required |

Omit means omit - not `null`, not `0`. `[DOCS]` corroborated by `[SOURCE]`
(`lib/gitlab/diff/formatters/text_formatter.rb`, `line_age`).

Consequence worth keeping: sending both numbers for an added line silently
reclassifies it as a context line, GitLab then fails to find a context line
there, and the request is **rejected**. An off-by-one produces a loud failure
rather than a comment on the wrong line.

### Stale positions - two different things

- **Stale at POST time.** The request fails validation and returns **400** with
  `Failed to find diff line for: <path>, old_line: N, new_line: M`. It does NOT
  create an outdated thread. Docs are `[SILENT]`; this is `[SOURCE]` and is one of
  the live checks.
- **A thread that goes stale later.** Documented, and it survives. Auto-resolve on
  new push is an opt-in project setting that is **off by default**. `[DOCS]`

**This means idea.md S9 is free.** "Leave prior inline comments untouched" is
already GitLab's default behaviour. S9 needs no code - only the discipline of never
calling the resolve endpoint, which S4's whitelist already forbids. Recorded here so
nobody later tries to "implement" S9.

### Commenting outside a diff hunk

Possible, but only for **unchanged context lines** in modified text files - GitLab
unfolds the old blob to locate the line. Added and removed lines are inside a hunk
by definition. `[SOURCE]`; docs `[SILENT]`.

### SHA source, and a hazard

Both `diff_refs` on the single-MR endpoint and the `/versions` endpoint supply
`base_sha` / `head_sha` / `start_sha`; the docs' own worked example uses
`/versions`. `[DOCS]`

**Hazard:** `diff_refs` is empty immediately after MR creation and populates
asynchronously. S2 runs the full review on MR creation, so the review job lands
in exactly that gap. `/versions` may not share the delay - that is a live check.
This is the second field with this behaviour; see
[10-diff-size-cap.md](10-diff-size-cap.md) for the first (`changes_count`).

### Limits

- **60 note creations per minute** on GitLab.com, plus 2,000 authenticated API
  requests per minute. A 12-finding review sits well inside both. `[DOCS]`
- **Trap:** the note-creation limit is not exposed in response headers, so
  approaching it cannot be detected - only the 429 tells you.
- Note body cap ~1,000,000 characters; 5,000 comments per MR. `[DOCS]`

Carried into [12-comment-posting-policy.md](12-comment-posting-policy.md).

### `position_type` beyond `text`

`image` and `file` are both accepted. `image` is ignorable. **`file` is not:** a
file-level comment "persist[s] across rebases and file changes", which makes it a
natural degradation path for a finding whose line cannot be positioned. `[DOCS]`

### Posting is not atomic

Each POST is independent; there is no batch-create with rollback. Comment 7 failing
leaves 1-6 posted and 8-12 unsent. The draft-notes batch route does not fix this -
it drops bad notes to a log line. `[DOCS]` + `[SOURCE]`

Raised as [12-comment-posting-policy.md](12-comment-posting-policy.md) rather than
decided here.

### Relationship to ticket 01

Ticket 01's decision holds up well against these facts. The `position` rules are
mechanical, unforgiving, and derived from the diff walk - exactly the kind of
payload that should be built by code rather than produced by a model.
