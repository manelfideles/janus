# Comment posting policy: partial failure, retries, and the API budget

Status: open
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
