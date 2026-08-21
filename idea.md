# AI-Assisted Code Review Tool — Design Doc

Status: design-interview session complete. All sections confirmed.

## 1. Goal

An AI-assisted code review tool for GitLab merge requests that:
- Automatically reviews MRs on repos that opt in
- Lets human reviewers give thumbs up/down + written reasoning feedback on the bot's comments
- Feeds that feedback into a **human-curated** rule-update loop (not automatic prompt injection)
- Supports persona selection (backend / frontend / systems / fast-budget) to match review scope
- Integrates read-only with Jira for issue context
- Runs on the company's AWS account, using Bedrock for model access

Pilot scope: 2-3 repos across different personas before wider rollout. Config/storage designed to be multi-tenant from day one.

## 2. Trigger Architecture

- **Per-repo CI/CD include** (not a centralized webhook service). Each repo opts in by adding an `include:` to its `.gitlab-ci.yml` that pulls the reviewer Docker image and runs on MR pipeline events.
- Rationale: simplest auth model (runs with the project's CI credentials), no public endpoint to secure, and "installed on a repo" maps naturally to "added to that repo's pipeline."
- Full review runs on MR creation; **incremental (diff-only)** review runs on subsequent pushes to the same MR.
- Incremental review tracking: the bot stores the **last-reviewed commit SHA in a hidden/system note on the MR itself** — no external storage dependency, keeps the ephemeral review job fully self-contained (talks only to GitLab + Bedrock).

## 3. Persona System

- Personas are YAML files, versioned in the central repo alongside the CI image (see §8 - Repo Layout).
- **No project-specific overrides** at this time — one central source of truth governs personas, to avoid model confusion / token bloat from poorly-constructed local overrides.
- Selection mechanism: **slash command in the MR description** (e.g. `/ai-review persona:backend`), parsed by the CI job via the GitLab API at run time — not a comment, and not a webhook.
  - **Known limitation**: editing the description *after* MR creation, without a new push, will not trigger a fresh pipeline run. This is documented as a pilot limitation rather than solved with new infra. The bot's summary comment always states which persona it used and includes a one-line hint on how to force a re-run (push again / re-run pipeline manually).
- **Default persona: `fast` (budget reviewer)** — chosen as the fallback specifically so an un-tagged MR gets a cheap, low-noise pass rather than a full heavyweight review.

### Pilot persona list
| Persona | Focus |
|---|---|
| `backend` | API design, data integrity, performance, security |
| `frontend` | Accessibility, state management, rendering performance, UX consistency |
| `systems` | Memory/resource discipline, concurrency, low-level correctness |
| `fast` (default) | Budget review — word cap, blockers only |

A `security` persona is deferred to phase 2, once feedback data exists to justify its rules.

### Persona YAML schema
```yaml
name: backend
description: "..."
review_focus:            # free-text checklist bullets, read as prompt content — not parsed programmatically
  - api_design
  - data_integrity
  - performance
  - security
max_words: null           # null = no cap; fast persona sets this
blockers_only: false      # fast persona sets true
jira_context: true        # whether to fetch linked Jira issue via acli
diff_size_cap_override: null   # null = use global default cap
# tool_allowlist is intentionally NOT here — it's hardcoded at the application level, not persona-configurable
```

`review_focus` is deliberately free text (like the reference slide's reviewer cards) rather than a rigid structured schema — flexibility for a curator writing checklist items matters more than machine-parseable structure, since this content only ever goes into a prompt.

## 4. Review Scope & Guardrails

- **Purely qualitative, LLM-driven review** — no orchestration of SAST/linting; those are a prior CI pipeline step and this tool complements, not replaces, them ("AI reviews complement humans, they don't replace them").
- **Hardcoded tool whitelist** (not persona-configurable):
  - GitLab: get MR diff, get MR metadata/description, list MR notes/comments, post new inline comment, post new summary comment, list award-emoji on a note.
  - Jira: get issue by key, resolve issue linked to an MR (via GitLab-Jira link or description parsing) — via **acli**, not the Atlassian MCP server (see §5).
  - Explicitly excluded: merge, close, approve, delete, or edit-existing-comment operations. Read + comment only.
- **Diff-size hard cap**, checked *before* any model call:
  - Global default cap, with optional per-persona override in YAML.
  - On breach: halt before calling any model, post a comment explaining the MR was skipped (size vs. cap), and **exit the pipeline job successfully (non-blocking)** — an AI review skip must never block a merge.
- **Failure handling** (Bedrock errors, GitLab/Jira API failures): post a "review could not complete: `<reason>`" comment, log the failure into a `logs` table (see §6) for posterior analytics in the dashboard, and exit non-blocking. No dedicated alerting infra for pilot — the weekly digest includes a simple failure-rate line.
- **Prompt assembly structure**: system prompt (org-wide non-negotiable rules) + selected persona's YAML content + fetched Jira issue context (if `jira_context: true`) + the diff itself.
- Reference materials (e.g. Matt Pocock's `/review` / `/improve-codebase-architecture`) are used **only as inspiration during rule-authoring** by human curators — never fetched or included at runtime, never reproduced verbatim.

## 5. Jira Integration

- Read-only context lookup only (v1). No write-back.
- **acli confirmed as cheaper than the Atlassian Rovo MCP server** — MCP servers load their full tool schema into context on initialization regardless of use (real-world reports of 40-50% of context window consumed before any useful work), and Rovo MCP specifically has weak project scoping / high token overhead. A CLI wrapped as a single "run command" tool avoids that upfront cost.

## 6. Feedback Loop

- **Capture mechanism**: native GitLab emoji reactions (👍/👎) on the bot's own comments, plus an optional human reply with written reasoning on why the review was good/bad.
- Ideal flow: reviewer reacts + explains why. If they don't, the bot simply doesn't improve on that data point — but it also doesn't deteriorate. Every extra piece of feedback is a net win, never a cost.
- **Incorporation strategy**: **human-curated**, not automatic prompt injection or retrieval. Feedback is aggregated and a curator periodically updates persona YAML / org-wide rules based on patterns. Rationale: avoids "garbage rules = garbage reviews" risk of unreviewed automated rule changes, and keeps token expenditure down (no retrieval overhead per review).
- **Collection mechanism**: a standalone, always-on Python `schedule`-based poller (not a GitLab/AWS-native webhook or Lambda, to avoid vendor lock-in) walks recently-reviewed MRs, pulls award-emoji + reply threads on the bot's own comments, and writes results to storage.
  - This process is the **only** writer to the feedback store — the ephemeral per-MR review job never touches it, keeping that job's dependencies limited to GitLab + Bedrock.
- **Storage**: **DuckDB** — single-file, relational, zero extra deployment infra, good fit for a single-writer access pattern and analytical curator queries ("top downvoted comment categories per persona, last 30 days").
- **Failure/error logs**: a `logs` table in the same DuckDB store, feeding the dashboard's failure-rate reporting.
- **Curator-facing reporting**: a **Streamlit dashboard** with simple visualizations run against the DuckDB data (exact contents TBD later — deferred as a lower-priority detail).
- **Bot identity**: dedicated GitLab bot/service account (e.g. `ai-reviewer-bot`), scoped to minimal permissions (comment + read MR, nothing destructive). Makes feedback attribution and reaction-polling unambiguous.

## 7. Infra & Hosting

- **Model access**: Amazon Bedrock (corporate AWS account).
- **Auth from GitLab CI → AWS**: OIDC federation (GitLab CI ID token exchanged for temporary AWS credentials via IAM role trust policy) — no long-lived secrets. Same role also grants ECR pull permissions (see below).
- **Container registry**: **ECR** (consistent with other images in the project already using ECR). Semver tags; pilot repos pin to explicit versions (no `latest` in steady state) so a persona-schema change doesn't silently break their pipeline mid-review.
- **Scheduler/feedback-collector hosting**: a **small EC2 instance** running the `schedule`-based poller as a long-lived process.
  - DuckDB file backed up to **S3 hourly** (feedback data is low-volume, so hourly is cheap and keeps the loss window negligible on crash/replacement).
  - On boot/replacement, the box restores the latest DuckDB snapshot from S3 before starting the scheduler.
- **Deploy mechanism for the EC2 scheduler**: triggered from the monorepo's own pipeline via **SSM Run Command** (auditable, tied to a merge, no long-lived SSH keys).
- **GitLab/Jira credentials**: bot's GitLab token and Jira API token stored as **masked, protected CI/CD variables at the group level** (shared across pilot repos' pipelines without per-repo duplication). Manual rotation on a ~90-day cadence for pilot — automating rotation (e.g. via Secrets Manager) deferred until the tool graduates past pilot.
- **Cost/runaway governance**: diff-size hard cap (per §4) plus a pipeline job timeout, regardless of persona.

## 8. Repo Layout

**Single monorepo** containing:
- The CI/CD review-job Docker image + agent wrapper code
- All persona YAML files (single source of truth, no per-project overrides)
- The scheduler/feedback-collector service (different deployment lifecycle — long-running service vs. a consumed image — but kept in the same repo per explicit preference)
- ADRs (`docs/adr/`, Nygard-style template: Context / Decision / Consequences)

**Internal CI/CD for the monorepo**: path-based pipeline rules — a change to `scheduler/` only triggers a scheduler deploy (via SSM), a change to the review-image code or `personas/` only triggers an image build/publish to ECR. Avoids unnecessary rebuilds/redeploys of the unrelated half of the repo.

## 9. Comment Posting Behavior

- Each re-review posts a **fresh summary comment**; prior inline comments are left untouched even if the referenced code has since changed (full history preserved over automatic thread-resolution, to avoid false "resolved" calls). Revisit if MR noise becomes a real complaint.
- Every summary comment states which persona was used.

## 10. ADRs

All significant decisions in this document are to be recorded as individual ADRs in `docs/adr/` within the monorepo, using a lightweight Nygard-style template (Context / Decision / Consequences). Initial batch to cover at minimum:
- Trigger architecture (CI/CD include vs. webhook)
- Persona system design (selection mechanism, schema, no project overrides)
- Feedback loop design (human-curated vs. automated incorporation)
- Storage choice (DuckDB)
- Auth model (OIDC, credential storage)
- Tool whitelist / guardrails
- Repo layout (monorepo, path-based CI)

## 11. Pilot Success Criteria (informal, re-evaluate after a few weeks)

- Feedback ratio: 👍 outweighs 👎 on bot comments over a sustained window (2-4 weeks)
- Adoption signal: reviewers engaging with reactions/replies rather than bypassing/ignoring the bot
- No recurring complaints driven by diff-size skips or Bedrock/API failures

This is explicitly a subjective checkpoint, not an automated gate.

## 12. Local Development / Reproduction (pending final confirmation)

Goal: reproduce the full tool locally with **no changes to production code**, without touching the company AWS account, while staying high-fidelity and usable for iterative testing.

Approach: a 12-factor-style config swap — same code path everywhere, only env-driven configuration/credentials differ between local and prod.

| Component | Production | Local (recommended) |
|---|---|---|
| GitLab | Company self-managed instance | Personal/free GitLab.com namespace + throwaway test project — same generic GitLab API v4 endpoints (MR diff, notes, award-emoji, CI variables) are used either way, so fidelity is equivalent without standing up a self-hosted GitLab CE instance |
| Model | Amazon Bedrock | Direct Anthropic API via a personal/dev key, behind a `ModelClient` interface (`BedrockClient` / `AnthropicClient`) selected by env var — formalizes the provider-abstraction already motivated by the vendor-lock-in concern in §6 |
| Jira | Company Jira Cloud | Personal/free Jira Cloud sandbox, same `acli` invocation, different site/token |
| Container registry | ECR | Local `docker build`/`docker run`, no push needed |
| Scheduler + DuckDB + Streamlit | EC2 + S3 backup | Same code, run via local docker-compose; DuckDB is already just a local file |
| S3 backup path | Real S3 bucket | **MinIO container** in the local docker-compose stack — exercises the real backup/restore code path against the same S3 API, fully offline and zero cost |
| Bot identity | Dedicated corporate service account | Personal/secondary GitLab.com account |
| Secrets | Group-level masked CI/CD variables | Local `.env` file (gitignored) |

**Confirmed:**
- **GitLab substitute**: a personal/free GitLab.com namespace + throwaway test project (not a self-hosted GitLab CE container). The tool only uses generic GitLab API v4 endpoints (MR diff, notes, award-emoji, CI variables), none of which differ between SaaS and self-managed, so this gives equivalent fidelity without the ~4GB+ RAM overhead of running GitLab CE locally.
- **Model provider**: a `ModelClient` interface with `BedrockClient` (prod) / `AnthropicClient` (local, using a personal/dev Anthropic API key) implementations, selected via env var (e.g. `MODEL_PROVIDER=bedrock|anthropic_api`). This formalizes the same abstraction already motivated by the vendor-lock-in concern in §6 — not extra work, just making the interface explicit.
- **S3 backup path**: a **MinIO container** added to the local docker-compose stack, so the backup/restore code exercises the real S3 API offline and at zero cost, rather than being a code path that's only ever tested for the first time in production.

This closes out the local/dev environment design — no open items remain in this section.
