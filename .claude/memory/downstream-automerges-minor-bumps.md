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

**Confirmed working since 2026-09-14 11:59Z**, after two wrong theories. The rule matches — Renovate writes "Automerge:
Enabled" on our chart's pull requests and "Disabled by config" on every other — but no bump
has been merged unattended yet. `platformAutomerge: false` (rgielen/k3s-nuc#97, live since
2026-09-12 07:49Z) was the first theory: GitHub's auto-merge is unusable there, since the
repository setting is off *and* GitHub only offers it for a pull request blocked by a
required check or review, of which that repository has none. It was not enough. On #96
Renovate then ran three times with that config live (07:49, 08:31, 13:57) and force-pushed a
rebase of the branch each time without ever merging; the version reached the cluster because
a human merged it at 14:17.

**Cause found, measured on #103 (2026-09-14):** Renovate refuses to automerge a branch whose
status is not green, and GitHub's combined status API answers `pending` — not `success` —
for a commit with **no checks at all**, which is every commit in a repository without CI:

    GET /repos/rgielen/k3s-nuc/commits/<sha>/status
    {"state": "pending", "total_count": 0, "statuses": []}

The pull request waits on a condition that cannot occur, and nothing about it looks wrong.
`ignoreTests: true` on the automerge rule is the fix (rgielen/k3s-nuc#105). Proven 55
seconds after that merge: Renovate force-pushed a rebase of #103 onto the new `main` and
merged it **in the same run**, unattended. That also retires the rebase-treadmill theory
twice over — it never deferred a merge to a later run at all.

This is the general trap, not a local quirk — **any** repository with no checks at all
cannot satisfy Renovate's green-status requirement, so automerge there needs `ignoreTests`
regardless of how the rule is written.

**How to apply:** a non-major chart version published here now reaches a running
single-node cluster without anyone reading the pull request. With `selfHeal` that is
an immediate rollout, so a change that restarts the pod is a short unattended outage
there — the same reason [[never-generate-secrets-in-charts]] matters. Anything whose
blast radius needs a human decision belongs in a **major** bump, not in a minor one
with a warning in the release notes.
