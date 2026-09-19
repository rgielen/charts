---
name: called-workflow-permissions
description: a reusable workflow may not request more permissions than the calling job grants; violating it is a startup_failure with no jobs and no logs, every run
metadata:
  type: project
---

A workflow invoked through `workflow_call` can only *downgrade* the `GITHUB_TOKEN`
permissions of the job that calls it. If any job in the called workflow requests more —
including through a workflow-level `permissions:` block, and regardless of that job's `if`
— GitHub rejects the entire caller run before it starts: conclusion `startup_failure`, an
empty job list, no logs. The only trace is an annotation on the run's web page
("The nested job 'build' is requesting 'contents: write', but is only allowed
'contents: read'"); `gh run view` merely says "likely failed because of a workflow file
issue". `curl` the run page and grep for `requesting` to get the actual message.

This broke `upstream-sync.yaml` after #53 (2026-09-17): its `render` job called
`pages.yaml` with `contents: read` for least privilege, while `pages.yaml` declares
`contents: write` for its push path. The nightly runs of 2026-09-18 and -19 failed at
startup — also on nights with no pending update, because the check is static. Fixed by
granting `contents: write` to the calling job; `render_only` is what prevents the push.

**Why:** the failure looks like a broken YAML file and is caught by neither `actionlint`
nor a pull request run, because `pull_request` never exercises the `workflow_call` path.

**How to apply:** when a job `uses:` a local reusable workflow, its `permissions:` must be
a superset of everything the called workflow declares. After changing either side, prove
it with a `workflow_dispatch` of the caller from the branch — for `upstream-sync.yaml`,
`-f chart=<nonexistent>` yields `updates=[]` and therefore no side effects, yet still
passes the startup validation. Related: [[github-token-does-not-trigger-workflows]].
