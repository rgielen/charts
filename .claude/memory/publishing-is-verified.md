---
name: publishing-is-verified
description: Both publishing targets work and were verified end to end on 2026-09-01; records two beliefs about the setup that turned out to be wrong
metadata:
  type: project
---

Publishing from `rgielen/charts` works and was verified end to end on 2026-09-01 with
`manifest-llm-gateway` 1.0.0, from a clean Helm config with no credentials:

- `helm repo add rgielen https://rgielen.github.io/charts` → `helm search repo` →
  `helm pull` ✔
- `helm pull oci://ghcr.io/rgielen/charts/manifest-llm-gateway --version 1.0.0` ✔

This replaces the earlier `post-first-release-setup` memory, two of whose assumptions were
wrong:

1. **`helm/chart-releaser-action` does not create the `gh-pages` branch.** The first
   release run failed with `fatal: invalid reference: origin/gh-pages` and published
   nothing at all. The branch was seeded by hand as an orphan branch holding `.nojekyll`
   and a README. Any new chart repository built this way needs that branch to exist
   *before* the first release. GitHub Pages itself was already enabled and needed nothing.
2. **The GHCR package was public immediately, not private.** The widely repeated "a GHCR
   package is private on first push" does not apply here: the push comes from Actions with
   `GITHUB_TOKEN`, which links the package to this public repository and inherits its
   visibility. Verified with an anonymous `helm pull` and an unauthenticated
   `ghcr.io/token` request (HTTP 200).

`manifest-llm-gateway` 0.1.0 is marked as a pre-release on GitHub and exists on Pages only
— the OCI push step was broken on that run. Deliberate, see [[charts-start-at-1-0-0]].

**How to apply:** when a second chart is added, none of this needs redoing. If a *new*
chart repository is ever set up, seed `gh-pages` first.
