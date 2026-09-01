#!/usr/bin/env bash
# Regenerate every chart README from the shared skeleton plus the chart's own
# README.md.gotmpl. Run from the repository root.
set -euo pipefail

# helm-docs concatenates every --template-files entry, and appends its own
# built-in template as soon as one listed file is missing for a chart -- which
# yields a README with every section twice. That is only visible in the diff, so
# the missing file is caught here instead.
missing=()
for chart in charts/*/Chart.yaml; do
  [ -e "$chart" ] || continue
  dir="$(dirname "$chart")"
  [ -f "$dir/README.md.gotmpl" ] || missing+=("$dir")
done
if [ ${#missing[@]} -gt 0 ]; then
  for dir in "${missing[@]}"; do
    echo "::error file=$dir/Chart.yaml::$dir has no README.md.gotmpl. Add one defining chart.aboutSection and chart.usageSection -- see CONTRIBUTING.md." >&2
  done
  exit 1
fi

# The shared template must be an absolute path: helm-docs resolves a relative
# --template-files below each chart directory and silently ignores a path
# containing "..". README.md.gotmpl is a bare basename on purpose -- that is
# exactly the per-chart resolution we want.
helm-docs \
  --chart-search-root=charts \
  --template-files="$(pwd)/.helm-docs.gotmpl" \
  --template-files=README.md.gotmpl
