---
name: open-followups
description: "OPEN: inotify limits; the drift check blind to settings read only in code; upstream-sync stacking stale pull requests; index rebuild time on the consumers (2026-10-01)"
metadata:
  type: project
---

Everything built on 2026-09-01 is released and verified except the items below. Each one
is either waiting on somebody else's schedule or was concluded from evidence rather than
observed directly.

**1. ~~The Renovate `ignorePaths` fix is not confirmed.~~ Resolved 2026-09-01.** Renovate
now lists `charts/manifest-llm-gateway/templates/tests/test-health.yaml` under *Detected
Dependencies* and has opened a pull request for `curlimages/curl`. The delay had a second
cause worth remembering: the `_comment_ignorePaths` key added alongside the fix made the
whole configuration invalid and stopped Renovate opening pull requests at all — see
[[renovate-json-has-no-comments]].

**2. ~~The nightly `upstream-sync` run has never happened.~~ Resolved 2026-09-02.** It
fired on schedule at 05:31 UTC, detected 6.19.1 → 6.20.0, and held the pull request because
the configuration surface had changed. The whole chain — detect, drift check, branch, pull
request, verify — ran unattended and correctly.

**3. ~~`gh` here has no `workflow` scope.~~ Resolved 2026-09-02.** The user ran
`gh auth refresh -h github.com -s repo,workflow`; pull requests touching
`.github/workflows/**` now merge through the API, and the local-squash workaround is no
longer needed.

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

**5. The drift check still cannot see a setting read only in code.** Since 2026-10-01
`chart_audit.py` scans `charts.rgielen.de/upstream-source-roots` for `process.env` reads,
but the audit only runs in the `review` job, and that job only runs on a pull request
`upstream_diff.py` already held. `upstream_diff.py` compares the `-watch-paths` files
alone. An upstream release that adds a variable in a service file, and touches none of
those files, comes back `clean` and merges unattended. 6.26.1 was caught only because the
upstream also edited both `.env.example` files. Closing this means having the drift check
compare the env-read set at both commits and answer `review` when it grows. That changes
what gets merged unattended, so it needs a decision first. Separately, the first scan
listed 16 such settings for `manifest-llm-gateway` that nobody has classified yet;
`TRUST_PROXY` and `DATABASE_UNPOOLED_URL` are the operational ones.

**6. `upstream-sync` stacks pull requests while one is on hold.** Each night it opens a
new `upstream/<chart>-<tag>` branch for the newest tag, cut from `main` and versioned from
`main`'s `Chart.yaml`. While a pull request is held, `main` stays put, so every later one
starts from the same base and computes the same `version`. Between 2026-09-28 and
2026-10-01 that produced #61 (6.26.1), #62 (6.27.0) and #63 (6.28.1), all based on 6.25.5
and all at `version: 2.9.0`. Once #59 shipped 2.9.0, each one conflicted, and merging any
of them with the conflict resolved would have released nothing. #61 and #63 were rebuilt
on `main` by hand (2.10.0, 2.11.0) and #62 was closed. The fix: when an
`upstream/<chart>-*` pull request is already open, the sync should move that branch to the
new tag, recut from current `main`, and retitle it. It should not open another. Today the
existence check at `upstream-sync.yaml` (`git ls-remote ... "$branch"`) only matches the
exact tag, so it never notices the older branch. Until this is fixed: **before merging an
`upstream/*` pull request, check that its `Chart.yaml` `version` is above the last
published one and that it is not `DIRTY`.**

**7. The 6.26.0 index rebuilds have not been timed.** Upstream 6.26.0 (chart 2.9.0) adds
`1803000000000-CoverRequestsLogFilters` and `1803100000000-CoverHarnessRequestsIndex`.
They rebuild `requests` indexes with `CREATE INDEX CONCURRENTLY` inside the pre-upgrade
hook Job, and `manifest.migrations.job.activeDeadlineSeconds` defaults to 900. Nobody
measured how long these take on k3s-nuc or k3s-ze. When those clusters move from a
version below 2.9.0, watch the migration Job. A Job killed mid-build can leave an
`INVALID` index behind, and whether the upstream's in-place rebuild recovers from that was
not checked.

**A scheduled routine checks this file.** `rgielen/charts — open follow-ups`
(`trig_01GGA4bUnenMByUoaKa6TeYF`, Mondays 07:00 UTC,
<https://claude.ai/code/routines/trig_01GGA4bUnenMByUoaKa6TeYF>) reads this file, verifies
what is verifiable from a cloud sandbox — item 2 above, essentially — and reports the rest
as "you have to run this yourself". It reads the file rather than a copy of these items, so
editing this file is how you steer it. It does not modify the repository.

**How to apply:** work through these at the next session and delete each one as it closes;
delete the file when all are done, and turn the routine off at the link above.
