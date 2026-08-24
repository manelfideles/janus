# The posting policy's failure table, re-derived from measurement

Status: open
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —
Blocks: —

## Why this exists

Ticket 12 closed with a failure-classification table and a retry policy, both derived from
GitLab's source rather than from a live call, because no sandbox existed when it was
written. The sandbox now exists and every load-bearing row has been exercised. **Five of
its claims rest on behaviour GitLab does not have**, and one of the five turns the retry
policy from a safety measure into a duplication machine.

That table is what a builder will implement. Left as it stands, it produces string matchers
that can never fire and a retry ladder that posts the same comment twice. So the correction
needs an owner, and a closed ticket is settled by definition — per the map's Notes, this is
raised as its own ticket rather than silently rewritten.

**First thing to settle, before the content:** whether this lands as an amendment inside
[12-comment-posting-policy.md](12-comment-posting-policy.md), the way ticket 04 was amended
in place, or as a superseding decision recorded here. Everything below is the input to that
sitting, not a decision already taken.

## Refuted — do not build these

**1. The two 400 string matchers do not exist.** The table matches on
`Failed to find diff line for:` and `Failed to find diff file`. **Neither string ever
appears.** Every bad position — a line past EOF, a wrong line kind, a file not in the diff,
a file that does not exist — returns the same opaque body:
`Note {:line_code=>["can't be blank", "must be a valid line code"]}` (`t2/V1`, `t2/V7`,
both partly refuted). The status code split survives untouched; the two rows collapse into
one: **any 400 on a `position` is a deterministic positioning failure.** They already share
a disposition, so behaviour does not change — but a matcher written against those phrases
would silently fall through to the default bucket forever.

The one 400 signature that *is* real and matchable is `position "is incomplete"`, returned
when both line fields are omitted (`t2/V3`, confirmed). It is a janus bug when it fires,
exactly as the table says.

**2. The 500-versus-403 quick-action rows are wrong on both endpoints.** The table has
`POST .../notes` returning 403 and the un-rescued `POST .../discussions` returning 500 for
a body carrying a disallowed quick action. **Both return 201 and silently delete the
offending line** (`t12/P3`, partly refuted). A commands-*only* body returning **202 with no
note created** is real and matchable, and the table handles that one correctly.

The mitigation ticket 12 chose — prefix any rendered line matching `^/` with a single space
— survives and is more necessary than its author thought, because a silent 201 leaves the
caller nothing to react to. Its security framing belongs to
[14-diff-as-untrusted-input.md](14-diff-as-untrusted-input.md).

**3. The staleness degradation branch defends against nothing.** A position naming an older
head is not rejected: it returns 201, re-anchored to the current head with the line
translated (`t2/V9`), and existing threads are traced forward or stay frozen while still
rendering against the right code (`t2/V10`). Delete the staleness branch. Keep degradation
for the refusals that are real: an impossible line, a file not in the diff, and a
renamed-only file, which has an empty diff and cannot take a line comment on any path
combination (`t2/V8`).

**4. Retrying a create duplicates.** The per-comment ladder is three attempts with full
jitter. Measured: two identical 500s produced **two identical notes** (`t12/P4`), and a
transport timeout left the note behind **10 times out of 10** on both endpoints
(`t12/P5`). Ticket 12 classified transport errors as "transient, ambiguous" and retried
them; the ambiguity is one-sided. This is the re-decision below.

**5. The pre-flight rate-limit floor check reads the wrong limiter.** `RateLimit-*` headers
are present on a 201, but `ratelimit-name` is `throttle_authenticated_api` at 2,000/minute
— not the `notes_create` limiter that refuses the 61st note. A floor check would read ~1,996
of headroom on the very endpoint about to 429, and the 429 itself carries only
`Retry-After` and no `RateLimit-*` headers at all (`t12/P6`). Ticket 12 deferred this; it
should be **rejected**, not deferred.

## What survives untouched

