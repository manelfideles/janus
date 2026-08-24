# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

## What janus is

An AI code reviewer for GitLab merge requests. `idea.md` is the locked design doc
and is the authority on intent; `.scratch/ai-code-reviewer/issues/` holds the
decision tickets, and a ticket marked `Status: closed` is settled — read it rather
than re-deciding it. `.scratch/ai-code-reviewer/MAP.md` lists what is still open.

## Commands

The `Makefile` is the entry point. It stays plain on purpose — see the rtk section below.

```sh
make setup      # uv sync from a clean checkout; uv manages the interpreter
make test       # pytest; tests are colocated in packages/<pkg>/tests
make typecheck  # ty check packages/core
make lint       # ruff check + ruff format --check
make lint_fix   # ruff check --fix + ruff format
```

Type checking is `ty`, not mypy. `ty` has no `strict` switch, so ticket 04's "strict on
`core`, looser elsewhere" is expressed as a `[[tool.ty.overrides]]` block in the root
`pyproject.toml` that promotes every rule to error-level under `packages/core/**`.
Ruff's `ANN` rules are the "annotations are present" half of that gate; `ty` checks that
they are correct. Suppressions use ty syntax (`# ty: ignore[rule-name]`), not mypy's.

## Running commands through rtk

The captain runs `rtk`, a CLI proxy that compresses command output before it reaches an
agent's context. An agent working in this repo calls the Makefile targets through it:

```sh
rtk test make test        # only failures
rtk err make typecheck    # only errors and warnings
rtk err make lint         # only errors and warnings
```

A human or a CI job runs `make test` and friends directly.

Keep rtk *out* of the Makefile. rtk exists to compress output for an agent's context, so
baking it in would also compress it for the human reading the terminal and hide detail
they may want. The Makefile stays plain; the wrapper is the caller's choice.

There is no `rtk` subcommand for `uv`, `make`, or `ty`, which is why the general `rtk err`
and `rtk test` wrappers are the route. `rtk git`, `rtk gh` and `rtk glab` wrap those CLIs.
`rtk format` understands `ruff format`. `rtk ruff` and `rtk pytest` also exist, but they
call the tools directly and so bypass the Makefile.

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

Each package is a directory package at `packages/<pkg>/<import_name>/`, with no `src/`
layer. Bare top-level modules were tried and rejected: uv's build backend requires a
directory package, and three packages each exposing a bare `config.py` would collide
silently on `sys.path`. Distribution names track import names (`janus-core` /
`janus_core`) so the two never have to be mapped in your head.

## Sharp edges

- **`janus_core.marker` is a wire format, not a struct.** The reviewer writes
  markers and the collector parses them, and they deploy separately. Never change
  the payload without bumping `MARKER_VERSION` and teaching the parser both
  versions. A silent drift breaks feedback attribution with no error at all — rows
  just stop matching. Its docstring carries the compatibility rules.
- **A finding's identity is its diff line's text, never its line number.**
  `finding_fid` hashes `line_text`; `Marker.dedup_key` is the `fid` alone. A line number
  moves when anything above it is inserted, and every push mints a new `head_sha`, so
  either one in the key re-posts the whole review on its second run. The marker keeps
  carrying `head_sha` for ticket 03's last-reviewed-commit channel, which is a different
  job. `finding_fid`'s docstring carries the whitespace and collision reasoning.
- **GitLab never mis-anchors a moved comment**, measured live: threads on the previous
  head are traced forward, older threads stay frozen and still render against the code
  they were written about, and posting with a stale `head_sha` returns 201 re-anchored.
  So there is no stale-position handling to build. Do not add one.
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
