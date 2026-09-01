---
name: upstream-drift-layer-2-planned
description: The Claude-review half of the upstream drift check is designed but not built; the full implementation plan is issue #26
metadata:
  type: project
---

The upstream drift check in `rgielen/charts` has two layers. **Layer 1 is built and
released** (PR #20): `upstream_diff.py` resolves both image tags to upstream commits via
`org.opencontainers.image.revision` and diffs the files named in
`charts.rgielen.de/upstream-watch-paths`. Auto-merge of an upstream bump requires a
non-major bump *and* a `clean` verdict.

**Layer 2 is designed and deliberately not built yet**: a Claude review of what a held diff
*means* for the chart, as opposed to whether anything changed. The complete plan —
verified action inputs, the escalate-only gate rule, the curated context, the output
schema, acceptance criteria, and the dry-run recipe — is
**<https://github.com/rgielen/charts/issues/26>**. Read that issue before touching this;
it is written to be picked up cold.

The two constraints that shape it, so they are not re-litigated:

- **The model may only escalate, never release a hold.** Layer 1 is the safety floor. The
  input is an upstream diff, i.e. untrusted content, so a model that could lift a hold
  would be a prompt-injection target with a merge behind it.
- **Layer 1 first, alone, on purpose.** Whether layer 2 earns its keep depends on how often
  layer 1 alone holds a real pull request, and that record did not exist yet on
  2026-09-01.

**Why:** the case that motivated all of it is concrete — between 6.18.0 and 6.19.1 the
upstream lowered `DB_POOL_MAX` 30 → 10 and `AUTH_DB_POOL_MAX` 10 → 5, values this chart
pins, with no variable added or removed for a name-level diff to notice.

**How to apply:** do not start building from this file. Open issue #26. If layer 1 has
never held a real pull request, say so before building anything. See
[[manifest-migration-paths]] for the upstream facts the review has to calibrate against.
