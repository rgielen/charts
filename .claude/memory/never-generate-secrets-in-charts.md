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
stored LLM provider API key and OAuth token at rest. A key that changes without warning
makes all of them undecryptable, and the read paths report that as "provider not
connected" rather than as an error, so the damage is silent.

A *deliberate* rotation is a different thing and has been supported since upstream 6.21.0:
`manifest.auth.previousEncryptionKey` (`MANIFEST_ENCRYPTION_KEY_PREVIOUS`) keeps the old
key readable while a pass after boot rewrites every row onto the new one. That does not
soften this rule — it is the difference between an operator changing a key on purpose and
a renderer changing it behind their back. Generated values are still forbidden, and stored
recording bodies are not rewritten by that pass either.

Instead: `manifest.existingSecret` (keys named after the upstream environment variables,
mounted with `envFrom`) or plain values, and a `fail` in `_helpers.tpl` naming both ways
out when neither is set.

**Why:** the consumers of these charts are `k3s-nuc` and `k3s-ze` via ArgoCD, so the
ArgoCD rendering path is the *normal* path here, not an edge case.

**How to apply:** in any new chart, a secret with no safe default is a hard `fail` with a
message that names the two ways to supply it — never a generated default.
