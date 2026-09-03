# Plan: a chart for `hermes-webui`

Status: **deferred, not started.** Nothing has been created under `charts/`.
Tracked in <https://github.com/rgielen/charts/issues/41>.

Upstream: <https://github.com/nesquena/hermes-webui> — a self-hosted browser
interface for the Hermes Agent. Everything below was verified against the
upstream on **2026-09-03**, working from a shallow clone of `master`
(pushed 2026-08-31) and from the registry. Where a fact is likely to age, the
date it was true is written next to it.

---

## The three decisions that fix the shape

Taken 2026-09-03. Each one closes off a branch of the design; re-open them only
deliberately.

1. **WebUI standalone.** The chart does not deploy the Hermes Agent. It carries
   exactly one upstream, and documents the recipe an operator uses to add the
   agent themselves.
2. **Stable channel only.** An image tag counts as a candidate only if a
   matching `v<version>` git tag exists upstream. This needs an addition to
   `upstream_sync.py` — the image tags alone cannot tell the channels apart.
3. **`/app` is an `emptyDir`.** Dependencies are installed on every pod start.
   It costs start-up time and PyPI egress, and it is the only arrangement where
   the code and its dependencies provably come from the same image.

---

## What the upstream actually is

A Python standard-library HTTP server with a vanilla-JS frontend — no build
step, no framework. MIT. 18k stars, 831 open issues, created 2026-03-30,
default branch `master`.

**Image.** `ghcr.io/nesquena/hermes-webui`, `linux/amd64` + `linux/arm64`.
Built from `python:3.12-slim`. Runs as `root` with `CMD ["/hermeswebui_init.bash"]`,
`EXPOSE 8787`, and `HERMES_WEBUI_HOST=0.0.0.0` / `HERMES_WEBUI_PORT=8787` baked
into the image environment. Creates user `hermeswebui` with **UID/GID 1024**,
and leaves `/app`, `/uv_cache` and `/workspace` at mode 1777. `uv` is
pre-installed system-wide in `/usr/local/bin`.

**Labels.** `org.opencontainers.image.revision` is present, so
`upstream_diff.py` works against this image without modification.
`org.opencontainers.image.source` points at the GitHub repository, which is what
the stable-channel check in Phase 5 can reuse.

**Entrypoint.** `docker_init.bash` is where nearly every surprise lives:

- Started as root it aligns the `hermeswebui` UID/GID with `WANTED_UID`/`WANTED_GID`
  (auto-detected from the state dir, then `$HERMES_HOME`, then `/workspace`),
  chowns `/home/hermeswebui` recursively, `rsync`s `/apptoo` → `/app`, and
  re-enters through `su`.
- A rootless path exists since v0.51.64 (PR #2277, plus PR #2268 for the
  `whoami` fallback on UIDs without an `/etc/passwd` entry). It is written for
  Kubernetes `runAsNonRoot` and OpenShift's restricted SCC. **This is the mode
  the chart should use.**
- In the rootless path a UID that does not match the detected `WANTED_UID`
  is a **hard abort**: `hermeswebui MUST be running as UID … GID …`. The chart
  must therefore derive `WANTED_UID`/`WANTED_GID` from
  `podSecurityContext.runAsUser`/`runAsGroup` rather than let them be set
  independently.
- It creates a virtualenv and runs `uv pip install -r requirements.txt` on every
  fresh container. `requirements.txt` is tiny — `pyyaml>=6.0`,
  `cryptography>=42.0` — so a standalone start stays cheap.
- If the agent source is found at `$HERMES_HOME/hermes-agent` or `/opt/hermes`,
  it additionally stages it into `/app/hermes-agent-src` and runs
  `uv pip install -e …[all]`. Those two paths are hardcoded in the shell script;
  `HERMES_WEBUI_AGENT_DIR` only steers the Python side, not the installer.

**State.** JSON sessions plus SQLite under `$HERMES_HOME/webui`, attachments,
settings, projects. ReadWriteOnce, one replica, `Recreate`. There is no
arrangement in which a second replica is correct.

**Configuration surface.** 108 distinct `HERMES_WEBUI_*` variables, read from
`os.getenv` calls spread across `api/*.py`. `api/config.py` alone is 10,404
lines. **There is no authoritative configuration file** — nothing here plays the
role `packages/backend/src/config/app.config.ts` plays for Manifest.

**Auth is optional.** Password (`HERMES_WEBUI_PASSWORD`), passkeys, OIDC
(`HERMES_WEBUI_OIDC_ISSUER`, `_CLIENT_ID`, `_ALLOW_CLAIM`, `_ALLOW_VALUES`),
signed HMAC cookies with a 24h TTL. With none of them configured the server only
prints a warning at start-up: *"Binding to 0.0.0.0 with NO PASSWORD SET. Anyone
on the network can access your filesystem and agent."*

