#!/usr/bin/env python3
"""Report what changed in an upstream project's configuration surface.

An image bump is only safe to merge unattended if the settings the chart models
did not move underneath it. That is not what release notes tell you -- the
upstream tracked here publishes image tags without a matching GitHub release at
all, so for `6.19.1` there is nothing to read. What every image does carry is
`org.opencontainers.image.revision`: the exact commit it was built from. This
compares the watched files between the old and the new revision.

The comparison is deliberately mechanical. It answers "did anything in the
configuration surface change", not "does it matter" -- a changed default is
reported the same as a new variable, because deciding which of those matters is
the part a person (or, later, a model) should do.

A chart opts in with a Chart.yaml annotation:

    charts.rgielen.de/upstream-watch-paths: docker/.env.example,docker/docker-compose.yml

Verdicts:
  clean   nothing watched changed; safe to merge unattended
  review  something changed, could not be determined, or a migration was added

Anything that goes wrong -- an unreachable registry, a missing label, a failed
fetch -- is `review`. A check that answers "clean" when it could not look is
worse than no check at all.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upstream_sync import read_chart  # noqa: E402

ANNOTATION_WATCH_PATHS = "charts.rgielen.de/upstream-watch-paths"
REVISION_LABEL = "org.opencontainers.image.revision"
SOURCE_LABEL = "org.opencontainers.image.source"


class Unknown(Exception):
    """Something could not be determined. Always resolves to `review`."""


def image_labels(image: str, tag: str) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["crane", "config", f"{image}:{tag}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as err:
        raise Unknown(f"could not read the image config of {image}:{tag}: {err}") from err
    try:
        return json.loads(result.stdout).get("config", {}).get("Labels") or {}
    except json.JSONDecodeError as err:
        raise Unknown(f"the image config of {image}:{tag} is not JSON: {err}") from err


def revision(image: str, tag: str) -> tuple[str, str]:
    """Return (commit, source repository url) for an image tag."""
    labels = image_labels(image, tag)
    commit = labels.get(REVISION_LABEL)
    source = labels.get(SOURCE_LABEL, "")
    if not commit:
        raise Unknown(f"{image}:{tag} carries no {REVISION_LABEL} label")
    return commit, source


def slug(source_url: str) -> str:
    """github.com/owner/repo out of the source label."""
    if "github.com/" not in source_url:
        raise Unknown(f"the source label {source_url!r} is not a GitHub repository")
    return source_url.split("github.com/", 1)[1].removesuffix(".git").strip("/")


def fetch(url: str, token: str | None = None) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "rgielen-charts-upstream-diff"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        raise Unknown(f"GET {url} returned {err.code}") from err
    except OSError as err:
        raise Unknown(f"GET {url} failed: {err}") from err


def file_at(repo: str, commit: str, path: str) -> str:
    return fetch(f"https://raw.githubusercontent.com/{repo}/{commit}/{path}")


def added_files(repo: str, base: str, head: str, prefix: str, token: str | None) -> list[str]:
    body = fetch(f"https://api.github.com/repos/{repo}/compare/{base}...{head}", token)
    try:
        files = json.loads(body).get("files", [])
    except json.JSONDecodeError as err:
        raise Unknown(f"the compare response for {repo} is not JSON: {err}") from err
    # `added` only: a range that merely touches existing migrations -- a rename, a
    # comment -- is not a schema change, and reporting those buries the real ones.
    return sorted(
        f["filename"]
        for f in files
        if f.get("status") == "added" and prefix in f["filename"] and ".spec." not in f["filename"]
    )


def report(chart_dir: Path, from_version: str, to_version: str) -> dict:
    chart = read_chart(chart_dir / "Chart.yaml")
    image = chart.get("charts.rgielen.de/upstream-image", "")
    watch = [p.strip() for p in chart.get(ANNOTATION_WATCH_PATHS, "").split(",") if p.strip()]

    lines: list[str] = []
    reasons: list[str] = []

    if not watch:
        return {
            "verdict": "review",
            "reasons": [f"{chart_dir.name} has no {ANNOTATION_WATCH_PATHS} annotation"],
            "markdown": (
                f"### Upstream configuration surface\n\n"
                f"Not checked: `{chart_dir.name}` has no `{ANNOTATION_WATCH_PATHS}` annotation, "
                f"so there is nothing to compare. Review this bump by hand.\n"
            ),
        }

    try:
        old_commit, source = revision(image, from_version)
        new_commit, _ = revision(image, to_version)
        repo = slug(source)
    except Unknown as err:
        return {
            "verdict": "review",
            "reasons": [str(err)],
            "markdown": (
                f"### Upstream configuration surface\n\n"
                f"Could not be compared: {err}. Review this bump by hand.\n"
            ),
        }

    compare_url = f"https://github.com/{repo}/compare/{old_commit}...{new_commit}"
    lines.append("### Upstream configuration surface")
    lines.append("")
    lines.append(
        f"`{from_version}` ([`{old_commit[:12]}`](https://github.com/{repo}/commit/{old_commit})) → "
        f"`{to_version}` ([`{new_commit[:12]}`](https://github.com/{repo}/commit/{new_commit})) — "
        f"[full compare]({compare_url})"
    )
    lines.append("")
    lines.append(
        "Resolved from the images' `org.opencontainers.image.revision` label, "
        "which exists whether or not the upstream cut a release for this version."
    )
    lines.append("")

    changed: list[str] = []
    for path in watch:
        try:
            old = file_at(repo, old_commit, path)
            new = file_at(repo, new_commit, path)
        except Unknown as err:
            reasons.append(str(err))
            lines.append(f"- `{path}` — **could not be fetched**: {err}")
            continue
        if old == new:
            lines.append(f"- `{path}` — unchanged")
            continue
        changed.append(path)
        diff = list(
            difflib.unified_diff(
                old.splitlines(), new.splitlines(), fromfile=path, tofile=path, lineterm="", n=3
            )
        )
        lines.append(f"- `{path}` — **changed** ({len(diff)} diff lines)")

    if changed:
        reasons.append(f"changed: {', '.join(changed)}")
        lines.append("")
        lines.append("<details><summary>Diff</summary>")
        lines.append("")
        lines.append("```diff")
        for path in changed:
            old = file_at(repo, old_commit, path)
            new = file_at(repo, new_commit, path)
            lines.extend(
                difflib.unified_diff(
                    old.splitlines(), new.splitlines(), fromfile=path, tofile=path, lineterm="", n=3
                )
            )
        lines.append("```")
        lines.append("")
        lines.append("</details>")

    try:
        migrations = added_files(
            repo, old_commit, new_commit, "database/migrations/", os.environ.get("GITHUB_TOKEN")
        )
    except Unknown as err:
        reasons.append(str(err))
        migrations = []
        lines.append("")
        lines.append(f"- migrations — **could not be listed**: {err}")
    else:
        lines.append("")
        if migrations:
            reasons.append(f"{len(migrations)} new migration(s)")
            lines.append(f"- **{len(migrations)} new migration file(s)**:")
            lines.extend(f"  - `{m}`" for m in migrations)
        else:
            lines.append("- no new migration files")

    verdict = "review" if reasons else "clean"
    lines.append("")
    if verdict == "clean":
        lines.append(
            "**Clean.** Nothing the chart models moved between these two revisions, "
            "so this bump merges unattended."
        )
    else:
        lines.append(
            "**Needs review.** " + "; ".join(reasons) + ". "
            "This pull request is on hold until someone confirms the chart still matches "
            "the upstream, then merges it."
        )
    lines.append("")

    return {"verdict": verdict, "reasons": reasons, "markdown": "\n".join(lines)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chart_dir", type=Path)
    parser.add_argument("from_version")
    parser.add_argument("to_version")
    parser.add_argument("--markdown-out", type=Path, help="write the report here")
    args = parser.parse_args()

    result = report(args.chart_dir, args.from_version, args.to_version)
    if args.markdown_out:
        args.markdown_out.write_text(result["markdown"])
    print(json.dumps({"verdict": result["verdict"], "reasons": result["reasons"]}, separators=(",", ":")))
    for reason in result["reasons"]:
        print(f"  {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
