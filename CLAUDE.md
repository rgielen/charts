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
.helm-docs.gotmpl       the shared README skeleton; calls two per-chart hooks
renovate.json           dependency updates for chart deps, images, and workflow actions
.github/workflows/      lint-test.yaml (PR + workflow_call), release.yaml (main),
                        upstream-sync.yaml (nightly image watch)
.github/actions/        helm-docs (pinned install + regeneration)
.github/scripts/        regenerate-readmes.sh, upstream_sync.py
```

Chart `README.md` files are **generated**. Edit the comments in `values.yaml`, the chart's
own `README.md.gotmpl`, or the shared `.helm-docs.gotmpl` — never the README itself. CI
regenerates them and fails on a diff.

**Every chart must ship a `README.md.gotmpl`** defining `chart.aboutSection` and
`chart.usageSection`. helm-docs concatenates all `--template-files` entries and appends its
own built-in template as soon as one of them is missing for a chart, so a chart without the
file renders a README with every section twice. `.github/scripts/regenerate-readmes.sh`
fails on a missing file rather than let that reach a diff.

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
.github/scripts/regenerate-readmes.sh          # same script CI runs
```

**The shared template path must be absolute.** `--template-files` is documented as relative
to each chart directory, but helm-docs (1.14.2) refuses to resolve a path containing `..`:
it logs `Did not find template file` and appends its built-in template instead, exiting 0.
Run the script from the repository root; it builds the absolute path itself.

`ct install` gets its backing services from `charts/<name>/ci/fixtures/`, which
`lint-test.yaml` applies to the kind cluster beforehand and waits on via the
`charts.rgielen.de/ci-fixture: "true"` label. Fixtures live in a fixed namespace and are
addressed by cluster FQDN, because `ct` installs each release into a random namespace.

## Auditing a chart against its upstream

`/analyze-upstream` is the interactive companion to the CI drift check: it answers whether
an upstream change alters what the chart must model, and applies accepted edits up to a
lint-clean working tree — never a commit, push or release. It runs
`.github/scripts/chart_audit.py` (chart claims versus what the upstream reads, plus the
image assumptions the templates depend on) and `upstream_diff.py` before judging anything.

The skill lives in `.claude/skills/analyze-upstream/`, with its calibration reference
beside it. Cloud sessions and `claude-code-action` load project skills from the repository,
so the same skill is meant to serve CI in `--report-only` mode — see issue #26.

## Dependency updates that touch a chart

Renovate cannot raise a chart's own `version:`, so `renovate-chart-bump.yaml` adds it —
twice a day, onto the dependency pull request's own branch, along with the regenerated
README — then runs `lint-test.yaml` through `workflow_call` against that branch, because
its own push used `GITHUB_TOKEN` and does not re-trigger the pull request's checks. It does
not merge: whether the new version suits the chart is a judgement call.

## Upstream image tracking

A chart whose `appVersion` follows a container image carries four `Chart.yaml`
annotations (`charts.rgielen.de/upstream-image`, `-tag-pattern`, `-releases`,
`-watch-paths`). `upstream-sync.yaml` watches the image nightly, bumps `appVersion` **and**
`version` together, regenerates the README, opens a pull request, and merges it only when
the bump is not a major one **and** the drift check is clean. That coupled bump is
precisely what Renovate cannot do, which is why `renovate.json` still forbids automerge for
image updates.

The drift check (`.github/scripts/upstream_diff.py`) resolves both image tags to upstream
commits through `org.opencontainers.image.revision` — release notes are not usable here,
the upstream publishes image tags with no matching GitHub release — and diffs the
`-watch-paths` files between them. Everything it cannot determine is `review`, which holds
the pull request with the diff in its body. It never decides whether a change *matters*.

The workflow verifies its own pull request by *calling* `lint-test.yaml` through
`workflow_call` rather than waiting for it: a pull request opened with `GITHUB_TOKEN` never
triggers `pull_request` workflows, so waiting would wait forever. This keeps one
implementation of lint and install, and needs no personal access token.

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
- A new chart starts at `version: 1.0.0`. A `0.x` chart tells consumers the values
  interface may move at any time, which defeats the pinned `targetRevision` those
  consumers rely on.
- Every key in `values.yaml` carries a comment; that comment is the published
  documentation.
- Prefer `values.schema.json` for anything with a constrained shape — it turns a typo in
  a consumer's values into an install-time error instead of a broken template.
- Test scenarios go in `charts/<name>/ci/*-values.yaml`; each file is a separate
  `ct install` run against kind.
