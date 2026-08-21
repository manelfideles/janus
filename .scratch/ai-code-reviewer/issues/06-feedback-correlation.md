# Feedback correlation: linking a reaction back to a review

Status: open
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: 03-last-reviewed-sha-storage.md
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
