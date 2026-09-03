---
name: hermes-webui-chart-deferred
description: "DEFERRED: a chart for nesquena/hermes-webui is analysed and decided but not built; the plan is in .claude/plans/hermes-webui.md, tracked in issue #41"
metadata:
  type: project
---

On 2026-09-03 the upstream <https://github.com/nesquena/hermes-webui> was analysed in full
for a chart of its own, three shaping decisions were taken, and the work was then
**deferred without a single file under `charts/`**. Everything needed to pick it up cold
lives in `.claude/plans/hermes-webui.md`; the tracker is
<https://github.com/rgielen/charts/issues/41>. The same plan as a rendered page, in German:
<https://claude.ai/code/artifact/997e5505-b8f5-47d5-9865-95aeb05ffd42>.

The three decisions, so they are not silently re-opened: **WebUI standalone** (the Hermes
Agent is a second upstream with its own versioning and a ~950 MB image, and is documented
rather than deployed), **stable channel only** (an image tag counts only when a matching
`v<version>` git tag exists), and **`/app` as an `emptyDir`** (the container installs its
dependencies at start, and a persistent `/app` would keep them across image upgrades).

Two findings are worth carrying even if the chart is never built, because they generalise
past this one upstream:

- **A registry tag pattern is not a channel.** hermes-webui tags `v*` and `exp-v*` upstream
  and `docker/metadata-action` maps both to a bare `X.Y.Z`. Today `latest`, `experimental`
  and `0.52.264` are one digest, built from `exp-v0.52.264` — so `latest` serves an
  experimental build. Any future chart whose upstream has two release channels needs the
  git-tag cross-check described in the plan, not just `-tag-pattern`.
- **Watch paths are the image contract, not the config surface.** A file that changes daily
  in `-watch-paths` makes every drift check a `review` and the automation pointless. The
  split — image contract in `-watch-paths`, what the app reads in `-config-sources` — is
  the general rule, see [[upstream-drift-layer-2-planned]].

**Why:** the analysis cost a full session and none of it is derivable from this repository,
because the subject lives entirely in someone else's repository and registry. Without this
note a later session starts by re-discovering the channel trap.

**How to apply:** read `.claude/plans/hermes-webui.md` before doing anything on this topic,
and start at its Phase 0 — the eight kind checks — rather than at the chart. Delete this
memory when the chart ships or when issue #41 is closed as wontfix. Related:
[[charts-start-at-1-0-0]], [[never-generate-secrets-in-charts]],
[[local-chart-toolchain-missing]], [[helm-docs-template-concatenation]].