Worth stating, so the correction is not read as a rewrite of the whole policy.

- **Inline posting is not rate limited, exactly as ticket 12 read it from source.** 61 ×
  `POST .../discussions` in 7.7 s returned 61 × 201, while 61 × `POST .../notes` in the
  same minute returned 59 × 201 and two 429s (`t12/P1`, confirmed). The consequence is
  worth writing into the table rather than leaving in prose: the 429 row is reachable on
  **the summary comment alone**, which is the last call a review makes. `Retry-After: 60`
  is real and **conservative** — the limit cleared at 30 s (`t12/P7`) — so honouring it
  over-waits rather than under-waits, and a second 429 is not a risk to plan around.
- The two axes — **scope** (`comment` = skip and continue, `review` = stop posting) and
  **class** (deterministic versus transient) — and the default rule that an unrecognised
  4xx is deterministic while an unrecognised 5xx or transport error is not.
- `401`/`403`/`404` are review-scoped, post nothing at all, and cannot carry the S4 failure
  comment.
- Summary comment last, inline comments in stable diff order.
- Unplaced findings listed in the summary rather than posted as file-level notes — and
  `position_type=file` is confirmed viable as the documented upgrade, for every file kind,
  provided **both** paths are sent (`t2/V12`).
- `GET .../notes` is the right endpoint for the idempotency read: `DiffNote`s come back
  with a fully populated `position` (`t12/P2`, confirmed), so no fallback to `/discussions`
  is needed.
- The `fid` fingerprint and the idempotency check itself, which have since been built and
  corrected — `finding_fid` hashes the diff line's text and `dedup_key` is the `fid` alone
  (`packages/core/janus_core/marker.py`).

## The genuine re-decision: what replaces the retry ladder

A create cannot be blind-retried. Three shapes to weigh, and this is the sitting's real
work:

- **Do not retry a create at all.** Let the next run's idempotency check reconcile. Cheapest
  and provably duplicate-free; loses a finding until something re-runs.
- **Read before re-writing.** Re-read the merge request's notes before each retry and skip
  anything whose `fid` is already there. Correct, and costs a paged GET per retry.
- **Retry only where the write provably did not land.** The regimes are measured: a bad
  `head_sha` 500 created nothing, a bad `start_sha` 500 created a note, and a bad
  `base_sha` returned 201 because `base_sha` is not validated at all (`t2/V2`). This is the
  most precise and the most fragile, because it keys on undocumented behaviour.

Whatever is chosen, one rule falls out of the same evidence and costs nothing:
**read `diff_refs` and `/diffs` from the same response.** The single dangerous regime is a
stale `head_sha` carried alongside a current line number — valid now, absent at the head
named — which is a 500 that can leave a note behind (`t5 §6.1`). Reading both from one
response makes it unreachable.

## Two items that move from "defer" to "required"

- **Paginate the idempotency read.** Ticket 12 deferred this on the grounds that one page
  covers the skeleton. `per_page=100` silently returned the first page of a 219-note history
  and made a just-created note look absent (`t12/P2`). An unpaged check re-posts everything
  on a busy merge request.
- **Never adopt `bulk_publish`.** It accepted an invalid draft with 201, returned **204 with
  an empty body**, published 2 of 3, and destroyed the bad draft along with the good ones
  (`t2/V15`). Ticket 02 reached the same conclusion from source; it is now measured, and it
  should be written down as a rule rather than left as a road not taken.

## Not in scope here

What the summary comment *says* about a shortfall belongs to
[15-partial-post-disclosure.md](15-partial-post-disclosure.md). The security reading of the
quick-action result belongs to [14-diff-as-untrusted-input.md](14-diff-as-untrusted-input.md).
This ticket is only the classification and retry rules.

Evidence: `data/janus-live-verify-t5/report.md` §2.1–2.5, §5.1–5.6, §6.1 and §7
("Undermined — revisit these"), in the firstmate home, against
`data/janus-postpolicy-t12/report.md`.
