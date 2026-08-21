# Comment posting policy: partial failure, retries, and the API budget

Status: closed
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —
Blocks: —

## Question

Posting a review is not atomic. Ticket 02 established that each inline comment is
its own `POST`, there is no batch-create with rollback, and the draft-notes batch
route does not help (it drops bad notes to a log line). So comment 7 of 12 failing
leaves 1-6 posted and 8-12 unsent.

What does the job do about it?

## The failure classes are not the same

The obvious design - "retry from the comment that broke" - is right for one class
and wrong for the other, so the classes have to be split before any retry policy
makes sense.

| Failure | Nature | Correct response |
|---|---|---|
| **400, rejected position** (`Failed to find diff line for: ...`) | **Deterministic.** The line is not there. Retrying fails identically, forever. | Skip it and **keep going**. Do not treat it as a stopping point. |
| **429 rate limited**, **5xx** | **Transient.** | Retry that same comment with backoff before moving on. |

A retry loop that does not make this distinction will stall permanently on the
first bad position.

Settle:

1. **The classification itself** - which status codes and error bodies map to which
   class, and what the default is for an unrecognised failure.
2. **Backoff shape** for the transient class, and a cap. The job has a pipeline
   timeout (S7), so retries cannot be unbounded.
3. **Degradation for the deterministic class.** Ticket 02 found that
   `position_type=file` comments "persist across rebases and file changes". Is a
   file-level comment a better answer than dropping the finding? It changes
   "we could not place this" from a silent loss into a visible note.
4. **Does the summary comment declare partial success?** GitLab keeps no
   partial-state marker, so the summary comment is the only place "9 of 12 findings
   posted" can live. S9 posts a fresh summary every review anyway.
5. **Crash idempotency.** If the job dies after comment 6 and the pipeline is
   re-run, what stops it re-posting 1-6? Nothing, unless each comment carries a
   review id that can be searched for first. This is a third argument for the
   metadata marker under discussion in
   [03-last-reviewed-sha-storage.md](03-last-reviewed-sha-storage.md), and it
   couples this ticket to that decision.
6. **Whether a failed post is a `logs` row.** S4 promises a `logs` table for
   failures; the map lists the error taxonomy as unspecified fog. A rejected
   position is a strong candidate for a named category.

## The API budget (parked here deliberately)

Ticket 02's measured limits, recorded so this does not have to be rediscovered:

- **60 note creations per minute** on GitLab.com.
- 2,000 authenticated API requests per minute.
- Note body cap ~1,000,000 characters; 5,000 comments per MR.

A 12-finding review sits well inside all of these, so **this is not a skeleton
blocker** - it is recorded because it becomes one at scale, and because of the trap
below.

**The trap:** the note-creation limit is **not exposed in response headers**. There
is no way to see it approaching. The only signal is the 429 itself, which lands
mid-review with some comments already posted - i.e. straight into the partial-post
problem above. That coupling is why the budget lives in this ticket rather than its
own.

Consider, when this is worked: a deliberate small delay between posts, or a cap on
inline comments per review (which the `fast` persona's `blockers_only` already
approximates).

Recommendation to argue with: **best-effort posting that never stops on a
deterministic rejection**, bounded backoff on transient ones, a review id in every
comment for crash-safe re-runs, and a summary comment that states the count when it
is not the full set.

## Policy

Full classification table, citations, and a build-now-versus-defer split:
`data/janus-postpolicy-t12/report.md` in the firstmate home.

### Classification gained a second axis

Not just deterministic versus transient - also **scope**:

- `comment` scope: skip this one, keep posting.
- `review` scope: **stop posting entirely.**

`401`, `403 insufficient scope`, and `404` are review-scoped: post **nothing at all**
rather than skipping and continuing. A credential or project problem is not a
per-comment failure, and continuing would produce a partial review for a reason that
has nothing to do with the code.

`400 Maximum number of comments exceeded` is also review-scoped.

**Defaults for anything unrecognised: 4xx deterministic, 5xx and transport transient.**

### Backoff

3 attempts per comment, jittered, worst case ~6s. A 429 honours `Retry-After` and
retries once; a **second** 429 anywhere in the review stops the inline loop.
**Global posting-phase cap: 180s wall clock**, checked before every attempt and every
sleep. That is 30% of the *minimum* job timeout GitLab permits, so the retry budget
cannot outlive its own job at any legal timeout.

### Degradation

A finding whose position is rejected is **listed in the summary comment**, not posted
as a `position_type=file` note. Zero extra API calls, one scannable list instead of
several unanchored comments, and no dependency on an undocumented payload shape.
`position_type=file` remains the documented upgrade if reviewers ask for it.

Findings rejected because of a *janus* bug (invalid payload, note eaten as a quick
action) are **not** listed - telling a reviewer "could not place this finding" would
send them looking at their own code. They count toward the shortfall and get a `logs`
row.

### Idempotency - the key in this ticket's question was one field short

`review_id` **cannot** deduplicate: a re-run mints a new one. The marker gains
`fid = sha256(new_path|old_path|line_kind|line_number|category)[:12]`, which is
content-independent and therefore survives the model rewording the same finding.

Key = **`(head_sha, fid)`**. At the start of the posting phase, read the bot's own
notes, parse markers, build the set, skip anything already in it. Same commit means
skip; a different `head_sha` is not in the set, so nothing is suppressed and ticket 09
decides whether the finding exists at all.

**Cost: zero additional requests.** It is a read tickets 03 and 09 already make.

### Ordering

Inline comments first in stable diff order, **summary comment last, one summary.** No
placeholder-then-edit, because S4's whitelist excludes edit operations. The
"inline comments with no summary" crash state is transient - the pipeline re-run
completes it, because of the idempotency check above.

### The 429 trap is defused

Ticket 02 recorded GitLab.com's 60-notes-per-minute creation limit as invisible in
response headers. At source level **that limit does not apply to inline diff
comments**, which removes the preventive-throttling question for the skeleton.
React to a 429, do not pace for it.

### Open

One captain decision remains: whether the summary comment admits a partial post.
