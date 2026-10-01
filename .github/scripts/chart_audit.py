#!/usr/bin/env python3
"""Compare what a chart claims against what its upstream actually does.

Two kinds of drift are invisible to a file diff and to `helm lint`:

1. The chart and its own documentation disagree -- a value is emitted but never
   appears in the environment-variable mapping table, or the table names a
   setting the chart stopped emitting.
2. The upstream reads a setting the chart has never modelled. No single file
   lists them all: `MIGRATION_DATABASE_URL` appears in neither `.env.example`,
   and `MANIFEST_RATE_MAX_REQUESTS` is read in the proxy's rate limiter, not in
   `app.config.ts`. The documented sources are read first; the source tree is
   then scanned for every `process.env` read they do not account for.

This reports both, plus the image assumptions the chart is built on -- the
migration Job runs a hardcoded path inside the image, the Helm test pod assumes
there is no shell, the pod security context pins a numeric UID. None of that
survives an upstream refactor quietly.

It reports. It decides nothing: several findings here are legitimate omissions,
and telling those apart is the reviewing half of `/analyze-upstream`.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upstream_diff import Unknown, file_at, revision, slug  # noqa: E402
from upstream_sync import read_chart  # noqa: E402

# Which files define an upstream's configuration surface is project-specific, and
# there is no sensible default -- guessing produces a confident empty answer. A
# chart without this annotation gets "not checked", not "nothing found".
ANNOTATION_CONFIG_SOURCES = "charts.rgielen.de/upstream-config-sources"

# The directories whose code runs in the image. Scanning the whole repository
# instead would mix in the frontend's build-time variables and CI scripts, none
# of which a deployment can set; a chart without the annotation gets "not
# checked" for the same reason as above.
ANNOTATION_SOURCE_ROOTS = "charts.rgielen.de/upstream-source-roots"

ENV_NAME = r"[A-Z][A-Z0-9_]{2,}"

SOURCE_SUFFIXES = (".ts", ".js", ".mjs", ".cjs")
TEST_PATH = re.compile(r"\.(spec|test|e2e-spec)\.[cm]?[jt]s$|/(__tests__|test|tests|e2e)/")


def emitted_env(helpers: str) -> set[str]:
    """Environment variables the chart actually puts into the container.

    Matches the two shapes `_helpers.tpl` uses and nothing else, so the word
    `KEY` in a doc comment is not mistaken for a setting.
    """
    names = set(re.findall(rf'\.put" \(list \$d "({ENV_NAME})"', helpers))
    names |= set(re.findall(rf'set \$d "({ENV_NAME})"', helpers))
    return names


def documented_env(gotmpl: str) -> set[str]:
    """Environment variables named in the chart's mapping table."""
    table = gotmpl.split("## Environment variable mapping", 1)
    if len(table) < 2:
        return set()
    return set(re.findall(rf"`({ENV_NAME})`", table[1]))


def upstream_env(sources: dict[str, str]) -> dict[str, set[str]]:
    """Environment variables the upstream reads, per source file."""
    found: dict[str, set[str]] = {}
    for path, text in sources.items():
        if path.endswith(".env.example"):
            names = set(re.findall(rf"^#?\s*({ENV_NAME})=", text, re.MULTILINE))
        else:
            names = env_reads(text)
        found[path] = names
    return found


def env_reads(text: str) -> set[str]:
    """`process.env.NAME` and `process.env['NAME']`, the two shapes the upstream uses."""
    names = set(re.findall(rf"env\[['\"]({ENV_NAME})['\"]\]", text))
    names |= set(re.findall(rf"process\.env\.({ENV_NAME})\b", text))
    return names


