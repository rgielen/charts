---
name: github-token-does-not-trigger-workflows
description: GITHUB_TOKEN triggers no workflow run -- not for a PR it opens, and not for the push its merge makes; upstream-sync answers with workflow_call and workflow_dispatch
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

The **merge** has the same problem and it is the more dangerous half: `gh pr merge` in
that workflow pushes to `main` with the same token, so `release.yaml` (`on: push`) never
runs. Chart 2.3.1 (#43, 2026-09-04) and 2.5.1 (#48, 2026-09-12) landed on `main` unpublished
— no failed job, no warning, and the next nightly run sees `appVersion` already current and
says nothing. 2.3.1 never shipped; 2.5.1 was released by a manual `workflow_dispatch` hours
later, once the gap was noticed. Every release that happened on its own had been merged by a
human. Fixed by dispatching `release.yaml` from the merge job: `workflow_dispatch` and
`repository_dispatch` are the two events `GITHUB_TOKEN` may still raise — and the dispatch
needs `actions: write`, which the workflow's own permissions block did not grant.

**How to apply:** any future automation that opens a PR and then wants it verified must
call the reusable workflow rather than wait for a check run; anything that *merges* must
start the follow-on workflow explicitly, because no push it makes will. When a pipeline
here reports success but nothing shipped, check the actor on the merge commit first. If a
check ever *must* run on the PR itself (a required status check on a protected branch,
say), that is the point where a GitHub App token becomes unavoidable.