**Health.** `/health` is listed in `PUBLIC_PATHS` (`api/auth.py`), so it answers
without authentication and is usable as a probe. `/health?deep=1` exists for
supervisors.

**Reverse-proxy surface.** `HERMES_WEBUI_TRUST_FORWARDED_FOR`,
`_TRUST_FORWARDED_PROTO`, `_TRUST_FORWARDED_HOST`, `_TRUSTED_PROXY_CIDRS`,
`_ALLOWED_ORIGINS`, `_SECURE`, `_COOKIE_NAME`, `_CSP_FRAME_EXTRA`,
`_SSE_CHUNKED`. Chat streams over SSE, so a buffering proxy is a real failure
mode.

**The agent.** `nousresearch/hermes-agent` on Docker Hub, public, ~950 MB
compressed, calendar-versioned (`v2026.8.31`). The WebUI imports the agent's
Python modules in-process; the gateway URL (`HERMES_API_URL`) only covers
health, tasks and cron. Without the agent source the WebUI starts but runs with
reduced functionality — no model auto-detection, no personality routing, no CLI
session import. Deliberately out of scope; see the recipe in Phase 3.

---

## The findings that shape the plan

### 1. The registry tags do not distinguish stable from experimental

Upstream tags two channels, `v*` and `exp-v*`. `.github/workflows/release.yml`
feeds both to `docker/metadata-action` through
`type=match,pattern=v(\d+\.\d+(?:\.\d+)?)` and
`type=match,pattern=exp-v(\d+\.\d+(?:\.\d+)?)`, and both produce a bare
`X.Y.Z` image tag. A pattern like `^\d+\.\d+\.\d+$` — what
`manifest-llm-gateway` uses — would silently track experimental builds.

As of 2026-09-03:

| reference      | digest               | origin                                    |
| -------------- | -------------------- | ----------------------------------------- |
| `latest`       | `sha256:1cbd4233…`   | built from `exp-v0.52.264`, 2026-08-26     |
| `experimental` | `sha256:1cbd4233…`   | same digest as `latest`                   |
| `0.52.264`     | `sha256:1cbd4233…`   | same digest as `latest`                   |
| `0.52.113`     | `sha256:48ba6ee4…`   | newest stable tag, 2026-07-19             |

So `latest` currently serves an experimental build. The release workflow intends
otherwise (`type=raw,value=latest,enable=<is_stable>`), and the workflow at the
revision that image was built from (`e168b67e`) is identical — which points at
`docker/metadata-action`'s default `flavor: latest=auto` combined with the
unanchored `type=match` pattern, which also matches *inside* `exp-v0.52.264`.
Worth reporting upstream; it affects everyone pulling `:latest`.

### 2. The stable channel has been silent for six weeks

1,273 three-part `v*` tags and 264 `exp-v*` tags exist. Historically almost
every patch was tagged stable (up to eight a day). Since `v0.52.0` the project
moved to experimental-first with occasional promotion, and since `v0.52.113`
(2026-07-19) no stable tag has been cut at all, while experimental ran on to
`exp-v0.52.264` (2026-08-26).

Decision 2 therefore ships a July build. That is the accepted side of the trade:
it costs currency and buys that nothing reaches the ArgoCD-pinned clusters that
the upstream has not itself promoted. **If the stable channel stays silent, this
decision needs revisiting** — see the open questions.

### 3. A persistent `/app` produces silent stale dependencies

The root path syncs `/apptoo` → `/app` with `rsync -av` and **no `--delete`**.
`/app/venv` and the marker file `/app/venv/.deps_installed` therefore survive an
image upgrade, and changed requirements are never reinstalled. This is the whole
reason for decision 3.

### 4. Watch paths decide whether the drift check can ever say "clean"

`api/config.py` changes almost daily. Putting it in `-watch-paths` makes every
sync a `review` and the automation pointless. The split that resolves it:

- **`charts.rgielen.de/upstream-watch-paths`** — the *image contract* the
  deployment depends on: `Dockerfile`, `docker_init.bash`, `requirements.txt`,
  `docker-compose.yml`.
- **`charts.rgielen.de/upstream-config-sources`** — what the application
  *reads*: `api/config.py`, `api/auth.py`, `api/routes.py`. These go to
  `chart_audit.py` only, which reports and blocks nothing.

### 5. Reaching the UI is equivalent to having a shell

The WebUI executes agent tools and browses and writes files in the workspace. An
Ingress in front of it without authentication is open remote code execution. The
upstream only warns; the chart must `fail` at render time when the service is
exposed (Ingress, HTTPRoute, `LoadBalancer` or `NodePort`) and none of
`auth.password`, `auth.oidc.issuer` or `auth.existingSecret` is set.

---

## Phases

The numbering is a real order. Phase 0 can still change the shape of phases 1–3,
and Phase 5 only makes sense once a chart exists to run the tooling against.

