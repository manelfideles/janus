# Provision the local review sandbox

Status: open
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
