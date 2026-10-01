---
name: open-followups
description: "OPEN: the inotify limits on the workstation, and the drift check still blind to settings read only in code (2026-10-01)"
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

**A scheduled routine checks this file.** `rgielen/charts — open follow-ups`
(`trig_01GGA4bUnenMByUoaKa6TeYF`, Mondays 07:00 UTC,
<https://claude.ai/code/routines/trig_01GGA4bUnenMByUoaKa6TeYF>) reads this file, verifies
what is verifiable from a cloud sandbox — item 2 above, essentially — and reports the rest
as "you have to run this yourself". It reads the file rather than a copy of these items, so
editing this file is how you steer it. It does not modify the repository.

**How to apply:** work through these at the next session and delete each one as it closes;
delete the file when all are done, and turn the routine off at the link above.
