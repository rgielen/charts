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
                        pages.yaml (the browsable gh-pages site, workflow_call),
                        upstream-sync.yaml (nightly image watch, drift check, review),
                        renovate-chart-bump.yaml, claude.yml (@claude, owner-gated)
.github/actions/        helm-docs (pinned install + regeneration)
.github/scripts/        regenerate-readmes.sh, upstream_sync.py, upstream_diff.py,
                        chart_audit.py, renovate_chart_bump.py, format_review_comment.py,
                        build_pages.py + requirements.txt (the only non-stdlib script)
.github/site/           style.css, copied verbatim onto gh-pages
.github/schemas/        upstream-review.json (the review's structured output)
.claude/skills/         analyze-upstream (/analyze-upstream, also run by CI)
.claude/plans/          design notes for work decided but not started yet
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

## The browsable site

`gh-pages` carries two things that never touch each other. `index.yaml` is for
`helm repo add` and belongs to chart-releaser. The pages beside it are for people, and
`.github/scripts/build_pages.py` renders every one of them: a landing page listing the
charts, and per chart its generated README, the versions actually published, and the
upstream image it tracks. `pages.yaml` is *called* by `release.yaml` after chart-releaser
has written the index — a site rendered before that is missing the version that just
shipped.

The site is derived, never edited. `index.yaml` is the truth about what is published, the
chart directory on `main` about what the current version documents; the generator reads
both and writes nothing else on the branch. That is the whole point — a hand-kept version
table is wrong the first time someone forgets it, which is why the root README has no
version column either.

The same workflow renders on pull requests with the push step skipped, and uploads the
result as the `site` artifact. That render *is* the check: nothing else here reads a chart's
`Chart.yaml` and generated README the way the generator does, so without it a broken
generator would first show up on `main`.

Three consequences worth knowing:

- **A chart page is a canary.** When `Chart.yaml`'s `version` is not among the published
  ones, the page says so in a banner instead of quietly documenting something nobody can
  install — the visible end of the silent-skip failure at the top of this file.
- **`build_pages.py` is the one script here that is not stdlib-only.** Rendering Markdown
  and reading `index.yaml` both want a real parser; the pins live in
  `.github/scripts/requirements.txt`, which Renovate reads without configuration.
- **A chart removed from `charts/` loses its page.** The generator deletes any directory
  holding a page it wrote for a chart that no longer exists — otherwise the branch keeps
  documenting something `main` no longer describes. Its published versions stay installable
  either way; they live in `index.yaml` and the GitHub releases, neither of which the
  generator touches.

## Local checks

```bash
ct lint --config ct.yaml --all                 # all charts; omit --all for changed only
helm template charts/<name>                    # render and inspect
.github/scripts/regenerate-readmes.sh          # same script CI runs

# Preview the gh-pages site. The index has to come from the branch -- it is the
# published history, and no part of it is derivable from the working tree.
git show origin/gh-pages:index.yaml > /tmp/index.yaml
python .github/scripts/build_pages.py --index /tmp/index.yaml --output /tmp/site
python -m http.server --directory /tmp/site 8000
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
beside it. `upstream-sync.yaml` runs the same skill in `--report-only` mode as its `review`
job, on pull requests the deterministic check already held.

That job can only add reasons to hold, and not because a rule says so: `merge` needs
`[detect, verify]` and gates on `verdict == 'clean'`, which only the deterministic check
produces. The review job is a leaf — nothing reads it but a comment and the
`upstream-impact` label. Keep it that way; wiring `review` into `merge`'s `needs` would
quietly turn a reporting tool into a gate.

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
