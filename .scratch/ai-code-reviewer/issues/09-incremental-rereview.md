# Incremental re-review semantics

Status: open
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —

## Question

§2 says a push to an already-reviewed MR triggers a "diff-only" review. What does that
mean precisely?

Five questions were filed here, and one premise sat under all of them. **The premise is
refuted**: a push does not leave an inline comment pointing at the wrong code, so §9's
"keep stale inline comments" costs nothing and needs no handling at all. The re-post
defect that finding exposed has since been fixed and merged. What remains is the diff
base, the force-push case, the empty or over-cap slice, and what the incremental summary
says. Prior-review context stays a cost judgement, and there are now measured numbers to
make it with.

## Refuted — there is no stale-comment problem, so do not build one

This ticket was written expecting that a push moves the code under an existing inline
comment and leaves the thread pointing at the wrong line. **Measured against the live
API, that does not happen.**

- **Writing with a stale `head_sha` is not an error.** Posting against a genuinely older
  registered diff version returns **201**, and GitLab discards the `head_sha` sent,
  substitutes the current head, and translates the line — `new_line` 11 was stored as 21
  where content had moved (`t2/V9`, confirmed).
- **Existing threads are traced forward.** After a push inserting five lines above them,
  three threads anchored at the immediately preceding head moved from `9d651857 / 21` to
  `549ea6a0 / 26` — the `head_sha` and the line number both rewritten by GitLab
  (`t2/V10`, confirmed).
- **Threads further behind stay frozen, and still render against the right code.** Of 86
  notes frozen at an older head, **83 render against the line they were written about and
  zero render against the wrong line**. The three that render nothing were born from
  `500`s and were unrenderable from birth — they are not casualties of the push
  (`t2/V10`).
- **There is no outdated flag to read.** REST note payloads have none, and a full GraphQL
  introspection of 4,257 types finds `outdated`/`stale` only on CI-catalog, runner and
  security types. The only staleness test either API offers is comparing a note's own
  `position.head_sha` against the merge request's `diff_refs.head_sha` (`t5 §2.7`).

An earlier pass concluded that a push does not re-anchor existing threads at all; that
was wrong, and it was wrong because it was tested against an empty commit — the one case
where no tracing happens. The later finding is the one that stands.

So: **no stale-position handling, no staleness branch, and no use of `head_sha` to detect
staleness.** §9's "prior inline comments are left untouched" is not a compromise the
design tolerates; it is measured behaviour that renders correctly.

## Settled

**The duplicate-suppression defect this exposed is already fixed and merged.** The real
cost of a moved line was never positioning — it was identity. `finding_fid` hashed the
line *number*, so an insertion above an untouched finding minted a new fingerprint
(`048e1b1d810d` → `412372d0f157`), and `dedup_key` compounded it by including `head_sha`,
which every push changes. A re-review therefore re-posted every finding. `finding_fid`
now hashes the **diff line's text** and `Marker.dedup_key` is the `fid` alone, so a
finding on untouched code keeps its identity across pushes and a finding whose line really
changed correctly re-posts. See `packages/core/janus_core/marker.py` and its docstrings.
**This ticket does not have to solve it, and must not re-open it.**

**Where the last-reviewed SHA comes from.** The newest bot summary comment's marker
carries `head_sha`, and the marker round trip is now verified byte-exact on merge request
notes, inline and root (`t5 §3.1`). The SHA is **absent** on a first review and after a
human deletes the bot's comment, and in both cases the correct behaviour is a full review
— so "no marker found" is a normal state this ticket must handle, not an error.

**The corroborating signal is weaker than it looked.** Inline notes the bot created do
carry `position.head_sha` (`t3/12`, confirmed populated), so a SHA can sometimes be
recovered with no marker. Two reasons not to rely on it: it fails whenever a review
produced zero inline findings — exactly what `fast` is built to produce — and a thread's
stored `head_sha` **advances when GitLab traces it forward**, so it is not a record of
when the comment was posted (`t5 §6.1`).

**Prior-review context is a plain cost decision**, not an architecture one: ticket 01
made the review a single-shot call where code assembles the whole prompt. What is new is
the size of the budget it competes for. `fast` caps the diff at 20,000 tokens and already
carries about **2,750 tokens of fixed prompt overhead** before it sees a line of code
(system prompt ~2,050, persona ~700, measured on ticket 08's draft). Real diffs run about
**2.18 characters per token** (`t10/1`), so prior-review context is denominated in the
same expensive unit as the diff itself.

## Still open

**Which diff.** Last-reviewed SHA against new head, or merge-base against new head
restricted to files that changed since the last review. Unchanged, and still the ticket's
central question.

**Force-push, and how to detect it.** When the last-reviewed SHA is no longer an ancestor
of head, the marker still names a commit that is no longer usable as a diff base. Decide
whether that degrades to a full review or to merge-base-against-head. `/versions` is still
the place to detect it, with one measured correction: **never index `/versions`
positionally.** One push produced *two* version records twenty seconds apart carrying the
same `head_commit_sha`, so `versions[1]` was the current head, not the previous diff. The
rule is to select the newest entry whose `head_commit_sha != diff_refs.head_sha`
(`t5 §1`).

**One hazard to build around.** A position naming a stale `head_sha` while carrying a
*current* line number — valid now, absent at the head named — is a **500**, and a 500 can
leave a note behind and duplicates on retry (`t2/V2`, `t12/P4`). Reading `diff_refs` and
`/diffs` from the same response makes that regime unreachable. Worth stating in whatever
this ticket decides, because an incremental review is exactly where a cached `diff_refs`
is tempting.

**The empty slice, and the slice that breaches the cap.** Unchanged. The cap is now
measured: 60,000 tokens covers **97.25%** of 1,165 real merged pull requests, and the
median is 2,046 tokens (`t10/3`), so an incremental slice alone breaching the cap is a
thin-tail case rather than a common one. It still needs an answer.

**What the incremental summary says.** §9 posts a fresh summary every time; confirm it
makes clear it covers only the new commits. Unchanged.

**Carried in from ticket 10 §8: review frequency is an uncapped cost vector.** §2 runs a
review on every push, so ten pushes is ten reviews. The diff cap bounds one review;
nothing bounds reviews per merge request per day, and a developer pushing fixups is
normal behaviour rather than a pathological merge request. Ticket 10 named this ticket as
its home. Mean measured input cost is $0.0363 per merge request at the current cap
(`t10a §9`), so this is a policy question about noise and repetition at least as much as
about money.

Evidence: `data/janus-live-verify-t5/report.md` §1, §2.7, §3.1, §6.1, which is where
every `t2/`, `t3/` and `t12/` row above was settled;
`data/janus-tokeniser-measure-t10a/report.md` rows 1 and 3;
`data/janus-shastore-t3/report.md` and `data/janus-mrpos-t2/report.md` for the original
claims; `data/janus-prompt-t8/report.md` §7.5 for the prompt overhead — all in the
firstmate home.
