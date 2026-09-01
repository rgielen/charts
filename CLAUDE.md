# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Helm chart monorepo published as `rgielen/charts`. Each chart under `charts/` is
versioned and released independently. There is no application build — the artefacts are
packaged charts, produced by CI, never by hand.

## The one rule that breaks everything

**Every change to a chart requires a bump of that chart's `version` in `Chart.yaml`.**

The release workflow packages all charts and then publishes only versions that do not
already exist. A chart edited without a bump produces a *green* release run that
publishes nothing — no error, no warning, and the change is simply absent from the
repository index. `ct lint` has `check-version-increment` on to catch this in the pull
request, but that check only runs on pull requests; a direct push to `main` bypasses it.

`version` and `appVersion` are independent and must not be moved in lockstep:

- `version` — the chart's own SemVer. Bumped for *any* change, including comments and
  default values.
- `appVersion` — the version of the packaged upstream software, quoted in YAML so
  `1.20` does not become the float `1.2`. Changing it is itself a chart change, so it
  always comes with a `version` bump too.

## Repository layout

```
charts/<name>/          one chart; Chart.yaml, values.yaml, templates/, ci/, README.md
ct.yaml                 chart-testing config (lint + install)
.helm-docs.gotmpl       the single template all chart READMEs are generated from
renovate.json           dependency updates for chart deps, images, and workflow actions
.github/workflows/      lint-test.yaml (PR), release.yaml (main)
```

Chart `README.md` files are **generated**. Edit the comments in `values.yaml` or the
shared `.helm-docs.gotmpl`, never the README itself — CI regenerates them and fails on a
diff.

## Publishing

Two targets, one release, identical content:

- **GitHub Pages** — `index.yaml` on the `gh-pages` branch, consumed as
  `helm repo add rgielen https://rgielen.github.io/charts`. Maintained by
  `helm/chart-releaser-action`.
- **OCI** — `oci://ghcr.io/rgielen/charts/<chart>`, pushed by a follow-up step in the
  same job, driven by the action's `changed_charts` output so unchanged charts are not
  re-pushed.

Both use the workflow's `GITHUB_TOKEN`; no repository secret is involved.

Two pieces of one-time setup live outside the repository and are easy to forget when
something appears broken:

- Pages must be configured to serve from branch `gh-pages` (`/`).
- A GHCR package is **private on first push**. Until its visibility is set to public,
  `helm pull oci://ghcr.io/rgielen/charts/<chart>` fails with a 403 for everyone,
  including CI in other repositories.

## Local checks

```bash
ct lint --config ct.yaml --all                 # all charts; omit --all for changed only
helm template charts/<name>                    # render and inspect
helm-docs --chart-search-root=charts --template-files="$PWD/.helm-docs.gotmpl"
```

**The template path must be absolute.** `--template-files` is documented as relative to
each chart directory, but helm-docs (1.14.2) refuses to resolve a path containing `..`:
it logs `Did not find template file`, falls back to its built-in template, and exits 0.
The result is a README that renders fine and is missing every custom section — a failure
that looks like success. In CI the path comes from `$GITHUB_WORKSPACE`; locally, run the
command from the repository root so `$PWD` is right.

## Consumers

`k3s-nuc` and `k3s-ze` (both `rgielen`) consume charts from here via ArgoCD. Their
convention is a pinned `targetRevision`, so a published version is effectively immutable:
never re-release a version with different content, always cut a new one. Both clusters
are single-node — a chart change that forces a pod restart is a real, if short, outage
there.

## Language

This repository is public: **all documentation and publicly visible content is written
in English** — READMEs, `values.yaml` comments (they become the published docs),
`Chart.yaml` descriptions, commit messages, PR and issue text. The user converses in
German, and the sister repos `k3s-nuc` / `k3s-ze` keep German `README.adoc` files
because they are private; neither carries over here.

## Agent memory

Project memory lives in `.claude/memory/` **inside this repo**, not under `~/.claude/`,
so it is versioned and travels between workstations. `MEMORY.md` there is the index;
`.claude/memory/README.md` explains the one-time symlink that enables auto-recall on a
new machine. Memory changes are committed and pushed together with the work that
prompted them — never left in the working tree.

## Conventions

- Chart `apiVersion: v2`, `type: application` unless it is a library chart.
- Every key in `values.yaml` carries a comment; that comment is the published
  documentation.
- Prefer `values.schema.json` for anything with a constrained shape — it turns a typo in
  a consumer's values into an install-time error instead of a broken template.
- Test scenarios go in `charts/<name>/ci/*-values.yaml`; each file is a separate
  `ct install` run against kind.
