# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

## What janus is

An AI code reviewer for GitLab merge requests. `idea.md` is the locked design doc
and is the authority on intent; `.scratch/ai-code-reviewer/issues/` holds the
decision tickets, and a ticket marked `Status: closed` is settled — read it rather
than re-deciding it. `.scratch/ai-code-reviewer/MAP.md` lists what is still open.

## Commands

```sh
uv sync                     # from a clean checkout; uv manages the interpreter
uv run pytest               # tests are colocated in packages/<pkg>/tests
uv run ruff check           # lint
uv run ruff format --check  # format
uv run mypy                 # strict on ai_reviewer_core, looser elsewhere
```

## Layout, and the rule that makes it worth the ceremony

Three packages under `packages/`, one uv workspace, one lockfile. See ticket 04
for the full rationale. The dependency rule is load-bearing, not stylistic:

- `core` — shared, no I/O dependencies and no runtime dependencies at all.
- `reviewer` — depends on `core` plus a model client. **Never `duckdb` or an S3 client.**
- `collector` — depends on `core` plus `duckdb`, `schedule` and an S3 client. **Never a model client.**

idea.md §6 says the collector is the *only* writer to the feedback store. The split
is what enforces that: the review job's dependency set cannot reach the store.

**Keep `core` small.** Ticket 04's CI rules make a change under `packages/core/`
rebuild the review image *and* redeploy the collector, because both depend on it.
Size of `core` is a CI concern, not only taste.

Tests are colocated per package because the path-based CI rules need a change under
`packages/collector/` to trigger only the collector deploy.

## Sharp edges

- **`ai_reviewer_core.marker` is a wire format, not a struct.** The reviewer writes
  markers and the collector parses them, and they deploy separately. Never change
  the payload without bumping `MARKER_VERSION` and teaching the parser both
  versions. A silent drift breaks feedback attribution with no error at all — rows
  just stop matching. Its docstring carries the compatibility rules.
- **`LineKind` is closed on purpose.** GitLab infers a diff line's kind purely from
  which line numbers the `position` hash carries, and omit means omit — not `null`,
  not `0`. Ticket 02 has the table.
- **New config variables need a settled source.** `config.py` holds only values a
  closed ticket or a settled report fixes. If a value is not settled, leave it out
  and say so rather than inventing a default there.
- **CI forge is unresolved.** idea.md §8 and ticket 04 specify GitLab CI; the git
  remote is GitHub. Both are true — production targets the company GitLab, the
  GitHub remote is where this work is kept. No pipeline configuration exists yet,
  deliberately.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
