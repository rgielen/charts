# Memory Index

- [English for public content](english-for-public-content.md) — docs, values comments, commits and PRs are English; the conversation stays German
- [Publishing is verified](publishing-is-verified.md) — both targets work; chart-releaser does not create `gh-pages`, and the GHCR package was public right away
- [Commit the memory with the work](commit-memory-with-the-work.md) — memory changes are always committed and pushed in the same session; uncommitted memory is worse than none
- [helm-docs concatenates templates](helm-docs-template-concatenation.md) — a missing README.md.gotmpl silently duplicates every section, so each chart needs one
- [GITHUB_TOKEN triggers no workflows](github-token-does-not-trigger-workflows.md) — upstream-sync calls lint-test via workflow_call instead of waiting for checks
- [Never generate secrets in charts](never-generate-secrets-in-charts.md) — ArgoCD renders without `lookup`, and a rotated encryption key means data loss
- [Charts start at 1.0.0](charts-start-at-1-0-0.md) — no 0.x phase; a pinned targetRevision deserves a stable values interface
