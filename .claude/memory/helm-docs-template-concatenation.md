---
name: helm-docs-template-concatenation
description: helm-docs concatenates all --template-files and appends its built-in template when one is missing, so every chart needs a README.md.gotmpl
metadata:
  type: project
---

helm-docs (verified in 1.14.2, `pkg/document/template.go:402-441`) concatenates the
contents of every `--template-files` entry into one template, and sets a
`templateNotFound` flag as soon as *one* listed file is missing for a chart — in which
case it appends its own built-in template to that concatenation. The chart's README then
contains every section twice, and helm-docs still exits 0.

`rgielen/charts` invokes it with two entries: the absolute shared `.helm-docs.gotmpl` and
the bare basename `README.md.gotmpl`, which helm-docs resolves per chart directory. That
is why **every** chart must ship a `README.md.gotmpl`, even a nearly empty one.
`.github/scripts/regenerate-readmes.sh` refuses to run when one is missing, because the
alternative is a duplicated README that only shows up in a diff.

**Why:** the failure mode is silent success — the same class of trap as the absolute-path
requirement already documented in `CLAUDE.md`.

**How to apply:** when adding a chart, create `README.md.gotmpl` with
`{{ define "chart.aboutSection" }}` and `{{ define "chart.usageSection" }}` before running
the generator. Never give the shared file no-op defaults for those hooks — an undefined
template fails loudly, a silently-empty one does not. See
[[english-for-public-content]] for the language these sections are written in.
