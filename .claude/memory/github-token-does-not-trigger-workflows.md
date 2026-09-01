---
name: github-token-does-not-trigger-workflows
description: A PR opened with GITHUB_TOKEN never triggers pull_request workflows, so upstream-sync calls lint-test via workflow_call instead of waiting for it
metadata:
  type: project
---

GitHub deliberately does not start new workflow runs for events caused by the built-in
`GITHUB_TOKEN`. A pull request that `.github/workflows/upstream-sync.yaml` opens therefore
never triggers `lint-test.yaml` on its own, and any "wait for checks, then merge" logic
would wait forever.

The repository solves this without a credential: `lint-test.yaml` also declares
`workflow_call` with a `ref` input, and `upstream-sync.yaml` invokes it as a job inside its
own run. Lint and install stay implemented exactly once, and there is no personal access
token to rotate or let expire.

**Why:** the obvious alternatives are both worse — a fine-grained PAT in a repository
secret (expires, and `CLAUDE.md` advertises that no repository secret is involved), or
duplicating `ct lint` / `ct install` into the sync workflow (drifts).

**How to apply:** any future automation that opens a PR and then wants it verified must
call the reusable workflow rather than wait for a check run. If a check ever *must* run on
the PR itself (a required status check on a protected branch, say), that is the point where
a GitHub App token becomes unavoidable.
