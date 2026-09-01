---
name: never-generate-secrets-in-charts
description: Charts here never generate secrets with randAlphaNum/lookup, because ArgoCD renders without cluster access and would regenerate them on every sync
metadata:
  type: project
---

No chart in `rgielen/charts` generates a secret value. The common Helm pattern
(`randAlphaNum` kept stable through `lookup`) depends on the renderer having cluster
access. ArgoCD renders with `helm template` and no cluster, where `lookup` returns nothing:
the value would differ on every sync.

For `manifest-llm-gateway` that is not a nuisance but data loss —
`MANIFEST_ENCRYPTION_KEY`, or `BETTER_AUTH_SECRET` which it falls back to, encrypts every
stored LLM provider API key and OAuth token at rest. A rotated key makes all of them
undecryptable.

Instead: `manifest.existingSecret` (keys named after the upstream environment variables,
mounted with `envFrom`) or plain values, and a `fail` in `_helpers.tpl` naming both ways
out when neither is set.

**Why:** the consumers of these charts are `k3s-nuc` and `k3s-ze` via ArgoCD, so the
ArgoCD rendering path is the *normal* path here, not an edge case.

**How to apply:** in any new chart, a secret with no safe default is a hard `fail` with a
message that names the two ways to supply it — never a generated default.
