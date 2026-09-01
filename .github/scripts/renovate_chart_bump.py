#!/usr/bin/env python3
"""Find dependency pull requests that touch a chart without bumping its version.

Renovate can update an image pinned inside a chart, but it cannot raise that
chart's `version:` -- and without the bump, chart-releaser packages the chart on
`main`, finds the version already published, and skips it. The release run is
green and the update never reaches anyone. `ct lint --check-version-increment`
catches it in the pull request, so what actually happens is that every such
update sits there failing until somebody adds the bump by hand.

This finds those pull requests and reports what the bump would be. The workflow
applies it, regenerates the README and pushes onto the same branch, so Renovate
keeps ownership of its own pull request.

Deliberately not merging afterwards: `curlimages/curl` 8.11.1 -> 8.21.0 needed
someone to check that the image's numeric UID had not moved, because the chart
pins `runAsUser: 100` for that pod. No workflow was going to notice that. The
mechanical half is automated; the judgement stays with a person.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upstream_sync import bump_chart_version, read_chart  # noqa: E402

API = "https://api.github.com"
# upstream-sync owns these and bumps them itself.
SKIP_BRANCH_PREFIXES = ("upstream/",)


def api(path: str, token: str | None) -> object:
    request = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "rgielen-charts-renovate-chart-bump",
        },
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as err:
        raise SystemExit(f"GET {path} returned {err.code}: {err.read().decode()[:200]}") from err


def chart_version_at(repo: str, ref: str, chart: str, token: str | None) -> str | None:
    """The chart's `version:` at a ref, or None when the file is not there."""
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/charts/{chart}/Chart.yaml"
    request = urllib.request.Request(url, headers={"User-Agent": "rgielen-charts"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
    except urllib.error.HTTPError:
        return None
    match = re.search(r"^version:\s*(\S+)\s*$", body, re.MULTILINE)
    return match.group(1) if match else None


def detect(repo: str, token: str | None) -> list[dict]:
    pulls = api(f"/repos/{repo}/pulls?state=open&per_page=100", token)
    pending = []

    for pull in pulls:  # type: ignore[union-attr]
        branch = pull["head"]["ref"]
        if branch.startswith(SKIP_BRANCH_PREFIXES):
            continue
        if pull["head"]["repo"] is None or pull["head"]["repo"]["full_name"] != repo:
            # A fork branch cannot be pushed to, so there is nothing to do here.
            continue

        files = api(f"/repos/{repo}/pulls/{pull['number']}/files?per_page=100", token)
        charts = sorted(
            {
                f["filename"].split("/")[1]
                for f in files  # type: ignore[union-attr]
                if f["filename"].startswith("charts/") and len(f["filename"].split("/")) > 2
            }
        )
        if not charts:
            continue

        base = pull["base"]["ref"]
        for chart in charts:
            head_version = chart_version_at(repo, branch, chart, token)
            base_version = chart_version_at(repo, base, chart, token)
            if head_version is None or base_version is None:
                continue
            if head_version != base_version:
                continue  # already bumped, by Renovate's own config or by hand
            pending.append(
                {
                    "number": pull["number"],
                    "title": pull["title"],
                    "branch": branch,
                    "base": base,
                    "chart": chart,
                    "dir": f"charts/{chart}",
                    "from": base_version,
                    "to": bump_chart_version(base_version, "patch"),
                }
            )
    return pending


def apply(chart_yaml: Path, chart_version: str) -> None:
    lines = chart_yaml.read_text().splitlines(keepends=True)
    out = [f"version: {chart_version}\n" if re.match(r"^version:\s", line) else line for line in lines]
    chart_yaml.write_text("".join(out))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    detect_cmd = sub.add_parser("detect", help="print pull requests needing a bump, as JSON")
    detect_cmd.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))

    apply_cmd = sub.add_parser("apply", help="write the version line of one chart")
    apply_cmd.add_argument("chart_yaml", type=Path)
    apply_cmd.add_argument("chart_version")

    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")

    if args.command == "detect":
        if not args.repo:
            raise SystemExit("no repository: pass --repo or set GITHUB_REPOSITORY")
        pending = detect(args.repo, token)
        print(json.dumps(pending, separators=(",", ":")))
        for entry in pending:
            print(
                f"  #{entry['number']} {entry['chart']}: {entry['from']} -> {entry['to']}",
                file=sys.stderr,
            )
        if not pending:
            print("  no dependency pull request is missing a chart version bump", file=sys.stderr)
    else:
        apply(args.chart_yaml, args.chart_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
