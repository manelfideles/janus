# Project stack and monorepo skeleton layout

Status: closed
Labels: wayfinder:ticket, wayfinder:grilling
Parent: ../MAP.md
Assignee: unassigned
Blocked by: —

## Question

What does the empty monorepo look like on disk, and what runs it?

`idea.md` §8 fixes the contents — review-job image and agent wrapper, persona YAML,
the scheduler/feedback-collector, `docs/adr/` — but not the directory names, and
nothing fixes the stack. Python is implied by `schedule` and `acli`, never stated.

Settle:

- Language and version. Python, and which one?
- Package and environment manager — `uv`, Poetry, plain pip plus a lockfile.
- Directory layout for the three halves: review job, scheduler, personas.
- Whether the review job and scheduler share one package or are two, given they have
  different deployment lifecycles but live in one repo.
- Test framework and where tests live.
- Lint and format toolchain.
- The path-based CI rules from §8 — which paths map to which internal pipeline.

Small ticket. The point is that the next ticket can create files without stopping to
ask where they go.

## Decision

Settled with the captain, 2026-08-21.

### Stack

| Choice | Value | Why |
|---|---|---|
| Language | Python | Implied by S6's `schedule` poller and S5's `acli`; never stated in the doc, now stated here. |
| Version | **3.13**, pinned at the workspace root | Deliberately not the newest. DuckDB and pyarrow wheel availability is the binding constraint, not language features. `uv` makes the pin one line, so revising it is cheap. **Verify DuckDB publishes wheels for the pinned version before the first code ticket commits**; if a newer version is clean, take it. |
| Package/env manager | **uv**, workspace mode | Workspaces are first-class, so three interdependent packages need no path-dependency workarounds and share ONE lockfile with one resolution. It manages the interpreter itself, so the Dockerfile needs no pyenv and no system Python. Install time is negligible, which matters because the review job is an ephemeral CI job whose cold start is part of S4's cost governance. `uv --package <name>` maps directly onto S8's path-based CI rules. |
| Test framework | **pytest**, colocated per package | See "Why tests are colocated" below - this is forced by S8, not taste. |
| Lint + format | **ruff** for both | One tool, fast enough for every commit. |
| Types | **mypy**, strict on `core`, looser elsewhere | `core` owns the marker format and the shared models that tickets 03, 06, 07, 09 and 12 all depend on. It is the one place a type error costs real debugging. |

### Three packages, not one

```
pyproject.toml            # uv workspace root, Python pin, shared dev deps
uv.lock                   # single lockfile, one resolution
packages/
  core/                   # ai-reviewer-core
    src/ai_reviewer_core/
    tests/
  reviewer/               # ai-reviewer            (the CI image)
    src/ai_reviewer/
    tests/
    Dockerfile
  collector/              # ai-reviewer-collector  (the EC2 poller)
    src/ai_reviewer_collector/
    tests/
personas/
  fast.yaml
  backend.yaml
docs/adr/
compose.yaml              # local stack (S12)
```

Dependency rules, which are the point of the split:

- `core` - shared, no I/O dependencies. Holds the comment marker format (write **and** parse), the domain models, the GitLab API client, and the 12-factor config surface.
- `reviewer` - depends on `core`, plus the model client. **No `duckdb`, no MinIO/S3 store client.**
- `collector` - depends on `core`, plus `duckdb`, `schedule`, and the S3 client. **No model client.**

**Why three, and why `core` is not optional.** S6 states that the poller "is the **only** writer to the feedback store - the ephemeral per-MR review job never touches it." In a single package that rule is enforced only by somebody remembering it. With this split it is enforced by the dependency graph: the review job's dependency set cannot reach the store.

A naive two-way split with no shared package is worse than either, because the **marker format would exist twice**. The review job writes it and the poller parses it, so a drift between the two silently breaks feedback attribution with no error at all - rows simply stop matching. Tickets 03, 06, 09 and 12 all depend on that format, so it gets exactly one owner.

### Why tests are colocated

`packages/<pkg>/tests/`, not one top-level `tests/`.

This is forced by S8's path-based CI rules, not preference. Those rules need a change under `packages/collector/` to trigger *only* the scheduler deploy. A shared top-level test directory makes every test edit look like it touched everything, and the path rules stop discriminating.

### Personas live at the root

