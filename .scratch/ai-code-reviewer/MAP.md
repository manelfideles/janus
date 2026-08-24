# Map: AI-Assisted Code Reviewer — Local Walking Skeleton

Status: open
Labels: wayfinder:map
Source design doc: [idea.md](../../idea.md)

## Destination

A local walking skeleton of the reviewer. `docker-compose up`, plus a real merge
request on a throwaway GitLab.com project, produces: a GitLab CI pipeline run that
posts persona-tagged review comments via the Anthropic API; a second push that
produces an incremental (diff-only) re-review; and a 👍 reaction on a bot comment
that the poller lands in DuckDB, with the DuckDB file snapshotted to MinIO.

The production path — Bedrock, ECR, EC2, OIDC, real S3, SSM deploy — stays unbuilt.

## Notes

**This map carries execution.** It overrides Wayfinder's plan-only default: the
destination is a running skeleton, so later tickets build code, not just decisions.
Front-load only the blocking unknowns, then start building and let the rest graduate
from fog.

- **Domain**: AI-assisted code review for GitLab merge requests. GitLab API v4,
  Anthropic API, DuckDB, MinIO, Python, Docker Compose.
- **`idea.md` §1–§12 is locked.** Treat it as settled. This map only fills gaps.
  If working a ticket exposes a decision in the doc that cannot work as written,
  raise it as its own ticket — do not silently redesign.
- **Solo, side-of-desk.** Keep tickets small and self-contained. One ticket should
  fit one sitting.
- **Claim identifiers.** Where a ticket rests on measured evidence it cites the claim,
  not the whole finding: `t2/V9`, `t3/11`, `t10/3`, `t12/P4` name the report that raised
  the claim and the row inside it, and `t5 §2.7` names a section of the live
  verification pass that settled it. Each ticket's closing Evidence line names the files
  in the firstmate home, so a reader can check rather than trust.
- Skills to consult: `/grilling` and `/domain-modeling` on decision tickets,
  `/prototype` on prototype tickets, a `/research` subagent on research tickets.
- Personas in the skeleton: `fast` (the default) plus one other, not all four.

## Decisions so far

<!-- one line per closed ticket: gist plus a link to the ticket that holds the detail -->

- **Agent architecture: single-shot, code-orchestrated.** The model is a pure
  function from prompt + persona + diff to a list of findings; code fetches
  everything before the call and posts every comment itself. §4's tool whitelist is
  a guardrail on the application, not a toolbox given to the model. No agent
  framework. See [01-agent-architecture.md](issues/01-agent-architecture.md).
- **Inline comment positioning: documented, and S9 is free.** Added lines send only
  `new_line`, removed lines only `old_line`, unchanged context lines both. An
  *impossible* position is rejected with a 400; a *stale* one is not - live measurement
  corrected that half, and GitLab accepts it with a 201, re-anchored to the current
  head. A thread that goes stale later survives untouched and still renders against the
  code it was written about, so S9 needs no code at all. Posting is inherently
  non-atomic. See
  [02-inline-comment-positioning.md](issues/02-inline-comment-positioning.md).
- **Comment metadata: an HTML-comment JSON marker, minted by code.** §2's
  "hidden/system note" does not exist - a bot cannot create a system note, and no MR
  channel is hidden from Reporter-and-above reviewers. One marker embedded in every
  comment the bot posts carries the last-reviewed SHA, review id, persona, and finding
  category, serving tickets 03, 06, 09 and part of 12 at once. DuckDB still holds the
  durable record; the marker is transport, not storage. See
  [03-last-reviewed-sha-storage.md](issues/03-last-reviewed-sha-storage.md), with the
  deferred counter-proposal in
  [13-revisit-external-storage.md](issues/13-revisit-external-storage.md).
- **Stack and layout: Python 3.13 on a uv workspace of three packages.** `core`
  (shared models, marker format, GitLab client, config), `reviewer` (the CI image),
  `collector` (the EC2 poller), with personas at the root as an input to the image.
  The split makes §6's single-writer rule structural: the review job's dependencies
  cannot reach the store. pytest colocated per package, ruff for linting and `ty`
  for type checking, with the package at `packages/core/janus_core/` and no `src/`
  layer (amended 2026-08-22).
  See [04-project-stack-and-layout.md](issues/04-project-stack-and-layout.md).
- **Diff-size cap: 60,000 tokens, counted with Anthropic's free `count_tokens`.**
  `fast` lowers it to 20,000; overrides may only lower. ~$0.50 worst case per review
  on the priciest assumed model. This removes `changes_count` from the design and
  answers ticket 11 outright: the cap is 6.75% of Opus 5's context, so a whole-diff
  call cannot overflow and per-file chunking solves nothing. Measured since against
  1,165 real merged pull requests: 60,000 covers 97.25% of them and real diffs run 2.18
  characters per token - but the GitLab-collapse arithmetic that justified the number is
  void (that line sits at 145,000-173,000 tokens), so the cap now stands on coverage
  alone. Also found that §4's non-blocking promise has a hole - a timeout or crash fails
  the job and blocks merges - closed by `allow_failure: true`. See
  [10-diff-size-cap.md](issues/10-diff-size-cap.md).
