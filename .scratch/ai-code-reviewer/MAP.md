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
  `new_line`, removed lines only `old_line`, unchanged context lines both. A stale
  position is rejected with a 400 rather than becoming an outdated thread, while a
  thread that goes stale *later* survives untouched - which is GitLab's default, so
  S9 needs no code at all. Posting is inherently non-atomic. See
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
  cannot reach the store. pytest colocated per package, ruff, mypy strict on `core`.
  See [04-project-stack-and-layout.md](issues/04-project-stack-and-layout.md).

## Not yet specified

<!-- in-scope fog: coming, but not yet sharp enough to ticket -->

- **Build sequencing.** The skeleton needs cutting into vertical slices with an
  order. Architecture (01) has closed and the correlation ticket (06) is now
  unblocked; graduates when 06 closes.
- **Error taxonomy and the `logs` table.** §4 promises a "review could not complete"
  comment and a `logs` row, but the failure categories are unnamed. Shape depends on
  the DuckDB schema. Ticket 12 supplies one strong candidate category (a rejected
  comment position) and ticket 02 supplies a second (a rate-limit 429 mid-review).
- **Testing approach.** Partly cleared by 01: a pure-function review job can be
  replayed offline against a recorded diff, with no GitLab and no real MR. Still
  open is whether review *quality* gets any check at all beyond eyeballing.
- **Model choice and cost per review** for the local path.
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
