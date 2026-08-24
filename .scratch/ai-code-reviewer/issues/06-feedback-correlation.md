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

Two coupled unknowns were filed here. **Identity** — what tells the poller which review
a reacted-to comment came from, which persona produced it, and what kind of finding it
was. **Discovery** — how the poller finds recently-reviewed merge requests at all, with
no store telling it where to look.

Identity is now settled apart from one choice — whether the category vocabulary is
org-wide or per-persona. Discovery is not settled, and the mechanism this ticket
recommended has been refuted against the live API. Read the next section before building
anything.

## Refuted — do not build the site-wide activity cursor

The cursor this ticket carried was:

```
GET /merge_requests?scope=all&state=all&updated_after=<cursor>&order_by=updated_at&sort=desc
```

**It does not work, and it is not a tuning problem.** Measured against GitLab.com
(`t3/11`, refuted):

- `scope=all` is a **site-wide firehose**, not "every project the bot can see". It
  returned `wireshark/wireshark!26262` among 100 results while the token was a member of
  exactly one project, which held zero merge requests.
- `membership=true` is **silently inert** on that endpoint. It does not narrow the
  firehose and it does not error.
- The exact query above returned **HTTP 408 `Request timed out` three times out of
  three**, about 15.3 s each. The per-project form answered the same question in 0.35 s.

Anyone who builds this will get a poller that reads other people's merge requests,
slowly, and then times out.

**The proposed replacement is a two-step per-project loop**, and it is a proposal for
this ticket to decide rather than a decision already taken:

```
GET /projects?membership=true
  then, per project:
GET /projects/:id/merge_requests?updated_after=<cursor>&order_by=updated_at&sort=desc
```

It has not been exercised across more than one project, so its cost at pilot scale
(2-3 repositories) is arithmetic, not measurement: one list call plus one call per
project per poll.

## Settled

**Identity — transport is decided and now verified in the field.** Ticket 03 chose an
HTML-comment JSON marker embedded by application code in every comment the bot posts:

```
<!-- ai-reviewer:{"v":1,"review_id":"…","persona":"fast","head_sha":"…","category":"…","fid":"…"} -->
```

It is implemented in `packages/core/janus_core/marker.py` and the real `render_marker`
output survives a round trip through GitLab **byte for byte**, on both note kinds the
reviewer uses — an inline `DiffNote` and a root summary note — and parses back into a
`Marker` (`t5 §3.1`). The one exception is a body line that parses as a genuine quick
action, which GitLab deletes from what it stores; the marker itself is never at risk
because it begins with `<` (`t5 §6.2`). That case belongs to
[14-diff-as-untrusted-input.md](14-diff-as-untrusted-input.md).

**Identity — the category question is mostly answered, by ticket 08 rather than here.**
This ticket asked whether categories are free text or a fixed enum, and how a category
maps back to a `review_focus` bullet. Ticket 08 settled both halves it could:

- The persona schema gains **exactly one field, `categories`** — a machine-readable id
  set. So the vocabulary is an enum minted by code, not free prose, and the model must
  pick from ids the prompt gave it.
- **Parsing the prose bullets was rejected**: reformatting a bullet would silently change
  a category id and orphan historical feedback rows. §3's "not parsed programmatically"
  line stays true as written.
- So the mapping runs the other way round from how this ticket framed it. A
  `review_focus` bullet **carries** an id; it does not define one. Those are different
  things, and the difference is the whole reason the schema gained a field.

**Discovery — the cursor's underlying mechanic holds.** Posting a note bumps the merge
request's `updated_at`, confirmed for both an inline diff note and a root note
(`t3/10`). GitLab **coalesces** the touch to roughly a minute, so a second note straight
after the first does not move the timestamp again — which loses nothing for an
"anything happened since X" cursor, and is worth knowing before someone writes a test
that flakes on it.

**Discovery — what is out stays out, and one route re-opened.** Global and group `notes`
search is Premium and needs advanced search, so it remains unavailable on the free
namespace ticket 05 provisions. But **project-scoped basic search does reach
`scope=notes` on a Free project** (`t3/8`) — the API reference's "needs advanced search"
sentence is wrong — and the marker **tokenises precisely**: searching a `review_id` or a
`fid` returns exactly the notes carrying it (`t3/9`). That does not solve discovery,
because it needs a project to search in. It is a cheaper way to find the bot's comments
*inside* a project the loop has already reached than paging every note.

## Still open

**The credential, which this ticket did not previously carry.** Ticket 05 took a
**project access token confined to one project** instead of the second bot account §5
and §6 assumed. Cross-project discovery cannot work with it, in any shape: the
per-project loop above still needs a credential that can see every opted-in project.
So this ticket now owns a scoping decision it did not have before:

- Group access token, a user-level token for a bot account, or one token per project.
- What that does to the containment ticket 05 bought deliberately — a leak of a
  project-scoped token costs one throwaway repo; a group token costs the group. GitLab
  offers no "read merge requests and comment" scope, so whatever is chosen carries `api`.
- Where the collector reads it from, given the review job and the collector deploy
  separately (ticket 04).

**Where the cursor lives, and the first-run bootstrap window.** Unchanged. Note the
circularity worth naming: the store the cursor would naturally live in is the one this
poller is the sole writer of, so "no store yet" is the first-run state by construction.

**Which projects are opted in.** The only record of an opt-in is an `include:` in a
repository's `.gitlab-ci.yml` (§2). `GET /projects?membership=true` returns what the
credential belongs to, which is a different set. Decide whether those are allowed to
differ, and what happens to a project that was reviewed and then removed.

**Whether the category id set is org-wide or per-persona.** Ticket 08 carried this here
explicitly. Its report recommends a **fixed org-wide registry** — about ten ids, each
with a one-line definition, every `review_focus` bullet naming a registered id, `other`
a permanent member so a rising `other` share becomes the signal that the registry is
missing a category, and renames treated as a migration rather than an edit. The
argument is that per-persona vocabularies make §6's cross-persona curator query
meaningless: writing two persona files in one sitting already produced `data_loss` and
`data_integrity` as near-synonyms. Decide the registry question, the initial id set, and
the rename rule; ticket 07's columns follow from it.

**REST or GraphQL for the poller.** The recommendation stands and is still unmeasured:
REST reads reactions one note at a time (`GET .../notes/:note_id/award_emoji`), which is
O(bot comments) round trips, while GraphQL's `MergeRequest.notes` connection exposes
`body` and `awardEmoji` together, so one query returns markers and reactions at once.
Nothing in the live pass exercised that query.

**The domain model.** What a review, a comment, a finding category and a feedback signal
each are, and how they relate. Still the first thing to do in a sitting on this ticket,
and still what ticket 07 is waiting on.

Evidence: `data/janus-live-verify-t5/report.md` §3.1, §3.3, §5.5, §6.2 and
`data/janus-shastore-t3/report.md` §5 and §6, in the firstmate home. Category
vocabulary: `data/janus-prompt-t8/report.md` §8, decided in
[08-prompt-and-persona-draft.md](08-prompt-and-persona-draft.md).
