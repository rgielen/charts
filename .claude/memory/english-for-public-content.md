---
name: english-for-public-content
description: Documentation and anything publicly visible in this repo is written in English, even though the user converses in German
metadata:
  type: feedback
---

Standing instruction from the user (2026-09-01): **documentation and publicly visible
content in this repository are written in English.** The user's own working language in
these sessions is German; that does not carry over into the artefacts.

**Why:** this repo is public and its output is consumed by strangers — the chart
`README.md` files land in the repository index and on chart pages, the release notes are
generated from commits, and the GHCR package description is world-readable. The sister
GitOps repos `k3s-nuc` and `k3s-ze` are private infrastructure and keep German
`README.adoc` files; that convention deliberately does **not** apply here, so do not
copy it over when porting anything from them.

**How to apply:** English for `README.md`, `CONTRIBUTING.md`, `CLAUDE.md`, chart
`Chart.yaml` descriptions, every comment in `values.yaml` (those become the published
docs via helm-docs), commit messages, PR and issue text, and workflow comments. German
stays in the conversation. When in doubt, ask whether the text ends up somewhere a
stranger can read it — if yes, English.
