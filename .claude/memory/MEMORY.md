# Memory Index

- [English for public content](english-for-public-content.md) — docs, values comments, commits and PRs are English; the conversation stays German
- [OPEN: post-first-release setup](post-first-release-setup.md) — Pages on `gh-pages` and GHCR package visibility, both only possible after the first release
- [Commit the memory with the work](commit-memory-with-the-work.md) — memory changes are always committed and pushed in the same session; uncommitted memory is worse than none
- [helm-docs concatenates templates](helm-docs-template-concatenation.md) — a missing README.md.gotmpl silently duplicates every section, so each chart needs one
- [GITHUB_TOKEN triggers no workflows](github-token-does-not-trigger-workflows.md) — upstream-sync calls lint-test via workflow_call instead of waiting for checks
- [Never generate secrets in charts](never-generate-secrets-in-charts.md) — ArgoCD renders without `lookup`, and a rotated encryption key means data loss
