# Provision the local review sandbox

Status: closed
Labels: wayfinder:ticket, wayfinder:task
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —

## Question

Nothing to decide here — the skeleton simply cannot be exercised until the external
accounts exist. This ticket is the checklist, driven by hand.

To stand up:

- A personal or free GitLab.com namespace, and a throwaway project inside it with at
  least one branch and one open MR to review.
- A secondary GitLab.com account acting as `ai-reviewer-bot`, added to that project
  with the minimum role that can comment on and read MRs.
- A personal access token for the bot account, scoped as narrowly as the required
  API calls allow.
- Confirmation that the throwaway project has CI runner minutes available, since
  §12 keeps a real pipeline run inside the skeleton.
- An Anthropic API key for local model access, on a key separate from anything else.

Jira is out of scope for the skeleton, so no Jira sandbox is needed.

Resolve by recording what was created, where each credential is stored locally, the
bot account's exact role, and the throwaway project's path — later tickets depend on
those facts.

## Resolution, 2026-08-22

**Sandbox project.** `https://gitlab.com/manelfideles/janus-sandbox`. Every later
ticket that needs a live call runs against this path.

**Bot identity: a project access token, not a second account.** The checklist above
assumed a secondary GitLab.com account, as §5/§6 wrote it. A project access token
was taken instead. GitLab auto-creates a bot user for such a token, so notes still
carry a distinct author, which is all §6's feedback attribution actually requires.
The token is confined to this one project, so the blast radius of a leak is one
throwaway repo rather than a whole namespace, and it costs no second email and no
second identity verification.

The trade this accepts: a project access token can only see its own project. The
future cross-project feedback poller (ticket 06) needs `scope=all` across many
projects, which a project-scoped token cannot serve. When that poller becomes real,
it needs its own credential — most likely the group- or user-level token the
original checklist imagined. Nothing in the skeleton depends on that yet.

**Role: Reporter.** Reporter can read a merge request's diff and post notes, which
is the complete set of things the reviewer does. Developer would additionally allow
pushing code and altering the project, which the reviewer never needs. Ticket 03
rejected the description-field and label-field storage options specifically to keep
Reporter sufficient; that choice is what makes this row possible.

**Token scope: `api`, and this is a known limitation.** GitLab has no fine-grained
"read merge requests and comment" scope. Posting a note requires the broad `api`
scope, which also grants far more than the reviewer uses. Confining the token to a
single project is the only containment GitLab actually offers here. Worth revisiting
if GitLab ships finer scopes.

**Credentials.** Both live in the repo-root `.env`, which `.gitignore` covers
(`.env` and `.env.*`, with `!.env.example` excepted). Verified: `.env` is untracked
and appears in no commit on any branch. Variable names:

- `GL_PAT` — the project access token above.
- `ANTHROPIC_API_KEY` — a key created for this project alone, so it can be revoked
  without disturbing anything else.

`.env.example` carries the same two names with empty values, as the committed record
of what a fresh checkout must supply.

Note for ticket 10: `count_tokens`, which the diff cap depends on, is free of charge
but carries its own separate rate limit. Test loops that call it per diff can hit
that limit while the message budget is untouched.

**CI runner minutes.** The GitLab.com account is identity-verified, which is the
condition GitLab places on shared-runner access, so shared runners are expected to
be available. Not yet proven by an actual pipeline run — the first pipeline the
sandbox executes is the confirmation. If shared runners turn out to be unavailable,
the fallback is a self-hosted runner on the development machine; nothing in the
design depends on which of the two runs the job.

**Still outstanding.** The open merge request itself. It should carry a mixed diff —
added lines, at least one removed line, and untouched context lines between them —
because ticket 02's positioning rules differ per line kind and a single-line diff
cannot exercise them. Until that MR exists, the live-verification pass below has
nothing to run against.

## What this unblocks

Tickets 02, 03, 10, and 12 closed on documented and source-read evidence, and each
flagged the claims that only a live call can settle. Those claims are now runnable
in one pass against this sandbox — every one of them names the exact call that
settles it. The highest-value ones:

- The stale-position POST failure: ticket 02 read `400` with the message
  `Failed to find diff line for: <path>, old_line: N, new_line: M` out of the
  source, while the documentation is silent on it. Ticket 12's whole
  deterministic-versus-transient split rests on that status code being `400`.
- Whether the inline-note rate limit is really invisible in response headers, and
  whether it applies to note creation on merge requests at all.
- Whether `position_type=file` notes survive a force-push, as the source implies.
- Whether the HTML-comment marker from ticket 03 survives a round trip through
  GitLab's note rendering unaltered, which the whole SHA-storage decision assumes.
