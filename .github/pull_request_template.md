## What changed

<!-- One or two sentences. Which chart, and why. -->

## Checklist

- [ ] `version` in `Chart.yaml` bumped for **every** touched chart — without it, the release workflow skips the chart and the change never ships
- [ ] `appVersion` updated if, and only if, the packaged upstream version changed
- [ ] `values.yaml` comments updated and `helm-docs` re-run (see `CONTRIBUTING.md`)
- [ ] `ct lint --config ct.yaml --all` passes locally
- [ ] Breaking changes to values are called out above and in the chart's `Chart.yaml` description
