---
name: local-chart-toolchain-missing
description: crane, helm-docs and ct are not installed on this workstation; fetch the CI-pinned versions into the scratchpad, and ct needs three extras to run from its tarball
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

What works, without installing anything system-wide (versions as of 2026-09-06; take them
from CI, so that a local pass means the same thing as a CI pass):

```bash
SP=<scratchpad>; mkdir -p "$SP/bin"
curl -sSfL https://github.com/google/go-containerregistry/releases/download/v0.22.1/go-containerregistry_Linux_x86_64.tar.gz | tar -xz -C "$SP/bin" crane
curl -sSfL https://github.com/norwoodj/helm-docs/releases/download/v1.14.2/helm-docs_1.14.2_Linux_x86_64.tar.gz | tar -xz -C "$SP/bin" helm-docs

# ct runs fine from its own tarball -- no container needed -- but it needs three things
# the release does not carry: yamale and yamllint on PATH, and the two config files it
# would otherwise look for under /etc/ct/. They are in the tarball's own etc/.
curl -sSfL https://github.com/helm/chart-testing/releases/download/v3.14.0/chart-testing_3.14.0_linux_amd64.tar.gz | tar -xz -C "$SP"
python3 -m venv "$SP/venv" && "$SP/venv/bin/pip" -q install yamale==6.0.0 yamllint==1.33.0

export PATH="$SP:$SP/bin:$SP/venv/bin:$PATH"
ct lint --config ct.yaml --all \
  --chart-yaml-schema "$SP/etc/chart_schema.yaml" --lint-conf "$SP/etc/lintconf.yaml"
```

The pins live in `.github/workflows/upstream-sync.yaml` (`CRANE_VERSION`),
`.github/actions/helm-docs/action.yml` (`HELM_DOCS_VERSION`), and the `version`,
`yamale_version` and `yamllint_version` defaults of the `helm/chart-testing-action`
release that `lint-test.yaml` uses. Note that `ct lint --all` prints
`Version increment checking disabled` — `--all` turns that check off, so it never catches
the missing bump described at the top of `CLAUDE.md`.

**Why:** every one of these silently degrades rather than stopping. A `crane`-less audit
answers "nothing unmodelled" for a chart it never compared, which is exactly the answer
[[analyze-upstream-skill]] must never give wrongly.

**How to apply:** before running `/analyze-upstream` or the local checks here, put the
pinned binaries in the scratchpad and on `PATH`. Keep them out of the repo. See
[[open-followups]] if installing them properly ever becomes worthwhile.
