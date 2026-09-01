# Agent memory (project-local)

This directory holds Claude Code's persistent memory for the `rgielen/charts`
project. It lives **in the repo** (instead of `~/.claude/...`) so it is committed
and travels to other workstations.

- `MEMORY.md` — the index (one line per memory), loaded into context each session.
- `*.md` files with YAML frontmatter — individual memories (one fact each).

The same convention is used in the sister GitOps repos `k3s-nuc` and `k3s-ze`.

## Enable auto-recall on a machine (one-time)

Claude Code stores per-project memory under
`~/.claude/projects/<PROJECT_KEY>/memory`. Point that at this folder so the
memory system reads and writes here:

```sh
# PROJECT_KEY = the Claude working directory with every '/' replaced by '-'.
PROJECT_KEY="-home-rene-DevHome-GitOps-charts"

mkdir -p "$HOME/.claude/projects/$PROJECT_KEY"
rm -rf "$HOME/.claude/projects/$PROJECT_KEY/memory"      # only if empty/relocating
ln -s "$(git rev-parse --show-toplevel)/.claude/memory" \
      "$HOME/.claude/projects/$PROJECT_KEY/memory"
```

Run it from within the cloned repo. Without the symlink these files are still
readable, they just are not surfaced automatically.

### One symlink per working directory

The project key is derived from the directory Claude is **started in**, so opening
the parent folder and opening the repo itself produce two different keys and two
separate memory folders. Link every directory you actually start Claude in —
otherwise a session in the unlinked one writes its memories to
`~/.claude/projects/<key>/memory` as a real folder, where they are neither
committed nor recalled later.

Keys relevant to this repo:

```sh
-home-rene-DevHome-GitOps-charts     # the repo itself (linked)
-home-rene-DevHome-GitOps            # parent folder, if Claude is started there
```

To check a machine: `ls -la ~/.claude/projects/*/memory` — every entry should be
a symlink (`l`), never a directory (`d`).