### Phase 0 — verify in kind, before writing any chart

Eight assumptions carry the rest. Measure them with a hand-written pod manifest,
no chart involved. `crane`, `helm-docs` and `ct` are missing on this workstation
and degrade silently — fetch the CI-pinned versions into the scratchpad first
(see `[[local-chart-toolchain-missing]]` in `.claude/memory/`).

| id  | check                                                                                                                                                 |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| V1  | Rootless start: `runAsNonRoot`, `runAsUser: 1024`, `fsGroup: 1024`, `WANTED_UID`/`WANTED_GID` set explicitly. Does the server come up?                  |
| V2  | `readOnlyRootFilesystem: true` with `emptyDir` on `/app`, `/uv_cache`, `/tmp`. Does anything still need `/home/hermeswebui` writable?                   |
| V3  | Measure start-up duration (`uv venv` plus two packages). The result is the `startupProbe.failureThreshold` budget.                                      |
| V4  | Behaviour of `/health` during start-up — connection refused or 503? Decides whether startup and readiness probes share a definition.                    |
| V5  | SIGTERM: does the server exit cleanly, and how long does it take? The result is `terminationGracePeriodSeconds`.                                        |
| V6  | PVC ownership on k3s `local-path` with `fsGroup`: does the auto-detection find the expected UID?                                                        |
| V7  | Set a deliberately wrong `runAsUser` and reproduce the hard abort. It is the justification for coupling the values in the template.                     |
| V8  | Start without PyPI egress (NetworkPolicy) and record the failure mode, so it is recognisable the first time it happens in production.                   |

**Abort criteria.** If V2 fails, `readOnlyRootFilesystem` is not a default and
the README's security claim shrinks. If V1 fails, the chart depends on the root
entrypoint and its recursive `chown` across the PVC — stop and re-discuss before
building further.

### Phase 1 — chart skeleton, `version: 1.0.0`

- `Chart.yaml`: `apiVersion: v2`, `type: application`, `version: 1.0.0`,
  `appVersion: "0.52.113"`, the four upstream annotations plus the new
  stable-channel annotation from Phase 5.
- `templates/`: Deployment, Service, Secret, ConfigMap, PVC, ServiceAccount,
  Ingress, HTTPRoute, `NOTES.txt`, `tests/test-health.yaml`, `extra-objects.yaml`.
- **No `replicaCount` value.** One replica is a property of the program, not a
  default. A value with exactly one valid setting is an invitation to data loss.
- `updateStrategy: Recreate`, hardcoded, for the same reason.
- Volumes: PVC for `HERMES_HOME` (on by default), workspace as
  PVC / `existingClaim` / `emptyDir`, plus `emptyDir` for `/app`, `/uv_cache`
  and `/tmp`, each with its own `sizeLimit`.
- `values.schema.json` for everything with a constrained shape — auth mode,
  storage sizes, the OIDC block.

Done when `helm template` renders, `ct lint --config ct.yaml --all` is green and
the pod becomes Ready in kind.

### Phase 2 — the values surface

Not all 108 variables get modelled. Model what an operator has to touch in a
cluster; everything else stays reachable through `extraEnv` and is named as such
in the README.

```yaml
# Sketch — the structure, not the full set.
webui:
  port: 8787              # HERMES_WEBUI_PORT (host is fixed at 0.0.0.0)
  hermesHome: /data       # HERMES_HOME
  stateDir: ""            # HERMES_WEBUI_STATE_DIR, empty = $HERMES_HOME/webui
  defaultWorkspace: /workspace
  auth:
    existingSecret: ""    # the GitOps path; takes precedence over everything below
    password: ""          # HERMES_WEBUI_PASSWORD
    oidc: {issuer, clientId, clientSecret, allowClaim, allowValues}
    cookieName: ""
    secure: ""            # HERMES_WEBUI_SECURE
  proxy:                  # everything that matters behind an Ingress
    trustForwardedFor: false
    trustForwardedProto: false
    trustedProxyCidrs: []
    allowedOrigins: []
    sseChunked: false     # for buffering reverse proxies
  agent:                  # no deployment, only the wiring
    dir: ""               # HERMES_WEBUI_AGENT_DIR
    autoInstall: false
  gateway:                # optional: an agent running elsewhere in the cluster
    apiUrl: ""            # HERMES_API_URL
    apiKey: ""
```

Every key carries a comment, and where it maps onto an upstream variable the
comment names it. Those comments are the published documentation.

### Phase 3 — the safety net and the agent recipe

- **The guard.** `fail` at render time on an exposed service without
  authentication. The message states the reason, not just the condition.
- **Secrets.** Password, OIDC client secret and gateway key come from a chart
  Secret or from `existingSecret` — never generated. A cookie signing key that
  changes on every ArgoCD sync throws away every session; see
  `[[never-generate-secrets-in-charts]]`.
