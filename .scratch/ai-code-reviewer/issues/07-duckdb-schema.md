# DuckDB schema for feedback and logs

Status: open
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: 06-feedback-correlation.md
Blocks: —

## Question

What tables does the DuckDB file hold, and what does each column mean?

§6 names two things only — feedback records, and a `logs` table for failures — and
one query shape the curator must be able to run: top downvoted comment categories per
persona over a window.

Settle the schema, including:

- How a reaction, a written reply, and a comment that got neither are each
  represented. Absent feedback is a normal state, not a gap.
- Whether the poller upserts or appends, given it re-walks the same MRs over time and
  a reviewer can change their reaction.
- What the natural key for a bot comment is, following from the identity decision.
- Migration story, if any — this is a single file with a single writer.
