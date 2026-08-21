# Project stack and monorepo skeleton layout

Status: open
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
