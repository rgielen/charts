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

**How to apply:** a non-major chart version published here now reaches a running
single-node cluster without anyone reading the pull request. With `selfHeal` that is
an immediate rollout, so a change that restarts the pod is a short unattended outage
there — the same reason [[never-generate-secrets-in-charts]] matters. Anything whose
blast radius needs a human decision belongs in a **major** bump, not in a minor one
with a warning in the release notes.
