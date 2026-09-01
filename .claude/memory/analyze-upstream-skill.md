---
name: analyze-upstream-skill
description: /analyze-upstream is the interactive companion to the CI drift check, and is meant to become the implementation of CI layer 2 as well
metadata:
  type: project
---

`.claude/skills/analyze-upstream/` provides `/analyze-upstream`. The CI drift check
(`upstream_diff.py`, in `upstream-sync.yaml`) answers *did anything change* and holds a
pull request; the skill answers *does it change what the chart must model*, proposes
concrete edits, and applies the accepted ones — stopping at a lint-clean working tree,
never a commit, push or release.

It runs two deterministic scripts before judging: `upstream_diff.py` (the same one CI
uses) and `chart_audit.py` (chart claims versus what the upstream actually reads, plus the
image assumptions the templates depend on). `reference/calibration.md` beside the skill
holds the worked examples and the classification guidance.

**It is intended to be CI layer 2 as well**, invoked in `--report-only` mode: cloud
sessions and `claude-code-action` both load project skills from the repository, so one
analysis can serve both consumers instead of two implementations drifting apart. Issue #26
carries the plan. The escalate-only rule still lives in the *workflow*, not the skill: the
skill only reports, and the workflow decides what that report may do.

Two consequences worth remembering:

- `disable-model-invocation` is deliberately **not** set, because it also blocks routine
  invocation and might block the action. The trade is that Claude may load the skill
  unprompted; the description is written narrowly to limit that.
- The audit needs the mapping table to spell every environment variable out in full. The
  abbreviated `PREFIX_A, _B` form reads well and is not machine-checkable, so it was
  removed from `README.md.gotmpl` in 2.0.3.

**Why:** the drift worth catching is invisible to a file diff — a default the upstream
moved under a value the chart pins, a schema enum the upstream outgrew, a setting read
only in `app.config.ts`. See [[manifest-migration-paths]] for the upstream facts it
calibrates against.

**How to apply:** run `/analyze-upstream --audit` when touching this chart. Its first real
run found 21 upstream settings the chart models nowhere; most are cloud-only or
development-only, but `STREAM_IDLE_TIMEOUT_MS` and `BACKFILL_DATABASE_URL` were left as
open decisions rather than silently ignored.
