# Revisit S2's "no external storage dependency" premise

Status: open
Labels: wayfinder:ticket, wayfinder:grilling, deferred
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —
Blocks: —

## Why this exists

Ticket 03 chose an HTML-comment marker for the last-reviewed SHA and accepted one
cost: the SHA lives on a **mutable, human-editable surface**. A reviewer who deletes
the bot's summary comment destroys it, and the job silently falls back to a full
review.

The captain's objection, raised while deciding ticket 03, was that updating a table
is less finicky than reading state back out of the GitLab API. That objection is
correct on ergonomics. It was not adopted for the skeleton because it conflicts with
two locked decisions - so per the map's Notes it is raised here rather than quietly
redesigned.

**This is deliberately deferred.** The skeleton ships on the marker. Open this only
when the marker's fragility becomes a real complaint, or before the tool graduates
past pilot.

## The locked decisions this would reopen

> **S2:** "no external storage dependency, keeps the ephemeral review job fully
> self-contained (talks only to GitLab + Bedrock)"

> **S6:** "This process is the **only** writer to the feedback store - the ephemeral
> per-MR review job never touches it."

## The three objections that have to be answered

1. **DuckDB is a single-file store with a single-writer assumption** - which is
   *why* S6 chose it. The review job runs as a GitLab CI job: many of them,
   concurrently, across repos, on unpredictable schedules. Multiple CI jobs writing
   one DuckDB file is not something DuckDB supports. Answering this means putting a
   service in front of the store, with authentication, reachable from CI - a new
   deployment surface the skeleton does not have.
2. **The review job needs the SHA at job start, cold.** If the poller is the only
   writer, the SHA may not be there yet after a push, because the poller runs on a
   schedule. So the review job would have to write it - becoming a second writer and
   breaking S6 directly.
3. **The loss window.** S7 snapshots DuckDB to S3 hourly. A crash loses up to an
   hour of SHA records, causing redundant full reviews. Survivable, but a cost the
   merge request itself does not have.

## What to settle if this is opened

- Whether the review job gets read-only access, read-write access, or stays
  store-free with the marker as the only channel.
- If a service fronts the store: what it is, how CI authenticates to it, and whether
  that contradicts S6's stated vendor-lock-in aversion and S7's minimal-infra
  posture.
- Whether the store replaces the marker or supplements it. Note that the marker also
  serves ticket 06's per-comment attribution and ticket 12's crash-safe re-run, and
  a store does **not** obviously replace either - a reaction still has to be traced
  back to a specific review and finding, and the only thing carrying that identity
  to the poller is the comment itself.
- Whether this is a pilot-graduation concern rather than a skeleton concern at all.

## Note on scope discipline

AGENTS.md-style caution applies and is worth restating: do not build a service,
control plane, or policy layer unless the direct path has exposed a concrete
blocker. As of ticket 03's decision it has not. "The marker could be deleted by a
human" is a known, safely-handled risk, not yet an observed failure.
