---
name: upstream-drift-layer-2-planned
description: Both layers of the upstream drift check are built; layer 2 invokes the /analyze-upstream skill, and escalate-only is a property of the job graph rather than a rule
metadata:
  type: project
---

The upstream drift check in `rgielen/charts` has two layers and **both are built** as of
2026-09-02 (issue #26 closed, PR #33).

**Layer 1** — `upstream_diff.py`: resolves both image tags to upstream commits via
`org.opencontainers.image.revision`, diffs the `upstream-watch-paths` files. Auto-merge
requires a non-major bump *and* a `clean` verdict.

**Layer 2** — the `review` job in `upstream-sync.yaml` invokes the `/analyze-upstream`
skill in `--report-only` mode through `claude-code-action`, on pull requests layer 1 held.
It posts a comment and, when it finds impact, the `upstream-impact` label.

**Escalate-only is a property of the job graph, not a rule anyone obeys.** `merge` needs
`[detect, verify]` and gates on `verdict == 'clean'`, which only the deterministic check
produces. `review` is a leaf: nothing reads it but a comment and a label. Wiring `review`
into `merge`'s `needs` is the single change that would turn a reporting tool into a gate.

Three things confirmed by the first real run, worth not re-deriving:

- **`claude-code-action` does invoke a repository skill** through `prompt: "/skill-name"`,
  with `disable-model-invocation` unset. This was the assumption the whole design rested on.
- **`--json-schema` takes the schema itself, not a path.** Given a path it fails with
  `Unexpected token '.'`. The workflow reads the file into a step output and passes it inline.
- **The failure path works**: with `continue-on-error`, a failed review posts a comment
  saying so and adds the hold label. Layer 1 already holds the pull request, so a broken
  token costs information, not a stuck queue.

**Why:** the drift worth catching is invisible to a file diff — a default the upstream
moved under a value the chart pins, a schema enum the upstream outgrew, a setting read
only in `app.config.ts`.

**How to apply:** the analysis lives once, in the skill ([[analyze-upstream-skill]]). Do
not add a second copy to the workflow. See [[manifest-migration-paths]] for the upstream
facts it calibrates against.
