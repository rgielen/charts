---
name: open-followups
description: "OPEN as of 2026-09-01: four things verified only by reasoning or still waiting on an external run"
metadata:
  type: project
---

Everything built on 2026-09-01 is released and verified except the items below. Each one
is either waiting on somebody else's schedule or was concluded from evidence rather than
observed directly.

**1. The Renovate `ignorePaths` fix is not confirmed.** `config:recommended` pulls in
`:ignoreModulesAndTests`, whose `ignorePaths` include `**/tests/**`, which hid
`curlimages/curl` in `charts/manifest-llm-gateway/templates/tests/test-health.yaml` from
the regex manager. `ignorePaths` was overridden, but the hosted Renovate instance had not
re-scanned yet — the dependency dashboard still showed the old state and the manual-run
checkbox was ticked but unconsumed. Check:

```sh
gh issue view 8 --json body --jq '.body' | grep -A3 "test-health"
```

Confirmed once `curlimages/curl` appears under *Detected Dependencies*. If it still does
not, the cause is elsewhere and the regex in `customManagers[1]` is the next suspect —
though it was checked against the file content and matches. See
[[helm-docs-template-concatenation]] for the other silent-failure trap in this repo.

**2. The nightly `upstream-sync` run has never happened.** Both dry runs used
`workflow_dispatch`. On a `schedule` event the `inputs` context is unavailable and
evaluates to the empty string, which `${CHART:+--chart "$CHART"}` turns into "check every
chart" — that is reasoning plus the observed `pull_request` equivalent, not a
`schedule`-triggered observation. The cron is `17 5 * * *` UTC. Watch the first one; a
failure there is a one-line fix, but nobody will notice it unless they look.

**3. `gh` here has no `workflow` scope.** Pull requests touching `.github/workflows/**`
cannot be merged through the API (`refusing to allow an OAuth App to create or update
workflow ... without workflow scope`); #7 and #11 were squashed locally over SSH and
closed by hand instead. `gh auth refresh -s workflow` fixes it, and needs an interactive
browser round trip the user has to do.

**4. The inotify limits may not be persistent.** `kind` needs more than the default 128
`fs.inotify.max_user_instances`; below that `kube-proxy` dies with
`fsnotify watcher init: too many open files`, CoreDNS never becomes ready, and the symptom
that reaches you is `EAI_AGAIN` on the database hostname — nothing that points at inotify.
Raised at runtime on 2026-09-01, but making it survive a reboot was left to the user:

```sh
printf 'fs.inotify.max_user_instances = 512\nfs.inotify.max_user_watches = 524288\n' \
  | sudo tee /etc/sysctl.d/99-inotify.conf
sudo sysctl --system
```

**How to apply:** work through these at the next session and delete each one as it closes;
delete the file when all four are done.
