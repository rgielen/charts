---
name: post-first-release-setup
description: "OPEN: publishing works over GitHub Pages and is verified; the ghcr.io package for manifest-llm-gateway 0.1.0 was never pushed and is still missing"
metadata:
  type: project
---

As of 2026-09-01 `rgielen/charts` has published its first chart. What is settled and what
is not:

**Done and verified.** `manifest-llm-gateway` 0.1.0 exists as a GitHub release, is listed
in `index.yaml` on `gh-pages`, and `helm repo add rgielen https://rgielen.github.io/charts`
→ `helm search repo` → `helm pull` works from a clean Helm config. Pages was already
enabled on branch `gh-pages` (`gh api repos/rgielen/charts/pages` reports
`status: built`), so the step this memory previously listed as open never needed doing by
hand.

**Correction to what this memory used to claim:** `helm/chart-releaser-action` does **not**
create the `gh-pages` branch. The very first release run failed with
`fatal: invalid reference: origin/gh-pages` and published nothing at all. The branch was
seeded manually as an orphan branch holding only `.nojekyll` and a README. Any future
chart repository built this way needs that branch to exist *before* the first release.

**Still open: the OCI package.** `oci://ghcr.io/rgielen/charts/manifest-llm-gateway` does
not exist — the push step of `release.yaml` had a bug (it treated
chart-releaser's `changed_charts` output, which is a list of chart *paths*, as bare names)
and failed on that first run. Fixed in `0d58132`, but the fix cannot retroactively publish
0.1.0: with `skip_existing`, a re-run reports no changed charts and the push step is
skipped. So 0.1.0 is currently reachable over GitHub Pages only, contradicting the promise
in `README.md` that both targets carry identical content.

**Decided:** 0.1.0 stays Pages-only and is treated as a pre-release. The chart was bumped
to 1.0.0 straight away, and that release populates both targets. See
[[charts-start-at-1-0-0]] — new charts start at 1.0.0 from now on, so this gap is a
one-off from the very first release and needs no note in the README.

**And after the first successful push:** a GHCR package is **private** on creation, and
visibility cannot be set before the package exists. Until it is flipped to public in the
package settings on github.com, `helm pull oci://...` returns 403 for everyone, including
CI in `k3s-nuc` and `k3s-ze`.

**How to apply:** once OCI is populated and public, verify with a `helm pull` from a clean
config and then delete this memory. See [[commit-memory-with-the-work]].
