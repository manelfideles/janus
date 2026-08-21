# Diff-size cap: what it measures, and what the number is

Status: closed
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —
Blocks: 11-review-call-shape.md

## Question

`idea.md` §4 fixes the cap's *mechanism* — check before any model call, post a skip
comment on breach, exit the job successfully so an AI review never blocks a merge —
but neither the unit nor the value. The map lists this as unspecified fog. Deciding
the agent architecture (01) promoted it to a blocker, because the cap is now the
only thing bounding what one model call receives.

Settle:

- **The unit.** Changed files, added/removed lines, bytes, or tokens.
- **The global default value**, in that unit.
- **How `diff_size_cap_override` in the persona YAML interacts with it** — does a
  persona raise the cap, lower it, or both? `fast` presumably lowers it.
- **What the skip comment says.** §4 requires it to state size versus cap, so the
  number must be renderable in the chosen unit.
- **Whether a job timeout is a separate guardrail or a consequence of the cap**
  (§7 lists both under cost governance).

## Established facts

Checked against GitLab API v4 docs during the 01 grilling session:

- The merge request object carries **`changes_count`**, which is the only size
  signal available *without* fetching the diff. It is a poor gate for three
  reasons:
  1. It counts **changed files, not lines**. One file with a 3,000-line change
     reports `"1"`.
  2. It is a **string, and it caps**: GitLab returns `"1000+"` once an MR has too
     many changes to display and store, so it cannot distinguish 1,000 changes
     from 40,000.
  3. It **populates asynchronously and is empty on MR creation**. §2 runs the full
     review on MR creation, so the field may be absent at exactly the moment the
     gate needs it.
- Therefore a pre-fetch gate is only possible if the unit is changed files, and
  even then it is unreliable on a fresh MR.
- **This is not the only field with that behaviour.** Ticket 02 found that
  `diff_refs` - which supplies the `base_sha` / `head_sha` / `start_sha` an inline
  comment's `position` requires - is *also* empty right after MR creation and
  populates asynchronously. S2 runs the full review on MR creation, so the job
  lands in that gap for both fields. The `/versions` endpoint may not share the
  delay; ticket 02 queued that as a live check. Whoever builds the fetch step needs
  one story that covers both, not two workarounds.

## Why the unit is the real question

The unit decides whether the cap can be checked before fetching the diff at all:

| Unit | Gate before fetching? |
|---|---|
| Changed files | Possible via `changes_count`, with the three problems above |
| Lines or bytes | No — code must hold the diff |
| Tokens | No — code must hold the diff **and** tokenize it |

Note that §4 only requires the check to happen before any *model* call, not before
any fetch. Fetching the diff costs one HTTP request and zero model tokens, so
fetch-then-measure is cheap. The cap exists to bound model spend, and tokens are
the unit that spend is actually denominated in.

Recommendation to argue with: **measure in tokens, fetch first, gate before the
model call.** Pick the number from the chosen model's context window minus the
system prompt, persona, and expected output, with headroom.

## Answer

Full reasoning and citations: `data/janus-diffcap-t10/report.md` in the firstmate home.

- **Unit: tokens.** Both jobs the cap does - bounding spend and bounding one model
  call - are token-denominated. The two official Anthropic characters-per-token
  figures disagree by 1.6x, so any byte or line proxy is inaccurate by more than the
  cap's own safety margin.
- **Measured by** `client.messages.count_tokens(...)`, called after the diff fetch
  and before the model call. Free, rate-limited separately from message creation.
  **Not a new dependency** - the `anthropic` client is already required by S12 and
  ticket 01; add the method to the `ModelClient` interface.
  **This removes `changes_count` from the design entirely.** S4 only requires the
  check before the *model* call, so no pre-fetch gate is needed.
- **Formula:**
  ```
  effective_cap = min( persona.diff_size_cap_override ?? GLOBAL_DIFF_CAP_TOKENS,
                       GLOBAL_DIFF_CAP_TOKENS,
                       context_ceiling(model) )

  context_ceiling(model) = floor(0.90 * model.max_input_tokens)
                           - reserved_output_tokens    # assumed 8,000
                           - prompt_overhead_tokens    # assumed 2,500 (ticket 08)
  ```
  `model.max_input_tokens` is read from the Models API, never hardcoded.
- **`GLOBAL_DIFF_CAP_TOKENS = 60_000`**, assuming `claude-opus-5` - stated as an
  assumption, **not** a settling of the map's model-choice fog. Opus 5 was chosen
  because it is the most expensive candidate, so the cap is comfortable under any
  cheaper model. Caps one review at **~$0.50** worst case. Roughly 3,300-5,300
  changed lines of coverage, which is an estimate until measured.
- **`fast` override: `diff_size_cap_override: 20_000`** (~$0.15 worst case).
  **Overrides may only lower, never raise**, enforced by load-time validation and
  guaranteed by the `min()` at use time. Raising is disallowed because the global
  default already sits below every model's context ceiling, so a lower-only rule
  makes an un-honourable cap impossible to configure rather than merely invalid.
- **Timeout: independent guardrail, 15 minutes** at the job level (GitLab's default
  is 60). It covers what the cap cannot: a hang after the gate, and a retry loop
  against GitLab's undetectable note limit.

### The gap this found in S4 - the most actionable item in the report

S4 says an AI review skip "must never block a merge" and implements that as exiting
the job successfully. **That covers the breach path only.** A timeout or an unhandled
crash marks the job **failed**, which blocks a merge on any project with "Pipelines
must succeed" enabled - and the timeout S7 asks for is itself capable of causing it.

So S4's non-blocking promise currently depends on every code path remembering to
exit 0. The fix is one line, and it makes the promise structural:

```yaml
ai-review:
  timeout: 15 minutes
  allow_failure: true
```

The exit-0-on-breach behaviour stays, because it keeps the pipeline green rather than
orange on the ordinary skip path. `allow_failure` is the belt behind that brace.

### Ticket 11 is answered, not merely unblocked

At 60,000 tokens the cap uses 6.75% of Opus 5's context ceiling and 35.4% of
Haiku 4.5's, so **a whole-diff call cannot overflow by construction**. Ticket 11's
per-file option solves a problem that cannot occur.

### Two hazards found that threaten the cap's correctness

1. **`GET .../diffs` returns 20 files per page by default.** Without pagination the
   cap measures a fraction of the diff and passes something far larger to the model.
2. **GitLab withholds file contents per file** (`collapsed`, `too_large`). Silently
   swallowing those means capping a diff that was never fully read.

Both belong to the fetch step. `generated_file` is a free exclusion worth taking.

### Raised, not decided here

- **An output-side bound.** The cap governs input only. A small diff can still produce
  an expensive review if the model is verbose, and `fast`'s `max_words` is the only
  thing bounding output. Named per the brief, not designed.
- **Review frequency is an uncapped cost vector** - relevant to ticket 09, since every
  push triggers a review.
