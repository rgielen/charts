# rgielen Helm Charts

Helm charts maintained by [@rgielen](https://github.com/rgielen), published from this
repository on every merge to `main`. Each chart is versioned and released
independently.

Charts are consumed by the GitOps repositories
[`k3s-nuc`](https://github.com/rgielen/k3s-nuc) and
[`k3s-ze`](https://github.com/rgielen/k3s-ze), but nothing here is specific to those
clusters.

## Available charts

| Chart | Description | Version |
| ----- | ----------- | ------- |
| _none yet_ | | |

Every released version is also a [GitHub release](https://github.com/rgielen/charts/releases)
with the packaged `.tgz` attached.

## Installation

Charts are published two ways, from the same release. Both carry identical content —
pick whichever fits the consumer.

### Helm repository (GitHub Pages)

```bash
helm repo add rgielen https://rgielen.github.io/charts
helm repo update
helm search repo rgielen
helm install my-release rgielen/<chart> --version <version>
```

### OCI registry (ghcr.io)

```bash
helm install my-release oci://ghcr.io/rgielen/charts/<chart> --version <version>
```

## Use from ArgoCD

Always pin `targetRevision` to an explicit chart version — `*` or a floating range
turns an unrelated upstream release into an unreviewed change in your cluster.

<details>
<summary>Helm repository source</summary>

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: infrastructure
  source:
    repoURL: https://rgielen.github.io/charts
    chart: <chart>
    targetRevision: 0.1.0
    helm:
      valuesObject:
        replicaCount: 1
  destination:
    server: https://kubernetes.default.svc
    namespace: my-app
```

</details>

<details>
<summary>OCI source</summary>

```yaml
spec:
  source:
    repoURL: ghcr.io/rgielen/charts
    chart: <chart>
    targetRevision: 0.1.0
```

Note the missing `oci://` prefix: ArgoCD expects a bare host and path, and marks the
repository as OCI through `enableOCI` on the repository credentials.

</details>

## Versioning

Charts follow [semantic versioning](https://semver.org/), applied to the chart, not to
the software it packages:

- **`version`** — the chart's own version. Bumped on *every* change to the chart,
  including documentation and default values.
- **`appVersion`** — the version of the packaged upstream software. Changes only when
  that software changes, and never triggers a release on its own.

A change merged without a `version` bump is silently skipped by the release workflow.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE).
