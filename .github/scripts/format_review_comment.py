#!/usr/bin/env python3
"""Turn the upstream review's structured output into a pull request comment.

Kept out of the workflow because an inline heredoc inside a YAML block scalar is
a reliable way to produce a file that parses today and breaks on the next edit.

Reads the JSON on stdin, writes markdown on stdout, and exits 1 when the review
should add a reason to hold. It never decides whether the pull request merges:
the merge job requires a `clean` verdict from the deterministic check, which this
path cannot produce.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    run_url = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = sys.stdin.read().strip()

    out: list[str] = ["### Upstream review", ""]

    if not raw:
        out += [
            "The review produced no output. The configuration-surface diff above still "
            "stands and this pull request is still held — nothing was auto-merged.",
            "",
            f"[Workflow run]({run_url})" if run_url else "",
        ]
        print("\n".join(out))
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as err:
        out += [
            f"The review's output could not be parsed (`{err}`). Treat this as no review "
            "having happened; the pull request is still held.",
            "",
            f"[Workflow run]({run_url})" if run_url else "",
        ]
        print("\n".join(out))
        return 1

    findings = data.get("findings") or []
    blocking = [f for f in findings if f.get("severity") == "blocking"]
    assessment = data.get("assessment", "uncertain")

    out += [
        f"**Assessment: `{assessment}`** — {len(blocking)} blocking, "
        f"{len(findings) - len(blocking)} worth knowing.",
        "",
    ]
    if data.get("summary"):
        out += [data["summary"], ""]

    for finding in findings:
        mark = "**blocking**" if finding.get("severity") == "blocking" else "worth knowing"
        out += [
            f"<details><summary>{mark} — {finding.get('summary', '')}</summary>",
            "",
            f"**Chart:** `{finding.get('chart_location', '')}`",
            "",
            "**Upstream evidence:**",
            "",
            "```",
            str(finding.get("evidence", "")),
            "```",
            "",
        ]
        if finding.get("proposed_edit"):
            out += [f"**Proposed edit:** {finding['proposed_edit']}", ""]
        out += ["</details>", ""]

    out += [
        "This review can only add reasons to hold. It has no path to the merge condition, "
        "which requires a `clean` verdict from the deterministic check. Run "
        "`/analyze-upstream` locally to act on any of this.",
        "",
    ]
    if run_url:
        out.append(f"[Workflow run]({run_url})")

    print("\n".join(out))
    return 1 if (assessment != "no_chart_impact" or blocking) else 0


if __name__ == "__main__":
    sys.exit(main())