def source_env(repo: str, commit: str, roots: list[str]) -> dict[str, list[str]]:
    """Every environment variable read under `roots`, with the files reading it.

    One tarball rather than a file at a time: the tree has thousands of files,
    and the contents API that would list them is rate-limited without a token.
    Tests are left out -- they set variables to exercise code, not to configure
    it.
    """
    url = f"https://codeload.github.com/{repo}/tar.gz/{commit}"
    request = urllib.request.Request(url, headers={"User-Agent": "rgielen-charts-chart-audit"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            archive = response.read()
    except urllib.error.HTTPError as err:
        raise Unknown(f"GET {url} returned {err.code}") from err
    except OSError as err:
        raise Unknown(f"GET {url} failed: {err}") from err

    prefixes = tuple(root.strip("/") + "/" for root in roots)
    found: dict[str, set[str]] = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar:
            # Every entry sits under one `<repo>-<commit>/` directory.
            path = member.name.split("/", 1)[-1]
            if not (
                member.isfile()
                and path.startswith(prefixes)
                and path.endswith(SOURCE_SUFFIXES)
                and "/node_modules/" not in path
                and not TEST_PATH.search(path)
            ):
                continue
            text = tar.extractfile(member).read().decode("utf-8", errors="replace")
            for name in env_reads(text):
                found.setdefault(name, set()).add(path)
    return {name: sorted(paths) for name, paths in found.items()}


def schema_enums(schema: dict) -> dict[str, list]:
    """Every enum in values.schema.json, by dotted path.

    An enum is a promise about what the upstream accepts. When the upstream adds
    a value, the chart rejects a configuration that would have worked, and
    nothing fails until a user hits it.
    """
    out: dict[str, list] = {}

    def walk(node: object, path: str) -> None:
        if not isinstance(node, dict):
            return
        if "enum" in node:
            out[path] = node["enum"]
        for key, value in node.get("properties", {}).items():
            walk(value, f"{path}.{key}" if path else key)

    walk(schema, "")
    return out


def image_contract(image: str, tag: str, expectations: dict) -> list[dict]:
    """Check the image assumptions the chart's templates are built on."""
    results: list[dict] = []

    try:
        config = json.loads(
            subprocess.run(
                ["crane", "config", f"{image}:{tag}"], capture_output=True, text=True, check=True
            ).stdout
        )["config"]
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError, KeyError) as err:
        return [{"check": "image config", "ok": False, "detail": f"could not be read: {err}"}]

    user = str(config.get("User", ""))
    results.append(
        {
            "check": "runs as the UID the chart pins",
            "ok": user == str(expectations["user"]),
            "detail": f"image User={user!r}, chart podSecurityContext.runAsUser={expectations['user']}",
        }
    )

    ports = sorted((config.get("ExposedPorts") or {}).keys())
    expected_port = f"{expectations['port']}/tcp"
    results.append(
        {
            "check": "exposes the port the chart uses",
            "ok": expected_port in ports,
            "detail": f"image exposes {ports or 'nothing'}, chart uses {expected_port}",
        }
    )

    results.append(
        {
            "check": "entrypoint still takes a script argument",
            "ok": bool(config.get("Entrypoint")) and "node" in " ".join(config.get("Entrypoint", [])),
            "detail": f"Entrypoint={config.get('Entrypoint')} Cmd={config.get('Cmd')}",
        }
    )

    # Layer contents: needs the layers, so it is the slow part.
    try:
        listing = subprocess.run(
            f"crane export {image}:{tag} - | tar -tf -",
            shell=True,
            capture_output=True,
            text=True,
            check=True,
            timeout=600,
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        results.append({"check": "image contents", "ok": False, "detail": f"could not be listed: {err}"})
        return results

    files = set(listing.splitlines())
    for path in expectations["required_files"]:
        results.append(
            {
                "check": f"{path} is present",
                "ok": path.lstrip("/") in files,
                "detail": "the chart runs this path directly",
            }
        )
    shells = sorted(f for f in files if f in ("bin/sh", "usr/bin/sh", "bin/bash", "usr/bin/bash"))
    results.append(
        {
            "check": "still no shell in the image",
            "ok": not shells,
            "detail": (
                f"found {shells}" if shells else "distroless, as the probes and the test pod assume"
            ),
        }
    )
    return results


def audit(chart_dir: Path, tag: str | None, skip_image: bool) -> dict:
    chart_yaml = chart_dir / "Chart.yaml"
    chart = read_chart(chart_yaml)
    image = chart.get("charts.rgielen.de/upstream-image", "")
    tag = tag or chart.get("appVersion", "")

    helpers = (chart_dir / "templates" / "_helpers.tpl").read_text()
    gotmpl = (chart_dir / "README.md.gotmpl").read_text()
    schema_path = chart_dir / "values.schema.json"
    schema = json.loads(schema_path.read_text()) if schema_path.exists() else {}

    emitted = emitted_env(helpers)
    documented = documented_env(gotmpl)

    report: dict = {
        "chart": chart_dir.name,
        "image": image,
        "tag": tag,
        "emitted_count": len(emitted),
        "documented_count": len(documented),
        "emitted_not_documented": sorted(emitted - documented),
        "documented_not_emitted": sorted(documented - emitted),
        "schema_enums": schema_enums(schema),
        "upstream": {},
        "upstream_unmodelled": [],
        "source_only": {},
        "image_contract": [],
        "errors": [],
    }

    try:
        commit, source = revision(image, tag)
        repo = slug(source)
        report["revision"] = commit
        paths = [p.strip() for p in chart.get(ANNOTATION_CONFIG_SOURCES, "").split(",") if p.strip()]
        if not paths:
            report["errors"].append(
                f"{chart_dir.name} has no {ANNOTATION_CONFIG_SOURCES} annotation, "
                "so what the upstream reads was not checked"
            )
        sources = {}
        for path in paths:
            try:
                sources[path] = file_at(repo, commit, path)
            except Unknown as err:
                report["errors"].append(str(err))
        found = upstream_env(sources)
        report["upstream"] = {path: sorted(names) for path, names in found.items()}
        every = set().union(*found.values()) if found else set()

        roots = [p.strip() for p in chart.get(ANNOTATION_SOURCE_ROOTS, "").split(",") if p.strip()]
        if not roots:
            report["errors"].append(
                f"{chart_dir.name} has no {ANNOTATION_SOURCE_ROOTS} annotation, "
                "so settings read outside the documented sources were not checked"
            )
        else:
            try:
                in_source = source_env(repo, commit, roots)
            except Unknown as err:
                report["errors"].append(str(err))
            else:
                report["source_only"] = {
                    name: paths for name, paths in sorted(in_source.items()) if name not in every
                }
                every |= set(in_source)
        report["upstream_unmodelled"] = sorted(every - emitted - documented)
    except Unknown as err:
        report["errors"].append(str(err))

    if not skip_image:
        try:
            report["image_contract"] = image_contract(
                image,
                tag,
                {
                    "user": 65532,
                    "port": 2099,
                    "required_files": ["app/packages/backend/dist/database/migrate.js"],
                },
            )
        except Exception as err:  # noqa: BLE001 - a failed check is a finding, not a crash
            report["errors"].append(f"image contract check failed: {err}")

    return report


def markdown(report: dict) -> str:
    lines = [f"### Chart audit — `{report['chart']}` against `{report['image']}:{report['tag']}`", ""]
    if report.get("revision"):
        lines.append(f"Upstream commit `{report['revision'][:12]}`.")
        lines.append("")

    def section(title: str, items: list[str], note: str) -> None:
        lines.append(f"**{title}** ({len(items)})")
        lines.append("")
        if items:
            lines.extend(f"- `{i}`" for i in items)
        else:
            lines.append("- none")
        lines.append("")
        lines.append(f"_{note}_")
        lines.append("")

    section(
        "Emitted by the chart, absent from the mapping table",
        report["emitted_not_documented"],
        "The table is published documentation; a missing row means a setting nobody can find.",
    )
    section(
        "In the mapping table, not emitted by the chart",
        report["documented_not_emitted"],
        "Expected for rows that document a deliberate omission. Anything else is a stale promise.",
    )
    section(
        "Read by the upstream, modelled nowhere in the chart",
        report["upstream_unmodelled"],
        "Not automatically a gap: some of these are cloud-only or legacy. Each one is a decision "
        "that has not been made, and the reasoning belongs in the chart once it has.",
    )

    unmodelled = set(report["upstream_unmodelled"])
    hidden = {n: p for n, p in report["source_only"].items() if n in unmodelled}
    if hidden:
        lines.append("**Of those, read in code but listed in no documented source**")
        lines.append("")
        for name, paths in hidden.items():
            lines.append(f"- `{name}` — {', '.join(f'`{p}`' for p in paths)}")
        lines.append("")
        lines.append(
            "_Where the upstream reads it is the only documentation there is; start there._"
        )
        lines.append("")

    if report["schema_enums"]:
        lines.append("**Schema enums to check against the upstream**")
        lines.append("")
        for path, values in sorted(report["schema_enums"].items()):
            lines.append(f"- `{path}`: {values}")
        lines.append("")
        lines.append(
            "_An enum the upstream has outgrown rejects a configuration that would have worked._"
        )
        lines.append("")

    if report["image_contract"]:
        lines.append("**Image contract**")
        lines.append("")
        for check in report["image_contract"]:
            mark = "ok" if check["ok"] else "**FAILED**"
            lines.append(f"- {mark} — {check['check']}: {check['detail']}")
        lines.append("")

    if report["errors"]:
        lines.append("**Could not be checked**")
        lines.append("")
        lines.extend(f"- {e}" for e in report["errors"])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chart_dir", type=Path)
    parser.add_argument("--tag", help="image tag to audit against; default is the chart's appVersion")
    parser.add_argument(
        "--skip-image",
        action="store_true",
        help="skip the image contract checks, which download the image layers",
    )
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()

    report = audit(args.chart_dir, args.tag, args.skip_image)
    if args.markdown_out:
        args.markdown_out.write_text(markdown(report))
    print(json.dumps(report, separators=(",", ":")))

    failed = [c for c in report["image_contract"] if not c["ok"]]
    for entry in failed:
        print(f"  IMAGE CONTRACT FAILED: {entry['check']} -- {entry['detail']}", file=sys.stderr)
    for entry in report["errors"]:
        print(f"  {entry}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
