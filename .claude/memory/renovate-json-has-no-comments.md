---
name: renovate-json-has-no-comments
description: renovate.json rejects unknown keys, so explanatory prose goes in `description`, never a `_comment_*` key — an invalid key stops all Renovate PRs
metadata:
  type: project
---

Renovate validates `renovate.json` against its schema and rejects any key it does not
know. A `"_comment_..."` key — the usual JSON-comment workaround — is such a key: it
produces `Invalid configuration option: _comment_ignorePaths`, and Renovate then **stops
opening PRs entirely** until the config is fixed, announcing it in an "Action Required"
issue (that was issue #14, caused by PR #13 on 2026-09-01).

The supported field is `description` (string or array of strings). Renovate ignores its
content and it is schema-valid at the top level as well as inside a manager block or a
`packageRules` entry — which is how the rest of `renovate.json` already carries its prose.

**Why:** the whole config file is written in explaining-prose style, so the temptation to
add a comment next to a bare value like `ignorePaths` is constant, and the punishment is
not a warning but a full stop of dependency updates.

**How to apply:** any prose in `renovate.json` goes into a `description`. Validate before
pushing:

```bash
npx --yes --package renovate@latest renovate-config-validator renovate.json
```

Pin `@latest` — a stale npx cache can resolve an old major (37.x here) that does not know
`managerFilePatterns` and reports seven bogus errors. Verify the version it actually ran.
Not a chart change: `renovate.json` is in no package, so no `version:` bump.
See [[open-followups]] for the still-unconfirmed parts of the Renovate setup.
