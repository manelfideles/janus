# Review call shape: whole diff in one call, or one call per file

Status: open
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: — (10-diff-size-cap.md closed 2026-08-21; its cap was measured against 1,165 real diffs 2026-08-24)
Blocks: —

## Question

Ticket 01 settled that the review is a single-shot, code-orchestrated call rather than an
agentic loop. It deliberately did not settle how many calls one review makes. That is a
build decision, and it is downstream of the cap.

Does the whole diff go to the model in one request, or does each changed file get its own
request?

- **One call, whole diff.** The model sees cross-file relationships — for example that a
  caller broke when a helper it depends on changed. One cost, one retry, one failure
  comment. The `fast` persona's `max_words` cap applies naturally to a single response.
- **One call per file.** No context-window ceiling, and one bad file does not sink the
  whole review. But the model cannot see cross-file effects, and `max_words` has no
  obvious meaning across N independent responses.

## Settled since this was filed

**The context ceiling cannot be reached, so per-file's headline advantage is not one.**
At 60,000 tokens the cap uses 6.75% of Opus 5's context ceiling and 35.4% of Haiku 4.5's
— and even at 100,000 it is 11.2% and 59.0%. A whole-diff call cannot overflow by
construction. This was ticket 10's answer; measurement leaves it intact.

**The typical review is nowhere near the cap.** Over 1,165 real merged pull requests, the
median diff is **2,046 tokens** and p90 is **30,442** (`t10/3`). Half of all reviews cost
about a cent of input. Whatever the two shapes cost each other, they are arguing over a
thin tail.

**The cap's coverage is measured: 60,000 tokens skips 2.75% of that corpus** (`t10/3`).
Real diffs run about **2.18 characters per token**, p10–p90 1.78–2.54 (`t10/1`), so
60,000 tokens is roughly **131 KB** of diff.

**Both shapes can be costed exactly, for free, before either is built.** `count_tokens`
returned a count identical to the billed call's `usage.input_tokens` — **delta 0** on all
four payloads, two models, 431 to 42,506 tokens (`t10/5`). It is free of charge and its
p50 latency is 232 ms (`t10/4`). So this ticket does not have to argue about cost:
assemble both shapes over a corpus of real diffs and count them. That is the strongest
new input here, and it is what turns the remaining question from a debate into a
measurement.

The one caveat on that endpoint is a cost of the per-file shape rather than of the
measurement: `count_tokens` is rate limited at **100 requests per minute per
organisation**, and a 200 response carries no rate-limit headers at all, so a client
cannot pace itself from them (`t10/4`). One gate per review is nowhere near that. One
gate per file, across concurrent pipelines, is a great deal closer.

**Per-file pays the prompt overhead per file, and that overhead is now a number.**
`fast` carries about **2,750 tokens** of system prompt plus persona before it sees a line
of code (measured on ticket 08's draft: system prompt ~2,050, persona ~700). On the median
2,046-token merge request, one per-file call's fixed overhead is larger than the entire
diff. Prompt caching is the counterweight, and it remains **unmeasured** — see below.

**The diff listing paginates, and both shapes have to deal with it.** `GET .../diffs`
returns **20 files per page** by default, confirmed directly from `x-per-page: 20`, with
`x-next-page` behaving as documented (`t10/7`). A whole-diff shape that does not page
under-measures the token count *and* reviews a truncated diff while reporting as if it had
seen everything. A per-file shape walks the same pages. Pagination is mandatory either
way; it is not an argument for either shape.

**The cap's coverage is model-specific.** `claude-haiku-4-5` counts about **25% fewer
tokens** for the same bytes than `claude-opus-5`, and on a 149-diff overlap 24 diffs
exceeded 60,000 tokens on Opus 5 while only 16 did on Haiku 4.5 (`t10a §6.5`). A
call-shape decision that leans on "how often the cap binds" must name the model it
assumes.

## Refuted — two inherited justifications this ticket should stop repeating

**The cap does not sit "just inside" GitLab's own collapse line.** Ticket 10 anchored
60,000 tokens on GitLab's 5,000-changed-line collapse threshold via an assumed 45
characters per line. Measured, that line is **145,000–173,000 tokens** (`t10/2`), so
60,000 is at roughly 40% of it. GitLab still renders plainly a great deal of what the cap
skips. The cap number survives on coverage alone; the "GitLab gave up on it too"
justification does not.

**The diffs the cap skips are not junk.** Of the 32 diffs above 60,000 tokens, exactly
**one** is a generated file; the other 31 are ordinary hand-written or agent-written
feature, test and refactor work (`t10a §6.4`). Removing every generated-heavy diff from
the corpus moves coverage by 0.03 percentage points. So "the cases where an AI review adds
least" is false, and any argument here that leans on "a skipped merge request was not
worth reviewing" is leaning on a refuted premise.

That raises the pressure on §4's breach behaviour — post a skip comment and exit
non-blocking — but it does not move the decision here. A "chunk instead of skipping"
fallback still overrides a locked decision, and per the map's Notes it needs raising as
its own ticket rather than sliding in as a call-shape implementation detail.

## Still to weigh

- **Prompt caching.** The one thing this ticket asked to have measured that still has not
  been. N calls sharing one system prompt and one persona may cost far less than N× the
  naive estimate, and at ~2,750 tokens of fixed overhead per call that is exactly where
  the per-file option lives or dies. Measure it before choosing; `count_tokens` cannot
  answer it, because caching shows up in `usage`, not in the count.
- **The output side is uncapped, and no ticket owns it.** On Opus 5 output is priced at
  5× input, only `fast` carries a `max_words` cap, and `max_words` is a prompt
  instruction rather than an enforced limit. The enforceable mechanism is `max_tokens` on
  the call — and N calls means N reserved output budgets, which is a cost difference
  between the two shapes that nothing currently bounds. Ticket 10 §8 named this gap and
  recommended a separate ticket; it has not been filed, and this ticket should not
  quietly decide it.
- **Two code paths cost more than one.** Unchanged, and still the strongest argument for
  the simpler shape: for a side-of-desk skeleton, a rare fallback path is the path that is
  never exercised and therefore broken when it is finally needed.

Recommendation to argue with, unchanged and now better supported: **one call for the whole
diff.** Overflow is impossible by construction, the median review is a thirtieth of the
cap, cross-file findings are among the most valuable a reviewer produces, and the per-file
shape pays a measured fixed overhead once per file to buy a ceiling that cannot be
reached. The way to settle it cheaply is to count both shapes over a corpus rather than to
argue further.

Evidence: `data/janus-tokeniser-measure-t10a/report.md` rows 1–5, §6.3–6.5 and §9;
`data/janus-live-verify-t5/report.md` §4.1; `data/janus-diffcap-t10/report.md` §3.4 for
the ceiling arithmetic; `data/janus-prompt-t8/report.md` §7.5 for the prompt overhead —
all in the firstmate home.
