#!/usr/bin/env python3
"""Render the GitHub release notes for one released chart version.

chart-releaser writes the chart's `description` into the release body and
nothing else. That one sentence is identical for every version of a chart, and
it is exactly what a consumer's Renovate pull request quotes back at them under
"Release Notes" -- so the single place a downstream operator looks before
merging a chart bump says nothing about what changed.

Everything worth reading is already here: the commits that touched the chart
directory since its last published tag, the appVersion they moved to, and the
values interface that moved with them. The notes are derived from those rather
than from a hand-kept changelog, for the same reason the browsable site is
generated -- a file maintained by hand is wrong the first time someone forgets
it, and a release body cannot be corrected in a pull request.

    python3 .github/scripts/release_notes.py charts/foo --output notes.md
    gh release edit foo-1.2.0 --notes-file notes.md

`--to` names the commit the notes describe. It defaults to HEAD, which is what
the release workflow has just released; pointing it at an existing tag is what
backfills the notes of a release that already shipped.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Run as a script, so sys.path[0] is this directory. Shared with upstream_sync
# rather than copied: the Chart.yaml reader keeps comments out of the way of a
# YAML parser, and the release link is only emitted when it actually resolves.
from upstream_sync import ANNOTATION_RELEASES, SEMVER, parse_chart, parse_version, release_url

# Record and field separators, so a commit body with newlines survives one
# `git log` call.
RECORD = "\x1e"
FIELD = "\x1f"

# Dropped from a commit body: they address the repository, not the consumer.
TRAILERS = {"co-authored-by", "signed-off-by", "claude-session", "reviewed-by", "helped-by"}

MAX_BODY_LINES = 20
MAX_COMMITS = 30
MAX_DIFF_LINES = 200


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def chart_at(ref: str, chart_dir: str) -> dict:
    """The chart's fields as of `ref`, or {} when the chart is not in that tree.

    The two ways `git show <ref>:<path>` fails are told apart on purpose. A ref
    that does not resolve is a broken invocation and has to say so with git's own
    message; a chart directory that is simply absent -- the chart was added after
    that tag -- is an answer, and the caller renders first-release notes from it.
    Resolving the ref first is what keeps a swallowed failure to the second kind.
    """
    git("rev-parse", "--verify", f"{ref}^{{commit}}")
    try:
        return parse_chart(git("show", f"{ref}:{chart_dir}/Chart.yaml"))
    except RuntimeError:
        return {}


def previous_tag(name: str, version: str) -> str:
    """The highest published tag of this chart below `version`.

    Published, not previous-in-Chart.yaml: a version can be bumped twice before
    a release ever runs -- 2.3.1 was overtaken by 2.4.0 and never shipped -- and
    notes that span a version nobody can install describe a gap that does not
    exist in the index.
    """
    current = parse_version(version)
    candidates = []
    for tag in git("tag", "--list", f"{name}-*").split():
        # The glob also catches a chart named `<name>-something`; the version
        # match on what follows the dash is what rejects those.
        suffix = tag[len(name) + 1 :]
        if SEMVER.match(suffix) and parse_version(suffix) < current:
            candidates.append((parse_version(suffix), tag))
    return max(candidates)[1] if candidates else ""


def commits(base: str, head: str, chart_dir: str) -> list[tuple[str, str, str]]:
    span = f"{base}..{head}" if base else head
    raw = git(
        "log",
        "--no-merges",
        f"--format={RECORD}%h{FIELD}%s{FIELD}%b",
        span,
        "--",
        chart_dir,
    )
    entries = []
    for record in raw.split(RECORD):
        if not record.strip():
            continue
        sha, subject, body = record.split(FIELD, 2)
        entries.append((sha.strip(), subject.strip(), body))
    return entries


def clean_body(body: str) -> tuple[str, bool]:
    lines = []
    for line in body.strip().splitlines():
        key, separator, _ = line.partition(":")
        if separator and key.strip().lower() in TRAILERS:
            continue
        lines.append(line.rstrip())
    while lines and not lines[-1]:
        lines.pop()
    if len(lines) <= MAX_BODY_LINES:
        return "\n".join(lines), False
    # Cut at the last paragraph break that fits rather than mid-sentence; these
    # bodies argue a point across a paragraph and half of one reads as nonsense.
    kept = lines[:MAX_BODY_LINES]
    if "" in kept:
        kept = kept[: len(kept) - kept[::-1].index("")]
    while kept and not kept[-1]:
        kept.pop()
    return "\n".join(kept), True


def values_diff(base: str, head: str, chart_dir: str) -> list[str]:
    """The values.yaml hunks, header stripped.

    Cutting at the first `@@` rather than filtering `---`/`+++` prefixes: a
    removed line that itself starts with `--` produces exactly those prefixes.
    """
    raw = git("diff", "--no-color", f"{base}..{head}", "--", f"{chart_dir}/values.yaml")
    lines = raw.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("@@"):
            return lines[index:]
    return []


def other_files(base: str, head: str, chart_dir: str) -> list[str]:
    """Changed files worth naming: not values.yaml, which is shown in full, and
    not the README, which is generated from it."""
    changed = git("diff", "--name-only", f"{base}..{head}", "--", chart_dir).split()
    skip = {f"{chart_dir}/values.yaml", f"{chart_dir}/README.md"}
    return sorted(path[len(chart_dir) + 1 :] for path in changed if path not in skip)


def render(chart_dir: str, head: str, repository: str) -> str:
    chart = chart_at(head, chart_dir)
    if not chart:
        raise SystemExit(f"{head} resolves, but carries no {chart_dir}/Chart.yaml.")

    name = chart["name"]
    version = chart["version"]
    app_version = chart.get("appVersion", "")
    base = previous_tag(name, version)
    before = chart_at(base, chart_dir) if base else {}
    owner, _, repo = repository.partition("/")

    out: list[str] = []

    if before:
        header = f"**Chart** `{before['version']}` → `{version}`"
    else:
        header = f"**Chart** `{version}` — first published version"
    if app_version:
        moved = before.get("appVersion") not in ("", None, app_version)
        header += (
            f" · **appVersion** `{before['appVersion']}` → `{app_version}`"
            if moved
            else f" · **appVersion** `{app_version}`"
        )
    out += [header, ""]

    # Only when the packaged software actually moved, and only if the upstream
    # really cut a release under that tag -- it does not always.
    if app_version and before.get("appVersion") not in ("", None, app_version):
        url = release_url(chart.get(ANNOTATION_RELEASES, ""), app_version)
        if url:
            out += [f"Upstream release notes: [{url.rsplit('/', 1)[-1]}]({url})", ""]

    entries = commits(base, head, chart_dir)
    if entries:
        out += ["### Changes", ""]
        for sha, subject, body in entries[:MAX_COMMITS]:
            link = f"https://github.com/{repository}/commit/{sha}"
            out.append(f"- **{subject}** ([`{sha}`]({link}))")
            text, truncated = clean_body(body)
            if text:
                out.append("")
                out += [f"  {line}".rstrip() for line in text.splitlines()]
                if truncated:
                    out += ["", f"  *(shortened — [full message]({link}))*"]
                out.append("")
        if len(entries) > MAX_COMMITS:
            out += [f"- … and {len(entries) - MAX_COMMITS} more commits", ""]
        if out[-1] != "":
            out.append("")

    if base:
        hunks = values_diff(base, head, chart_dir)
        if hunks:
            out += ["### Values", "", "<details>", "<summary><code>values.yaml</code> diff</summary>", ""]
            out += ["```diff"] + hunks[:MAX_DIFF_LINES] + ["```", ""]
            if len(hunks) > MAX_DIFF_LINES:
                out += [f"*{len(hunks) - MAX_DIFF_LINES} further diff lines omitted.*", ""]
            out += ["</details>", ""]
        rest = other_files(base, head, chart_dir)
        if rest:
            out += ["Also changed: " + ", ".join(f"`{path}`" for path in rest), ""]

    documentation = f"https://{owner}.github.io/{repo}/{name}/"
    links = [f"[Chart documentation]({documentation})"]
    if base:
        compare = f"https://github.com/{repository}/compare/{base}...{name}-{version}"
        links.append(f"[Full diff]({compare})")
    out += ["---", "", " · ".join(links), ""]

    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("chart", help="Chart directory, e.g. charts/manifest-llm-gateway.")
    parser.add_argument("--to", default="HEAD", help="Commit or tag the notes describe.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the notes here; stdout then carries the release tag they belong to.",
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", "rgielen/charts"),
        help="owner/name, used for every generated link.",
    )
    args = parser.parse_args()

    chart_dir = args.chart.rstrip("/")
    notes = render(chart_dir, args.to, args.repository)
    if args.output:
        args.output.write_text(notes)
        # The tag, so the caller does not read Chart.yaml a second time to find
        # the release these notes belong to.
        chart = chart_at(args.to, chart_dir)
        print(f"{chart['name']}-{chart['version']}")
    else:
        sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
