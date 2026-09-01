---
name: post-first-release-setup
description: "OPEN: two one-time settings outside the repo are still unconfigured and only become possible after the first chart release"
metadata:
  type: project
---

As of 2026-09-01 the repository is a scaffold: CI, docs and config are committed, but
`charts/` is empty, no release has ever run, and **two pieces of one-time setup are
still open.** Neither can be done in advance — both need artefacts that only the first
release creates. Until then the publishing side of this repo is untested.

**1. GitHub Pages must be switched to branch `gh-pages`.**
`helm/chart-releaser-action` creates that branch on the first successful release. Only
after it exists:

```sh
gh api -X POST repos/rgielen/charts/pages -f "source[branch]=gh-pages" -f "source[path]=/"
```

Without it, `helm repo add rgielen https://rgielen.github.io/charts` returns 404 even
though the release run was green and `index.yaml` is sitting on the branch.

**2. The GHCR package must be made public.**
A package pushed to `ghcr.io` for the first time is **private**, and package visibility
is not settable before the package exists. Until it is flipped,
`helm pull oci://ghcr.io/rgielen/charts/<chart>` fails with a 403 for everyone —
including CI in `k3s-nuc` and `k3s-ze`. There is no API-only path with the current `gh`
token scopes; do it in the package settings on github.com, or ask the user to.

**How to apply:** after the very first chart is merged to `main`, watch the release run,
then do both steps and verify with a `helm repo add` and a `helm pull` from a clean
machine before pointing any cluster at this repo. Once both are done and verified, this
memory should be replaced by a short note that publishing works, or deleted.
