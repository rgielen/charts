---
name: commit-memory-with-the-work
description: Always commit and push .claude/memory changes together with the work they describe; never leave memory uncommitted
metadata:
  type: feedback
---

Standing instruction from the user (2026-09-01): memory for this project is kept
**at project level and tracked in Git** — every change under `.claude/memory/` gets
committed and pushed in the same session that made it, not left in the working tree.

**Why:** this project's memory deliberately lives *in the repo* rather than under
`~/.claude/`, so that it is versioned and travels to other workstations (the mechanics
are in `.claude/memory/README.md`). That only works if it is actually committed. Memory
left uncommitted is worse than no memory: it exists on one machine, is invisible
elsewhere, and is silently lost when that checkout is replaced. The same instruction is
in force in the sister repos `k3s-nuc` and `k3s-ze`.

**How to apply:** when finishing a piece of work, check `git status` for
`.claude/memory/` before declaring done. Either fold the memory files into the commit
that carries the work, or give them their own `docs:` commit. Then push. Before
reporting a clean finish, verify with `git ls-files .claude/memory` against the
directory listing that nothing is untracked.

Note the path trap: a `cd` into the memory directory makes `git add .claude/memory` fail,
because the path is then resolved relative to the memory directory itself. Run git from
the repository root.
