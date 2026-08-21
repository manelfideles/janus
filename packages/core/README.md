# ai-reviewer-core

Shared code for the janus review job and the feedback collector.

Ticket 04 makes this package the single owner of anything both halves of the repo
need. Two of them are already here:

- `models.py` — the domain types. Findings are data returned by the model; code owns
  everything else (ticket 01).
- `marker.py` — the HTML-comment JSON marker, writer **and** parser. This is the whole
  reason the package exists: the reviewer writes markers and the collector parses them,
  so a drift between the two would break feedback attribution with no error at all
  (tickets 03 and 12).
- `config.py` — the 12-factor environment reader (idea.md §12).

**Keep it small.** A change under `packages/core/` rebuilds the review image *and*
redeploys the collector, because both depend on it. Ticket 04 records that as the
accepted price of the three-package split.

`core` has no I/O dependencies, and no runtime dependencies at all.
