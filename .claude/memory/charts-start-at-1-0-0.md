---
name: charts-start-at-1-0-0
description: New charts in rgielen/charts start at version 1.0.0, never 0.x
metadata:
  type: feedback
---

Every new chart in `rgielen/charts` starts at `version: 1.0.0`. No `0.x` phase.

Decided on 2026-09-01, when `manifest-llm-gateway` was released as `0.1.0` and then
immediately bumped to `1.0.0`. The `0.1.0` release stays where it is and is treated as a
pre-release; it is deliberately the one version that exists on GitHub Pages but not in the
OCI registry, and that gap needs no explaining away in the README.

**Why:** the consumers are `k3s-nuc` and `k3s-ze` via ArgoCD with a pinned
`targetRevision`. A `0.x` version tells them the values interface may move at any time,
which is exactly what pinning is meant to protect against. A chart is either fit to install
or it is not published; if the interface later has to break, that is what a major bump is
for.

**How to apply:** `helm create` writes `0.1.0` — change it before the first commit.
`CONTRIBUTING.md` and `CLAUDE.md` both state the rule. The 0.x branch in
`bump_chart_version` in `.github/scripts/upstream_sync.py` is now only a guard and should
never be reached. See [[post-first-release-setup]].
