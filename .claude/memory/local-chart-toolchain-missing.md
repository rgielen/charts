---
name: local-chart-toolchain-missing
description: crane, helm-docs and ct are not installed on this workstation; fetch the CI-pinned versions into the scratchpad and run ct through its container
metadata:
  type: project
---

Only `helm` is on `PATH` here. Three tools the local checks in `CLAUDE.md` and the
`/analyze-upstream` skill assume are missing, and each fails in a way that looks like a
different problem:

- **`crane`** — `upstream_diff.py`, `chart_audit.py` and `upstream_sync.py` all shell out
  to it. Without it every one of them reports `verdict: review` with
  `could not read the image config`, which is indistinguishable from a real upstream
  problem. `chart_audit.py --skip-image` does **not** avoid it: the flag skips the layer
  download, not the config read, so the run still comes back with an empty `upstream` map
  and a misleading `upstream_unmodelled: []`.
- **`helm-docs`** — `regenerate-readmes.sh` exits with `command not found`.
- **`ct`** — not installed at all.

What works, without installing anything system-wide:

```bash
SP=<scratchpad>/bin; mkdir -p "$SP"
curl -sSfL https://github.com/google/go-containerregistry/releases/download/v0.22.0/go-containerregistry_Linux_x86_64.tar.gz | tar -xz -C "$SP" crane
curl -sSfL https://github.com/norwoodj/helm-docs/releases/download/v1.14.2/helm-docs_1.14.2_Linux_x86_64.tar.gz | tar -xz -C "$SP" helm-docs
export PATH="$SP:$PATH"

# ct has no single-binary release worth chasing; the image carries yamllint and yamale too
docker run --rm -v "$(pwd)":/work -w /work quay.io/helmpack/chart-testing:v3.12.0 \
  ct lint --config ct.yaml --all
```

Take the versions from CI so a local pass means the same thing as a CI pass:
`CRANE_VERSION` and `HELM_DOCS_VERSION` in `.github/workflows/upstream-sync.yaml` and
`.github/actions/helm-docs/action.yml`, and the chart-testing version behind
`helm/chart-testing-action`. Note that `ct lint --all` prints
`Version increment checking disabled` — `--all` turns that check off, so it never catches
the missing bump described at the top of `CLAUDE.md`.

**Why:** every one of these silently degrades rather than stopping. A `crane`-less audit
answers "nothing unmodelled" for a chart it never compared, which is exactly the answer
[[analyze-upstream-skill]] must never give wrongly.

**How to apply:** before running `/analyze-upstream` or the local checks here, put the
pinned `crane` and `helm-docs` in the scratchpad and on `PATH`, and reach for the
chart-testing container for `ct`. Keep them out of the repo. See [[open-followups]] if
installing them properly ever becomes worthwhile.
