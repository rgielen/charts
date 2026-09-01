# Contributing

## Adding a chart

```bash
helm create charts/<name>
```

Then strip what you do not need and fill in `Chart.yaml`:

```yaml
apiVersion: v2
name: <name>
description: One sentence, shown in the repository index and on the chart page.
type: application
version: 1.0.0        # the chart's own version -- charts start at 1.0.0 here
appVersion: "1.2.3"   # the packaged upstream version, quoted
maintainers:
  - name: rgielen
    url: https://github.com/rgielen
sources:
  - https://github.com/rgielen/charts
```

Expected layout per chart:

```
charts/<name>/
├── Chart.yaml
├── values.yaml           # every key commented -- the comments are the documentation
├── values.schema.json    # optional, but it turns typos into errors at install time
├── templates/
├── README.md.gotmpl      # required -- the chart's own prose, see below
├── README.md             # generated, never edited by hand
└── ci/
    ├── default-values.yaml   # one file per scenario the install test should cover
    └── fixtures/             # optional, applied to the cluster before ct install
```

Anything under `ci/` is picked up by `ct install`: each `*-values.yaml` there becomes a
separate install against a throwaway kind cluster. A chart with no `ci/` directory is
installed once with its defaults.

### `README.md.gotmpl` is mandatory

The shared `.helm-docs.gotmpl` provides the skeleton and calls two hooks the chart has to
define — even if one of them is left empty:

```gotemplate
{{ define "chart.aboutSection" }}
What this packages, and how it differs from the upstream deployment.
{{ end }}

{{ define "chart.usageSection" }}
Setup, secrets, upgrades -- whatever the values table cannot say.
{{ end }}
```

This is not optional styling. helm-docs concatenates every `--template-files` entry and
appends its own built-in template as soon as one of them is missing for a chart, so a chart
without `README.md.gotmpl` gets a README containing every section twice. The
`helm-docs` composite action fails the build rather than let that reach a diff.

### `ci/fixtures/`

A chart that needs a backing service to come up — a database, say — ships throwaway
manifests here. `lint-test.yaml` applies them before `ct install` and waits for every
Deployment labelled `charts.rgielen.de/ci-fixture: "true"` to report Available. Put them in
a fixed namespace and address them from `ci/*-values.yaml` by their cluster FQDN: `ct`
installs each release into a random namespace of its own.

### Tracking an upstream image

A chart whose `appVersion` follows a container image opts into automatic updates with three
annotations in `Chart.yaml`:

```yaml
annotations:
  charts.rgielen.de/upstream-image: docker.io/example/app
  charts.rgielen.de/upstream-tag-pattern: '^[0-9]+\.[0-9]+\.[0-9]+$'
  charts.rgielen.de/upstream-releases: https://github.com/example/app/releases/tag/v{version}
```

A fourth annotation opts the chart into the drift check:

```yaml
  charts.rgielen.de/upstream-watch-paths: docker/.env.example,docker/docker-compose.yml
```

`.github/workflows/upstream-sync.yaml` then watches the image nightly and opens a pull
request that bumps `appVersion` and the chart `version` together, regenerates the README,
runs the full lint and install suite, and merges itself — but only when the upstream bump
is not a major one **and** the drift check came back clean. The tag pattern keeps `latest`,
floating majors and cosign `*.sig` tags out of the version comparison.

### The drift check

An image bump is only safe to merge unattended if the settings the chart models did not
move underneath it, and release notes are not a reliable way to find out: this upstream
publishes image tags with no matching GitHub release at all. Every image does carry
`org.opencontainers.image.revision`, the commit it was built from, so
`.github/scripts/upstream_diff.py` resolves both versions to commits and compares the
watched files between them, plus any newly added migration file.

It answers *did anything change*, not *does it matter* — a changed default reads the same
as a new variable, because deciding which of those matters is a person's job. Anything it
cannot determine is `review`, never `clean`: a check that says clean when it could not look
is worse than no check.

A `review` verdict labels the pull request `upstream-review`, puts the diff in its body,
and leaves it open. Merging it is the act of confirming the chart still matches upstream.
Put the paths that actually define the configuration surface in the annotation — for
`manifest-llm-gateway` that includes the backend's own `app.config.ts`, which is
authoritative in a way that neither `.env.example` is.

## Before opening a pull request

```bash
# Lint everything (drop --all to check only what changed against main)
ct lint --config ct.yaml --all

# Render templates to eyeball the output
helm template charts/<name>

# Regenerate the chart READMEs -- CI fails if these are stale.
# Run from the repository root; this is the same script CI uses.
.github/scripts/regenerate-readmes.sh
```

`ct` and `helm-docs` come from
[chart-testing](https://github.com/helm/chart-testing) and
[helm-docs](https://github.com/norwoodj/helm-docs); on macOS and Linux both are in
Homebrew (`brew install chart-testing norwoodj/tap/helm-docs`).

## Bump the version

Every pull request that touches a chart must raise that chart's `version` in
`Chart.yaml`. "Touches" means any file under `charts/<name>/`, including `ci/` — `ct`
does not care that `.helmignore` keeps those out of the package, so a fixture bump costs
a patch version too. `ct lint` enforces it in CI, and for good reason: the release workflow
packages all charts but only publishes versions that do not exist yet. A chart edited
without a bump passes through the release job without an error and simply never ships.

**Charts in this repository start at `1.0.0`, not `0.1.0`.** A `0.x` version tells
consumers the values interface may move under them at any time, which is the opposite of
what a pinned `targetRevision` in ArgoCD is for. A chart is either fit to install or it is
not published; if the interface later has to break, that is what a major bump is for.

Use the change to pick the increment:

| Change | Increment |
| ------ | --------- |
| Bug fix, template tweak, doc-only change | patch |
| New value, new optional resource, backwards-compatible default change | minor |
| Removed or renamed value, changed resource names, anything requiring user action | major |

For a major bump, describe the required action in the pull request body — it ends up in
the release notes.

## Releasing

There is no manual release step. Merging to `main` runs the release workflow, which:

1. packages every chart under `charts/`,
2. creates a GitHub release for each version that does not exist yet, and updates
   `index.yaml` on the `gh-pages` branch,
3. pushes those same packages to `oci://ghcr.io/rgielen/charts`.
