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

The rule matched from day one but merged nothing: Renovate hands an automerged pull
request to GitHub's auto-merge by default, and that is unusable in `k3s-nuc` — the
repository setting is off, and GitHub only offers auto-merge for a pull request *blocked*
by a required check or review, of which that repository has none. `platformAutomerge: false`
(rgielen/k3s-nuc#97) makes Renovate merge through the API itself. Until that lands, a
published bump still waits for a human there.

**How to apply:** a non-major chart version published here now reaches a running
single-node cluster without anyone reading the pull request. With `selfHeal` that is
an immediate rollout, so a change that restarts the pod is a short unattended outage
there — the same reason [[never-generate-secrets-in-charts]] matters. Anything whose
blast radius needs a human decision belongs in a **major** bump, not in a minor one
with a warning in the release notes.
