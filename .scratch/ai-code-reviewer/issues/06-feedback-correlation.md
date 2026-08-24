# Feedback correlation: linking a reaction back to a review

Status: open
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —
Blocks: 07-duckdb-schema.md

## Question

The poller is the only writer to the feedback store (§6), and the review job writes
nothing outside GitLab. So how does a 👍 on some comment become a row that means
something to a curator?

Two coupled unknowns:

**Identity.** When the poller finds a reaction on a bot comment, what tells it which
review that comment came from, which persona produced it, and what kind of finding it
was? §6 promises curator queries like "top downvoted comment categories per persona,
last 30 days" — categories that nothing in the doc currently defines or records.
Decide what metadata rides along with a posted comment and how it is encoded.

**Discovery.** How does the poller find "recently-reviewed MRs" at all, with no store
telling it where to look? Options to weigh: search the GitLab API for MRs carrying the
bot's comments, walk the projects that have opted in, or have the job leave a
discoverable trace.

Model the domain before choosing — what a review, a comment, a finding category, and
a feedback signal each are, and how they relate.

## Input from ticket 03 (closed)

Both of this ticket's coupled unknowns now have evidence.

**Identity - decided.** Ticket 03 chose an HTML-comment JSON marker embedded by
application code in every comment the bot posts:

```
<!-- ai-reviewer:{"v":1,"review_id":"…","persona":"fast","head_sha":"…","category":"…"} -->
```

Per ticket 01, code mints the review id, persona tag, and category, so attribution
does not depend on the model formatting anything. What remains for this ticket is the
**finding-category vocabulary**, not the transport. Ticket 01 established that the
persona YAML's `review_focus` bullets are the natural source, so this needs no new
vocabulary invented - only a decision on whether categories are free text or a fixed
enum, and how a category maps back to a `review_focus` bullet.

**Discovery - narrowed to one free option.** Searching for the bot's notes at global
or group scope needs the `notes` search scope, which is Premium/Ultimate and requires
advanced search. Ticket 05 provisions a **free** namespace, so that is out. The free,
fixed-cost path is:

```
GET /merge_requests?scope=all&state=all&updated_after=<cursor>&order_by=updated_at&sort=desc
```

`scope` defaults to `created_by_me`, which returns nothing for a bot that authors no
merge requests, so `scope=all` is mandatory. Posting a note bumps the merge request's
`updated_at`, so one cursor catches both new reviews and new reactions. What remains
is where the cursor itself lives, and the first-run bootstrap window.

**Recommendation carried over: the poller should use GraphQL.** REST reads reactions
one note at a time (`GET .../notes/:note_id/award_emoji`), which is O(bot comments)
round trips. GraphQL's `MergeRequest.notes` connection exposes `body` and `awardEmoji`
together, so a single query returns markers and reactions at once - making the marker
cost the poller nothing extra.

Evidence: `data/janus-shastore-t3/report.md` in the firstmate home, sections 5 and 6.
