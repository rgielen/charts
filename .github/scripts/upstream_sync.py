#!/usr/bin/env python3
"""Watch the upstream container image of every chart and bump it.

A chart opts in through annotations in its Chart.yaml:

    annotations:
      charts.rgielen.de/upstream-image: docker.io/example/app
      charts.rgielen.de/upstream-tag-pattern: '^[0-9]+\\.[0-9]+\\.[0-9]+$'
      charts.rgielen.de/upstream-releases: https://github.com/example/app/releases/tag/v{version}

`detect` prints a JSON array of the charts whose image has a newer tag, without
touching anything. `apply` writes the two version lines for one chart.

The chart's own `version` has to move together with `appVersion`: the release
workflow packages every chart but only publishes versions that do not exist yet,
so an appVersion bump without a version bump is a green run that ships nothing.
That coupling is the entire reason this script exists instead of a Renovate rule.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ANNOTATION_IMAGE = "charts.rgielen.de/upstream-image"
ANNOTATION_PATTERN = "charts.rgielen.de/upstream-tag-pattern"
ANNOTATION_RELEASES = "charts.rgielen.de/upstream-releases"

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER.match(value.strip().strip('"').strip("'"))
    if not match:
        raise ValueError(f"not a three-part semantic version: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def read_chart(path: Path) -> dict:
    """Read the handful of Chart.yaml fields we need.

    Deliberately line-based rather than a YAML parse: the same code path writes
    the file back, and comments in Chart.yaml carry real information that a
    round-trip through a plain YAML loader would drop.
    """
    fields: dict[str, str] = {}
    in_annotations = False
    for line in path.read_text().splitlines():
        top = re.match(r"^([A-Za-z][\w]*):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            in_annotations = key == "annotations"
            if value:
                fields[key] = value.strip('"').strip("'")
            continue
        if in_annotations:
            nested = re.match(r"^\s+([^:\s]+):\s*(.+)$", line)
            if nested:
                fields[nested.group(1)] = nested.group(2).strip().strip('"').strip("'")
    return fields


def list_tags(image: str) -> list[str]:
    result = subprocess.run(
        ["crane", "ls", image], capture_output=True, text=True, check=True
    )
    return [tag for tag in result.stdout.splitlines() if tag]


def bump_chart_version(current: str, kind: str) -> str:
    major, minor, patch = parse_version(current)
    if kind == "major":
        # Charts here start at 1.0.0 by convention, so the second branch should
        # never be reached. It stays as a guard: bumping a 0.x chart to 1.0.0
        # would be a statement about the chart's own stability, not about the
        # software it packages.
        return f"{major + 1}.0.0" if major > 0 else f"{major}.{minor + 1}.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def change_kind(current: tuple[int, int, int], latest: tuple[int, int, int]) -> str:
    if latest[0] != current[0]:
        return "major"
    if latest[1] != current[1]:
        return "minor"
    return "patch"


def detect(charts_dir: Path, only: str | None) -> list[dict]:
    updates = []
    for chart_yaml in sorted(charts_dir.glob("*/Chart.yaml")):
        directory = chart_yaml.parent
        if only and directory.name != only:
            continue

        chart = read_chart(chart_yaml)
        image = chart.get(ANNOTATION_IMAGE)
        if not image:
            continue

        pattern = re.compile(chart.get(ANNOTATION_PATTERN, r"^\d+\.\d+\.\d+$"))
        current_app = chart["appVersion"]
        candidates = [tag for tag in list_tags(image) if pattern.match(tag)]
        if not candidates:
            print(f"{directory.name}: no tag of {image} matched the pattern", file=sys.stderr)
            continue

        latest = max(candidates, key=parse_version)
        if parse_version(latest) <= parse_version(current_app):
            print(f"{directory.name}: {current_app} is current", file=sys.stderr)
            continue

        kind = change_kind(parse_version(current_app), parse_version(latest))
        new_chart_version = bump_chart_version(chart["version"], kind)
        releases = chart.get(ANNOTATION_RELEASES, "")
        updates.append(
            {
                "name": directory.name,
                "dir": str(directory),
                "image": image,
                "currentAppVersion": current_app,
                "appVersion": latest,
                "currentChartVersion": chart["version"],
                "chartVersion": new_chart_version,
                "bumpType": kind,
                "branch": f"upstream/{directory.name}-{latest}",
                "releasesUrl": releases.replace("{version}", latest) if releases else "",
            }
        )
        print(
            f"{directory.name}: {current_app} -> {latest} ({kind}), "
            f"chart {chart['version']} -> {new_chart_version}",
            file=sys.stderr,
        )
    return updates


def apply(chart_yaml: Path, app_version: str, chart_version: str) -> None:
    lines = chart_yaml.read_text().splitlines(keepends=True)
    out = []
    for line in lines:
        if re.match(r"^version:\s", line):
            out.append(f"version: {chart_version}\n")
        elif re.match(r"^appVersion:\s", line):
            # Quoted so a two-segment version stays a string rather than a float.
            out.append(f'appVersion: "{app_version}"\n')
        else:
            out.append(line)
    chart_yaml.write_text("".join(out))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    detect_cmd = sub.add_parser("detect", help="print pending updates as JSON")
    detect_cmd.add_argument("--charts-dir", default="charts", type=Path)
    detect_cmd.add_argument("--chart", default=None, help="limit to a single chart")

    apply_cmd = sub.add_parser("apply", help="write the version lines of one chart")
    apply_cmd.add_argument("chart_yaml", type=Path)
    apply_cmd.add_argument("app_version")
    apply_cmd.add_argument("chart_version")

    args = parser.parse_args()
    if args.command == "detect":
        print(json.dumps(detect(args.charts_dir, args.chart), separators=(",", ":")))
    else:
        apply(args.chart_yaml, args.app_version, args.chart_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