- **Comment posting is best-effort, with a scope axis.** 4xx deterministic, 5xx
  transient, but `401`/`403`/`404` are review-scoped: post nothing at all rather than
  a partial review. Unplaced findings are listed in the summary rather than posted as
  file-level notes. Crash-safe on the finding `fid` at zero extra API cost - the marker
  needed a finding id independent of the model's prose, because `review_id` cannot
  deduplicate. The key was `(head_sha, fid)` until measurement showed that every push
  mints a new head and so re-posts every finding; it is now the `fid` alone. Summary
  last. See [12-comment-posting-policy.md](issues/12-comment-posting-policy.md); five
  claims in its failure table were written before the sandbox existed and live
  measurement refuted them, which is
  [16-posting-policy-remeasured.md](issues/16-posting-policy-remeasured.md).
- **Prompt and personas: drafted, exercised, and corrected.** Running the draft against
  four diffs found three defects in it. Settled: assume every repo already lints (no
  detection) with a consequence carve-out for data loss, security, and broken
  interfaces; clarity nits are per-persona and `fast` stays defects-only; `fast` gains
  performance at blocker severity; the summary is a code template except for one
  model-written sentence on a clean review. The persona schema gains exactly one field,
  `categories`, because a machine-readable vocabulary is forced by tickets 03/06/07/12 -
  §3's free-prose `review_focus` is unchanged. See
  [08-prompt-and-persona-draft.md](issues/08-prompt-and-persona-draft.md).
- **Sandbox: a project access token, Reporter role, on a throwaway GitLab.com
  project.** `gitlab.com/manelfideles/janus-sandbox`, with credentials in the
  gitignored `.env` as `GL_PAT` and `ANTHROPIC_API_KEY`. A project access token
  replaced the second bot account §5/§6 assumed: its auto-created bot user still
  satisfies feedback attribution, and it is confined to one project. It cannot serve
  ticket 06's cross-project poller, which will need its own credential. `api` is the
  narrowest scope GitLab offers for posting a note. See
  [05-provision-local-sandbox.md](issues/05-provision-local-sandbox.md).

## Not yet specified

<!-- in-scope fog: coming, but not yet sharp enough to ticket -->

- **Build sequencing.** The skeleton needs cutting into vertical slices with an
  order. Architecture (01) has closed and the correlation ticket (06) is now
  unblocked; graduates when 06 closes.
- **Error taxonomy and the `logs` table.** §4 promises a "review could not complete"
  comment and a `logs` row, but the failure categories are unnamed. Shape depends on
  the DuckDB schema. Ticket 12 supplies one strong candidate category (a rejected
  comment position); the rate-limit 429 ticket 02 supplied turns out to reach only the
  summary comment, because inline posting is not rate limited at all.
- **Testing approach.** Partly cleared by 01: a pure-function review job can be
  replayed offline against a recorded diff, with no GitLab and no real MR. Still
  open is whether review *quality* gets any check at all beyond eyeballing.
- **Model choice and cost per review** for the local path. Ticket 10 bounded the
  worst case (~$0.50/review, ~$0.15 on `fast`) under an explicitly assumed model, and
  deliberately left the model choice itself open. Measurement adds a coupling: the cap's
  real coverage is model-specific, because Haiku 4.5 counts about 25% fewer tokens than
  Opus 5 for the same bytes. A captain hold (`diff-cap-coverage-stratum`) is open on
  whether 60,000 stays or rises to 100,000 - agent-authored repositories lose 7.09% of
  merge requests at 60,000, human-authored ones 0.64%.
- **An output-side cost bound.** The diff cap governs input only. Output is priced at 5x
  input on Opus 5, and the only thing bounding it today is `fast`'s `max_words` - a
  prompt instruction rather than an enforced limit, and null for every other persona.
  Ticket 10 §8 named the gap and recommended a ticket; none has been filed, and ticket
  11's call-shape choice multiplies it by the number of calls per review.
- **Config surface.** The 12-factor env var list that swaps local for prod (§12).
  Ticket 04 placed its owner in `packages/core`; the variable list itself is still open.
- **Docker Compose composition** — which services, and how the CI job relates to them.
  Ticket 04 gave `compose.yaml` a home at the repo root but deliberately no contents.
- **ADRs.** §10 asks for a Nygard-style ADR batch. The decisions this map makes are
  the natural input; sequencing and template are unspecified.

## Out of scope

<!-- ruled beyond the destination; never graduates -->

- **Jira context via `acli`** — cut from the skeleton. Standing up a personal Jira
  Cloud sandbox is real setup cost for a side-of-desk build, and the reviewer works
  with `jira_context: false`. Returns only if the destination is redrawn.
- **The production AWS path** — Bedrock, ECR, EC2, OIDC federation, real S3, SSM
  deploy, group-level CI variables. The skeleton stops at the local equivalents.
- **The Streamlit curator dashboard** — already deferred in §6.
- **The `security` persona** — already deferred to phase 2 in §3.
- **Multi-repo pilot rollout and the §11 success criteria** — those begin after the
  skeleton proves the design.
