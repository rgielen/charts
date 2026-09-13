---
name: downstream-automerges-minor-bumps
description: k3s-nuc automerges minor and patch bumps of charts from this repo; a non-major release now deploys unattended
metadata:
  type: project
---

Since 2026-09-06 (rgielen/k3s-nuc#83) the downstream cluster `k3s-nuc` automerges
Renovate bumps of charts from this repository for update type **minor and patch**;
major stays a manual merge. Matched by `matchSourceUrls`, so every chart here is
covered, not just `manifest-llm-gateway`. `k3s-ze` is unchanged.

**Why:** the review that matters already happens here — lint and install against
kind, the coupled appVersion/version bump, and the drift check holding a bump when
the upstream configuration surface moved. The remaining reason to merge by hand was
an unreadable release body, which `release_notes.py` fixed.

**OPEN: it has never actually merged one.** The rule matches — Renovate writes "Automerge:
Enabled" on our chart's pull requests and "Disabled by config" on every other — but no bump
has been merged unattended yet. `platformAutomerge: false` (rgielen/k3s-nuc#97, live since
2026-09-12 07:49Z) was the first theory: GitHub's auto-merge is unusable there, since the
repository setting is off *and* GitHub only offers it for a pull request blocked by a
required check or review, of which that repository has none. It was not enough. On #96
Renovate then ran three times with that config live (07:49, 08:31, 13:57) and force-pushed a
rebase of the branch each time without ever merging; the version reached the cluster because
a human merged it at 14:17.

Next theory to test, at the next bump: `rebaseWhen` from `config:recommended` resolves to
"rebase whenever the branch is behind base" for an automerge-enabled pull request, and
`main` there moves often. Renovate does not merge a branch in the same run in which it just
rewrote it, so every run rebases and defers — a treadmill that never reaches the merge. If
that is it, `rebaseWhen: "conflicted"` on the rule ends it: nothing gates these pull
requests, so being behind `main` costs nothing. Check first whether a run ever sees the
branch *not* behind.

**How to apply:** a non-major chart version published here now reaches a running
single-node cluster without anyone reading the pull request. With `selfHeal` that is
an immediate rollout, so a change that restarts the pod is a short unattended outage
there — the same reason [[never-generate-secrets-in-charts]] matters. Anything whose
blast radius needs a human decision belongs in a **major** bump, not in a minor one
with a warning in the release notes.