Not inside a package. S3 makes them a single source of truth with no per-project overrides, and S8 wants a persona change to rebuild the image - so they are an **input to the image**, not library code.

### S8 path-based CI rules

| Change under | Triggers |
|---|---|
| `packages/reviewer/**` | Build and publish the review image |
| `personas/**` | Build and publish the review image |
| `packages/collector/**` | Deploy the scheduler |
| **`packages/core/**`** | **Both** |
| `uv.lock`, root `pyproject.toml` | Both |
| `docs/**`, `*.md` | Neither |

**Recorded consequence, so nobody discovers it the hard way:** the fourth row is the price of the three-package split. A change to shared code rebuilds the image *and* redeploys the scheduler, because both halves depend on `core`.

S8's stated goal was avoiding "unnecessary rebuilds/redeploys of the unrelated half of the repo". A `core` change genuinely is not unrelated, so this is correct rather than a regression - but it means **keeping `core` small is now a CI concern, not only good taste.** If shared-looking code drifts into `core`, the result is the single-package option with extra ceremony.

### Deliberately not settled here

`compose.yaml` has a home in the layout but no contents. **Which services the local stack runs** remains unspecified fog on the map (S12 requires the collector, DuckDB as a plain file, and a MinIO container; how the CI job relates to them is open).

## Amendment, 2026-08-22

Two parts of the decision above are superseded. The original text is left in place
because the reasoning behind the three-package split is unchanged and still load-bearing;
only the layout depth and the type-checking tool moved.

### Layout: no `src/` layer, and the import name is `janus_core`

```
packages/core/janus_core/__init__.py
packages/core/janus_core/marker.py
packages/core/janus_core/models.py
packages/core/janus_core/config.py
packages/core/tests/...
```

Distribution `janus-core`, import `janus_core`. The `src/<import_name>/` form recorded
above is dropped.

**Why.** The captain found `packages/core/src/ai_reviewer_core/marker.py` needlessly
deep and flattened it to bare top-level modules (`from marker import ...`). Two facts
settled where it landed, both verified rather than assumed:

1. **uv's build backend cannot package bare top-level modules.** It requires a directory
   package: `Expected a Python module at: src/<name>/__init__.py`. Setting `module-name`
   does not help - it just demands that directory under the new name. Bare modules would
   need a different build backend (hatchling with a hand-maintained `only-include` list
   works) or no packaging at all.
2. **Bare generic module names collide across the three packages.** `reviewer` and
   `collector` will each want a `config.py`. Two modules named `config` installed into
   one environment resolve by `sys.path` order, silently and wrongly. `marker` and
   `models` are generic enough to collide with third-party distributions too.

Dropping `src/` rather than the package name gives the captain **exactly the file depth
they wanted** - `packages/core/janus_core/marker.py` is the same depth as
`packages/core/src/marker.py` - with no build-backend change and no collision. The
`src/` layer was what cost the depth, not the package name.

### Type checking: `ty`, not mypy. Linting stays ruff with the same rules.

mypy is removed entirely, on the captain's instruction. `ty` (Astral's type checker)
replaces it.

The ruff rule selection is **unchanged** - `E W F I B UP SIM RUF ANN PT TID`. The
captain's instruction was explicit that the rules stay and only the tooling differs.

One distinction worth keeping straight, because it is easy to lose: ruff's `ANN` rules
only check that annotations are **present**. mypy was checking they were **correct**.
`ty` is what replaces that second half. So `ANN` stays in ruff as the annotations-exist
gate, and `ty` does the checking. The "strict on `core`, looser elsewhere" intent above
is reproduced with `ty` as far as `ty` supports it; `ty` is young, and any part of the old
strictness that could not be reproduced is recorded in the pull request rather than
quietly dropped.

### A Makefile is the entry point

Four targets, following the captain's existing convention in
`aih-model-analysis-dashboard`: `test` (least verbose useful output), `typecheck`,
`lint`, `lint_fix`.

The Makefile deliberately does **not** invoke `rtk`. rtk exists to compress command
output for an agent's context, so putting it inside the Makefile would compress it for
the human at the terminal too, hiding detail they may want. The Makefile stays plain and
the wrapper is the caller's choice; the project's `AGENTS.md` records how an agent should
wrap these targets.

### codegraph

The repository is indexed with `codegraph` for symbol and call-graph lookup. The index is
a local artefact and is gitignored, not shared source.
