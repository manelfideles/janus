# Diff-size cap: what it measures, and what the number is

Status: open
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
