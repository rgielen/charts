# rgielen Helm chart repository

This branch is machine-managed. It carries the repository index that
[`helm/chart-releaser-action`](https://github.com/helm/chart-releaser-action) writes, and the
browsable pages that
[`.github/scripts/build_pages.py`](https://github.com/rgielen/charts/blob/main/.github/scripts/build_pages.py)
renders from that index and the chart sources. Do not commit to it by hand — the next release
overwrites everything but `index.yaml`.

```bash
helm repo add rgielen https://rgielen.github.io/charts
helm repo update
helm search repo rgielen
```

Rendered: <https://rgielen.github.io/charts/>. Sources, documentation and issues live on
[`main`](https://github.com/rgielen/charts).
