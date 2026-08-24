# Does the summary comment tell the reader when some findings were not posted?

Status: open
Labels: wayfinder:ticket, wayfinder:grilling, deferred
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —
Blocks: —

## What "a partial post" is

Ticket 02 established that each inline comment is its own API call and there is no
batch-with-rollback. So a review that produced 12 findings makes 12 separate calls, and
any one of them can be refused. The result is a **partial post**: some findings are on the
merge request, some are not. Ticket 12 settled that the job keeps going rather than
stopping at the first refusal, so this is a normal outcome, not a crash.

The open question is only about **what the reader is told.** GitLab stores no "this review
was incomplete" marker anywhere, and the reviewer is forbidden from editing its own
comments (S4), so the summary comment posted at the end is the only place the fact could
live. That part is unchanged.

## Refuted — the cause this ticket was written around does not happen

This ticket said a refusal happens "most often because the line it points at no longer
exists at the current head, which returns a 400", and ticket 12's draft sentence names a
force-push as the common case. **Measurement says that case is not a refusal at all.**

- Posting against an older registered diff version returns **201**; GitLab discards the
  `head_sha` sent, substitutes the current head, and translates the line (`t2/V9`).
- Threads already on the merge request are traced forward on a push, and threads too far
  behind stay frozen while still rendering against the line they were written about — 83
  of 86, with **zero** rendering against the wrong line (`t2/V10`).

So the moved-line shortfall the disclosure sentence was drafted for does not occur. What
is left as a genuine deterministic refusal is narrower and rarer: an **impossible line**,
a **file not in the diff**, and a **renamed-only file**, which carries an empty diff and
therefore cannot take a line comment on any path combination at all (`t2/V1`, `t2/V7`,
`t2/V8`). A finding on a renamed-only file has nowhere to go but the summary.

**And the transient sentence describes a cause that cannot arise on the path it names.**
Ticket 12 drafted "Posting stopped early — 4 of 12 findings were not posted because GitLab
rate-limited this bot." Inline posting is **not rate limited**: 61 `POST .../discussions`
in 7.7 s returned 61 × 201, while 61 `POST .../notes` in the same minute returned 59 × 201
and two 429s (`t12/P1`). The only call a review makes on the limited endpoint is **the
summary comment itself** — the one that would carry the disclosure. A rate-limited review
does not post a thin review with an explanation; it posts a complete set of inline
comments and then struggles to say anything about them.

Both refutations point the same way: **a partial post is rarer than this ticket assumed**,
which is an input to whether it deserves a line in every summary at all.

The corrections those same measurements force on ticket 12's classification table belong
to [16-posting-policy-remeasured.md](16-posting-policy-remeasured.md). This ticket is only
about what the reader is told.

## What is now settled

**A 5xx can leave a comment behind, so "posted" is not knowable from the status code.**
Garbage `start_sha` → **500 with the note created**; garbage `head_sha` → 500 with nothing
created; garbage `base_sha` → **201, silently accepted and not validated at all**
(`t2/V2`).

**A retry does not risk duplication; it produces it.** Two identical 500s produced two
identical notes (`t12/P4`), and a transport timeout left the note behind **10 times out of
10** on both endpoints (`t12/P5`). So a count derived from "how many calls returned 2xx"
is wrong in both directions: a 5xx or a timeout that did create the note makes it
under-report, and a 202 — which creates nothing — makes it over-report.

**The bulk path would destroy the evidence.** `bulk_publish` accepted an invalid draft at
creation with 201, returned **204 with an empty body**, published 2 of 3, and destroyed
the bad one along with the good ones — the caller is told nothing (`t2/V15`). The only way
to notice is to count notes before and after. A shortfall is reportable *because* ticket
12 posts individually; a batch route would remove both the count and the cause.

**There is a usable after-the-fact signal, and this ticket did not know about it.** A note
born from a failed request **renders as nothing**: `Discussion.truncatedDiffLines` comes
back empty, and the only three unrenderable threads on the fixture were exactly the three
created by 500s (`t5 §2.7`). So "this comment exists but shows the reader nothing" is
identifiable after the fact, through GraphQL.

Two limits on that signal, both worth stating before anyone leans on it. It costs a
GraphQL query the review job does not otherwise make, and reading it *after* posting means
a second pass. And it supports **counting**, not **cleanup**: deleting the orphan is an
operation S4's whitelist excludes.

**Any read-back count must page.** `GET .../notes?per_page=100` silently returned only the
first page of a 219-note history and made a just-created note look absent (`t12/P2`). An
unpaged read-back would over-report the shortfall.

## The question

Does the summary comment say something like "3 of 12 findings could not be placed", or
does it stay silent and simply show fewer comments than the reviewer found?

Three positions, unchanged:

- **Disclose only when it matters** (ticket 12's recommendation): silent when the review
  posted everything, and when it did not, one cause-specific sentence naming what the
  reader should do about it.
- **Never disclose.** The reader sees the comments that landed. Simplest, and it never
  worries anyone about an internal detail they cannot act on.
- **Always state a count**, complete or not. Most transparent, but adds a line to every
  review for the sake of the rare one — and "rare" is now measured rather than assumed.

One sub-question is new, and it applies to all three: **where the count comes from.**
Either from what the posting loop observed, which is cheap and provably wrong after a 5xx
or a transport timeout, or from a paged read-back of the merge request's notes after
posting, which is accurate and costs calls the job does not otherwise make. A sentence
that states a number the job cannot actually know is worse than silence.

## What has to be true whichever way it goes

- **The sentence is code-generated.** Ticket 08 settled that the summary comment is a
  template except for one model-written sentence on a clean review. A count is exactly what
  a template does well, and the model must never be asked to report it — it has no idea
  what the API did.
- **It must be actionable or absent.** The test is whether a reviewer reading the sentence
  knows what to do. "Some findings could not be placed" tells them nothing they can act on
  and is noise dressed as transparency. Note that the actionable sentences ticket 12 drafted
  were built on the two causes refuted above, so their replacements have to be written from
  the causes that survive.
- **Findings dropped because of a bug in janus are excluded.** Ticket 12 settled that
  telling a reviewer "could not place this finding" for an internal defect sends them
  looking at their own code. Those go to the `logs` table only.
- **A re-run promise is only honest because of the `fid` check.** "Comments already posted
  will not be duplicated" is a promise `finding_fid` keeps, and it now keeps it across
  pushes as well as re-runs, since the fingerprint no longer moves with the line number or
  the commit.

## Why this was deferred, and what has changed

Deferred on the captain's decision: it is a reader-experience detail with no dependants,
and the honest way to answer it is to see a real partial post on a real merge request
rather than to reason about it in advance. The stated revisit condition was "once the
sandbox (ticket 05) exists and a stale-position rejection has been observed".

**Half of that condition has been overtaken.** The sandbox exists, and the event named as
the trigger — a stale-position rejection — is now known not to occur. Genuine rejections
were observed, but of the narrower kinds listed above. Whether that re-opens this ticket
now, or leaves it deferred until a reviewer asks why a review looked thin, is the
captain's call; nothing downstream is waiting on it.

Evidence: `data/janus-live-verify-t5/report.md` §2.3, §2.5, §2.7, §5.1, §5.2, §5.4, §5.6,
in the firstmate home, and `data/janus-postpolicy-t12/report.md` §4 for the drafted
sentences.
