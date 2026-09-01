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
version: 0.1.0        # the chart's own version
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
├── README.md             # generated, never edited by hand
└── ci/
    └── default-values.yaml   # one file per scenario the install test should cover
```

Anything under `ci/` is picked up by `ct install`: each `*-values.yaml` there becomes a
separate install against a throwaway kind cluster. A chart with no `ci/` directory is
installed once with its defaults.

## Before opening a pull request

```bash
# Lint everything (drop --all to check only what changed against main)
ct lint --config ct.yaml --all

# Render templates to eyeball the output
helm template charts/<name>

# Regenerate the chart READMEs -- CI fails if these are stale.
# Run from the repository root; the template path must be absolute (see CLAUDE.md).
helm-docs --chart-search-root=charts --template-files="$PWD/.helm-docs.gotmpl"
```

`ct` and `helm-docs` come from
[chart-testing](https://github.com/helm/chart-testing) and
[helm-docs](https://github.com/norwoodj/helm-docs); on macOS and Linux both are in
Homebrew (`brew install chart-testing norwoodj/tap/helm-docs`).

## Bump the version

Every pull request that touches a chart must raise that chart's `version` in
`Chart.yaml`. `ct lint` enforces it in CI, and for good reason: the release workflow
packages all charts but only publishes versions that do not exist yet. A chart edited
without a bump passes through the release job without an error and simply never ships.

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