- **Ingress.** Document controller annotations for SSE — buffering off, generous
  read timeout — as an example, not as a default.
- **Adding the agent.** `docker_init.bash` looks for the source at exactly two
  paths, `$HERMES_HOME/hermes-agent` and `/opt/hermes`, and installs it
  automatically when it is there. An operator mounts it to one of them through
  `extraVolumes`/`extraVolumeMounts`. Put the full, copyable recipe in the
  README together with the warning that start-up then takes minutes and pulls
  unpinned packages from PyPI.

### Phase 4 — documentation and CI

- `README.md.gotmpl` with `chart.aboutSection` and `chart.usageSection`. Without
  the file helm-docs renders every section twice — see
  `[[helm-docs-template-concatenation]]`.
- A `## Environment variable mapping` section: mandatory, because
  `chart_audit.py` reads exactly that heading to compare the chart against its
  own documentation.
- A security section that states plainly what access to the UI means.
- `ci/default-values.yaml` (minimal, password set, no persistence),
  `ci/full-values.yaml` (Ingress, persistence, proxy trust, OIDC block),
  `ci/no-auth-values.yaml` (not exposed, to exercise the guard from the
  permitted side).
- **No `ci/fixtures/`.** The chart needs no backing service — the most pleasant
  difference from `manifest-llm-gateway`. The agent stays out of CI; 950 MB per
  run is not worth it, and `ct.yaml` passes `--timeout 600s`, which a standalone
  start meets comfortably and an agent install would not.
- `helm test` against `/health`.

### Phase 5 — toolchain (the real work)

- **`upstream_sync.py`, channel filter.** New annotation, e.g.
  `charts.rgielen.de/upstream-stable-ref: refs/tags/v{version}`. The source
  repository is already in the image label `org.opencontainers.image.source`
  that `upstream_diff.py` reads. A single `git ls-remote --tags` yields the set
  of stable tags; candidates not in it are dropped. **Not** an HTTP request per
  candidate — with 1,401 image tags that is not affordable.
- **`chart_audit.py`, Python extractor.** The current one understands
  `.env.example` lines and `process.env.X`. Add `os.getenv("X")`,
  `os.environ.get("X")` and `os.environ["X"]`.
- **Backwards compatibility is part of the task.** Both changes must leave
  `manifest-llm-gateway` behaving exactly as it does today; a chart without the
  new annotation keeps the current behaviour.
- Commit the two script changes separately from the chart, so a later bisect can
  tell the two causes apart.

### Phase 6 — release

Merging to `main` packages and publishes. The chart page on `gh-pages` is the
canary: if the version in `Chart.yaml` is not among the published ones, the page
says so in a banner. Then check that the GHCR package is public — it was
immediate last time, but that is not something to rely on (see
`[[publishing-is-verified]]`). Only then set `targetRevision` in `k3s-nuc` and
`k3s-ze`.

Both clusters are single-node: every chart change that forces a pod restart is a
short, real outage — longer than usual here, because the restart reinstalls the
dependencies.

---

## Explicitly out of scope

| excluded                  | why                                                                                                                                       |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Deploying the Hermes Agent | Second upstream with its own versioning scheme, no compatibility contract between the two, 950 MB pull. Replaced by the documented recipe. |
| Building our own image     | This repository builds no applications. An own image would be permanent maintenance and a second security inheritance.                     |
| More than one replica      | SQLite and JSON sessions on ReadWriteOnce. Not offering the knob is more honest than offering it with a warning.                           |
| Shipping a NetworkPolicy   | The pod needs egress to PyPI and to the LLM providers. A shipped policy would be either ineffective or broken; describe it instead.        |
| Automerging upstream PRs   | Only once the watch paths actually produce `clean` in practice. Until then the sync opens a pull request and holds it.                     |

---

## Open questions

1. If the stable channel stays silent, the chart ships 0.52.113 indefinitely. At
   what point is that untenable, and what is the answer then — wait, switch
   channel, or withdraw the chart?
2. Do we report the `latest=auto` finding upstream? It affects everyone pulling
   `:latest`, not just us.
3. Workspace default: own PVC, `emptyDir`, or none at all? Depends on whether
   the WebUI should work on real project data, and what that means in the
   cluster.

---

## Re-verifying the facts above

```sh
# Stable versus experimental git tags, without hitting the API rate limit.
git ls-remote --tags https://github.com/nesquena/hermes-webui.git \
  | awk '{print $2}' | sed 's|refs/tags/||; s|\^{}||' | sort -u

# Which digest a reference resolves to, and the labels behind it.
crane digest ghcr.io/nesquena/hermes-webui:latest
crane config ghcr.io/nesquena/hermes-webui:0.52.113 | jq '.config.Labels'
```
