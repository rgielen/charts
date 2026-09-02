# manifest-llm-gateway

![Version: 2.2.1](https://img.shields.io/badge/Version-2.2.1-informational?style=flat-square) ![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square) ![AppVersion: 6.20.0](https://img.shields.io/badge/AppVersion-6.20.0-informational?style=flat-square)

Manifest, the self-hosted LLM gateway, proxy and dashboard.

**Homepage:** <https://manifest.build>

[Manifest](https://manifest.build) is a self-hosted gateway in front of the LLM providers
you already pay for. It gives you one OpenAI-compatible endpoint, a dashboard for keys,
routing and fallbacks, and a record of what was actually sent and returned.

This chart follows the upstream Docker Compose deployment
([`docker/docker-compose.yml`](https://github.com/mnfst/manifest/blob/main/docker/docker-compose.yml),
[`docker/.env.example`](https://github.com/mnfst/manifest/blob/main/docker/.env.example))
closely enough that a Compose install maps onto it one setting at a time — see the
[environment variable mapping](#environment-variable-mapping) below. It carries over the
same container hardening: a read-only root filesystem, all capabilities dropped, no
privilege escalation, an in-memory `/tmp`, and the same 1 GiB memory ceiling.

Two things are deliberately different from Compose:

- **The chart does not deploy PostgreSQL.** `manifest.database.url` points at a database
  you run — an operator such as CloudNativePG, a managed instance, or a plain StatefulSet.
  A bundled single-replica database is a worse deal in Kubernetes than in Compose: it hides
  the backup and the major-version upgrade, which are the two things you actually need to
  own. Migrations still run by themselves when the application boots.
- **The chart never generates secrets.** See [Secrets](#secrets).

Not included, on purpose: no NetworkPolicy (a gateway needs egress to every provider on
the internet, so the policy would be decorative), no PodDisruptionBudget and no
HorizontalPodAutoscaler (the default is a single replica, and scaling out has real
prerequisites — see [High availability](#high-availability)). The
Compose file's `pids_limit: 512` has no pod-level equivalent and is a node setting in
Kubernetes.

## Installation

From the Helm repository:

```bash
helm repo add rgielen https://rgielen.github.io/charts
helm repo update
helm install my-manifest-llm-gateway rgielen/manifest-llm-gateway --version 2.2.1
```

Or directly from the OCI registry:

```bash
helm install my-manifest-llm-gateway oci://ghcr.io/rgielen/charts/manifest-llm-gateway --version 2.2.1
```

## Source Code

* <https://github.com/mnfst/manifest>
* <https://github.com/rgielen/charts>

## Values

### Workload

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| affinity | object | `{}` | Affinity rules for pod assignment. |
| containerSecurityContext | object | `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"readOnlyRootFilesystem":true}` | Container-level security context. Mirrors the `read_only`, `cap_drop: ALL` and `no-new-privileges` hardening of the upstream compose file. The compose file's `pids_limit: 512` has no pod-level equivalent in Kubernetes and is configured on the node instead. |
| fullnameOverride | string | `""` | Overrides the full name of the generated resources. |
| livenessProbe | object | `{"failureThreshold":3,"httpGet":{"path":"/api/v1/health","port":"http"},"periodSeconds":30,"timeoutSeconds":5}` | Liveness probe. |
| nameOverride | string | `""` | Overrides the chart name used in resource names. |
| nodeSelector | object | `{}` | Node selector for pod assignment. |
| podAnnotations | object | `{}` | Extra annotations for the pod. |
| podDisruptionBudget | object | `{"enabled":false,"maxUnavailable":1,"minAvailable":""}` | Voluntary-disruption budget. Off by default because it does nothing useful for a single replica and actively blocks node drains for one; with more than one replica you want it, and the install notes say so. |
| podDisruptionBudget.enabled | bool | `false` | Create a PodDisruptionBudget. |
| podDisruptionBudget.maxUnavailable | int | `1` | Maximum unavailable pods. |
| podDisruptionBudget.minAvailable | string | `""` | Minimum available pods. Takes precedence over `maxUnavailable` when set. |
| podLabels | object | `{}` | Extra labels for the pod. |
| podSecurityContext | object | `{"fsGroup":65532,"runAsGroup":65532,"runAsNonRoot":true,"runAsUser":65532,"seccompProfile":{"type":"RuntimeDefault"}}` | Pod-level security context. UID/GID 65532 is the user the upstream image already runs as. |
| priorityClassName | string | `""` | Priority class for the pod. |
| readinessProbe | object | `{"failureThreshold":3,"httpGet":{"path":"/api/v1/health","port":"http"},"periodSeconds":10,"timeoutSeconds":3}` | Readiness probe. The health endpoint answers 503 while the process drains on SIGTERM, which takes the pod out of the Service before it stops. |
| replicaCount | int | `1` | Number of application replicas. More than one needs S3-backed request recordings rather than a ReadWriteOnce volume, and has consequences for rate limiting and threshold alerts that the chart cannot fix — read the high-availability section of the chart README before raising it. |
| resources | object | `{"limits":{"memory":"1Gi"},"requests":{"cpu":"100m","memory":"512Mi"}}` | Resource requests and limits. No CPU limit on purpose: CFS throttling on a streaming proxy shows up directly as a worse time-to-first-token. The memory limit mirrors the `mem_limit: 1g` of the upstream compose file. |
| serviceAccount | object | `{"annotations":{},"automountServiceAccountToken":false,"create":true,"name":""}` | Service account used by the pod. |
| serviceAccount.annotations | object | `{}` | Annotations for the service account. |
| serviceAccount.automountServiceAccountToken | bool | `false` | Mount the service account token. The application never calls the Kubernetes API, so this stays off. |
| serviceAccount.create | bool | `true` | Create a dedicated service account. |
| serviceAccount.name | string | `""` | Name of the service account. Generated from the release name when empty. |
| startupProbe | object | `{"failureThreshold":36,"httpGet":{"path":"/api/v1/health","port":"http"},"periodSeconds":5}` | Startup probe. Generous by design: a cold start runs database migrations and warms the pricing cache, which the upstream compose file gives 90 seconds. |
| terminationGracePeriodSeconds | int | `30` | Grace period for the pod to finish in-flight requests. Keep this above `manifest.shutdownDrainMs` (which is milliseconds), or the kubelet kills the process mid-drain. |
| tmpDir | object | `{"sizeLimit":"64Mi"}` | Size of the in-memory `/tmp` volume. The container runs with a read-only root filesystem, so `/tmp` has to be mounted separately. |
| tolerations | list | `[]` | Tolerations for pod assignment. |
| topologySpreadConstraints | list | `[]` | Topology spread constraints for pod assignment. |
| updateStrategy | object | `Recreate` with a ReadWriteOnce volume, surge-first `RollingUpdate` otherwise | Deployment update strategy. Left empty, the chart picks one: `Recreate` while `persistence.enabled` uses a ReadWriteOnce claim the replicas cannot share, and a surge-first `RollingUpdate` (`maxUnavailable: 0`) otherwise — which is what keeps a multi-replica install available across an upgrade. |

### Extensibility

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| extraEnv | list | `[]` | Extra environment variables, in Kubernetes `env` form. Applied last, so they override everything the chart sets — the escape hatch for upstream settings this chart does not model, such as `FRAME_ANCESTORS`. |
| extraEnvFrom | list | `[]` | Extra `envFrom` sources, applied after the chart's own ConfigMap and Secret but before `extraEnv`. |
| extraObjects | list | `[]` | Extra manifests to render alongside the chart. Each entry is a full Kubernetes object and is passed through `tpl`. |
| extraVolumeMounts | list | `[]` | Extra volume mounts for the container. |
| extraVolumes | list | `[]` | Extra volumes for the pod. |

### Networking

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| httpRoute | object | `{"annotations":{},"enabled":false,"hostnames":[],"matches":[{"path":{"type":"PathPrefix","value":"/"}}],"parentRefs":[]}` | Gateway API route, as an alternative to `ingress`. Requires the `gateway.networking.k8s.io/v1` CRDs in the cluster. |
| httpRoute.annotations | object | `{}` | Annotations for the HTTPRoute. |
| httpRoute.enabled | bool | `false` | Create an HTTPRoute. |
| httpRoute.hostnames | list | `[]` | Hostnames to match. |
| httpRoute.matches | list | `[{"path":{"type":"PathPrefix","value":"/"}}]` | Rule matches. The default sends everything below `/` to the service. |
| httpRoute.parentRefs | list | `[]` | Gateways to attach to. Each entry is a `parentRef` and is passed through unchanged (`name`, and optionally `namespace`, `sectionName`, `port`). |
| ingress | object | `{"annotations":{},"className":"","enabled":false,"hosts":[],"tls":[]}` | Ingress for the dashboard and the gateway API. Both live on the same port and the same host. |
| ingress.annotations | object | `{}` | Annotations for the Ingress. Streaming responses need a generous read timeout on the controller; the values differ per controller. |
| ingress.className | string | `""` | Ingress class name. |
| ingress.enabled | bool | `false` | Create an Ingress. |
| ingress.hosts | list | `[]` | Hosts to serve. Each entry takes `host` and a list of `paths` (`path`, `pathType`). |
| ingress.tls | list | `[]` | TLS configuration, passed through unchanged. |
| service | object | `{"annotations":{},"port":2099,"type":"ClusterIP"}` | Service in front of the pods. |
| service.annotations | object | `{}` | Annotations for the service. |
| service.port | int | `2099` | Service port. |
| service.type | string | `"ClusterIP"` | Service type. |

### Image

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| image | object | `{"pullPolicy":"IfNotPresent","repository":"manifestdotbuild/manifest","tag":""}` | Image to deploy. The upstream publishes linux/amd64 and linux/arm64. |
| image.pullPolicy | string | `"IfNotPresent"` | Image pull policy. |
| image.repository | string | `"manifestdotbuild/manifest"` | Image repository. |
| image.tag | string | the chart's `appVersion` | Image tag. |
| imagePullSecrets | list | `[]` | Secrets used to pull the image from a private registry. |

### Manifest: core

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| manifest.apiKey | string | `""` | Optional key for programmatic access through the `X-API-Key` header (`API_KEY`). The dashboard uses cookie sessions and agents use their own `mnfst_*` keys, so this is only needed for scripting the admin API. |
| manifest.auth.encryptionKey | string | `""` | Separate at-rest encryption key for stored provider API keys and OAuth tokens (`MANIFEST_ENCRYPTION_KEY`). Falls back to `auth.secret` when empty, which means one leaked session cookie secret also decrypts every stored provider credential. Set a second, independent 32+ character value. **Changing this makes existing stored credentials unreadable.** |
| manifest.auth.secret | string | `""` | Session signing secret (`BETTER_AUTH_SECRET`), at least 32 characters. Generate with `openssl rand -hex 32`. Required unless `existingSecret` provides it — the chart refuses to render without one. It is never generated for you: this chart is meant to be rendered by ArgoCD, where `lookup` returns nothing and a generated value would be different on every sync, taking every stored provider credential with it. |
| manifest.corsOrigins | list | `[]` | Extra browser origins allowed to call the gateway (`WINGMAN_CORS_ORIGINS`). Joined with commas. |
| manifest.disableHsts | bool | `false` | Silence the boot warning about the missing HSTS header on a plain-http deployment (`MANIFEST_DISABLE_HSTS`). Prefer a real `https://` `publicUrl` anywhere reachable from the internet. |
| manifest.existingSecret | string | `""` | Name of an existing Secret holding sensitive settings. Its keys are the upstream environment variable names (`BETTER_AUTH_SECRET`, `DATABASE_URL`, `EMAIL_API_KEY`, ...) and it is mounted with `envFrom`. Takes precedence over the plain values below, which makes it the right choice for GitOps: keep the Secret in sealed-secrets or external-secrets and leave the values here empty. |
| manifest.mode | string | `"selfhosted"` | Deployment mode (`MANIFEST_MODE`). `selfhosted` relaxes the SSRF rules so private and plain-http provider URLs are allowed. Set explicitly rather than left to auto-detection, exactly as the upstream compose file does. `local` is the upstream's legacy alias for `selfhosted` and behaves identically; prefer `selfhosted` for anything new. |
| manifest.port | int | `2099` | Port the application listens on (`PORT`). |
| manifest.publicUrl | string | derived from the first `ingress.hosts` entry when an Ingress is enabled | Public URL the dashboard is reached at (`BETTER_AUTH_URL`). Must match what the browser actually uses, or logins and OAuth callbacks break. No trailing slash — the application appends paths such as `/api/auth/...` to this value. Serve it over https wherever it is reachable from the internet: the application only sends HSTS for an `https://` origin. |

### Manifest: LLM proxy

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| manifest.credits.autoProvisionAllowlist | list | `[]` | User e-mail addresses allowed to auto-provision, joined with commas (`CREDITS_AUTO_PROVISION_ALLOWLIST`). |
| manifest.credits.baseUrl | string | `""` | Base URL of the managed free-provider service (`CREDITS_BASE_URL`). |
| manifest.credits.geminiFreeMaxBudget | string | `""` | Budget in USD for each generated key (`CREDITS_GEMINI_FREE_MAX_BUDGET`). |
| manifest.credits.masterKey | string | `""` | Master key enabling automatic virtual-key provisioning (`CREDITS_MASTER_KEY`). |
| manifest.ollamaHost | string | `""` | Base URL of a locally reachable Ollama or other OpenAI-compatible server (`OLLAMA_HOST`), for example `http://ollama.ai.svc.cluster.local:11434`. Empty by default rather than the compose file's `host.docker.internal`, which does not exist in Kubernetes. |
| manifest.proxy.codexSemanticOutputTimeoutMs | int | `60000` | Time in ms to wait for deliverable text or tool output from ChatGPT Codex (`CODEX_SEMANTIC_OUTPUT_TIMEOUT_MS`). |
| manifest.proxy.concurrencyMax | int | `10` | Per-tenant limit of concurrent in-flight requests per backend process (`MANIFEST_CONCURRENCY_MAX`). |
| manifest.proxy.providerTimeoutMs | int | `180000` | Per-attempt timeout in ms for upstream provider requests (`PROVIDER_TIMEOUT_MS`). Keep it below your client's timeout so the fallback chain still has room to run. |
| manifest.proxy.streamIdleTimeoutMs | int | `180000` | Maximum silence in ms between two chunks of an upstream streaming response before the request fails with HTTP 504 (`STREAM_IDLE_TIMEOUT_MS`). Distinct from `streamWarmupMs`, which only covers the wait for the *first* chunk: raise this one for agent workloads that think for a long time between tokens. |
| manifest.proxy.streamWarmupMs | int | `15000` | Time in ms to wait for the first chunk of a streaming response before treating it as stalled and failing over (`STREAM_WARMUP_MS`). |

### Manifest: database

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| manifest.database.authPoolMax | int | `5` | Size of the separate pool Better Auth opens (`AUTH_DB_POOL_MAX`). |
| manifest.database.migrationUrl | string | `""` | Direct, non-pooled connection string used only for migrations (`MIGRATION_DATABASE_URL`). Falls back to `database.url` when empty, which is right whenever that is already a direct connection. Set it when `database.url` points at a transaction pooler such as PgBouncer: the migration runner takes a *session*-scoped PostgreSQL advisory lock, and transaction pooling does not preserve one. |
| manifest.database.poolMax | int | `10` | Size of the application's connection pool (`DB_POOL_MAX`). |
| manifest.database.tuneSession | string | `""` | Statements applied to each new session (`DB_TUNE_SESSION`). |
| manifest.database.url | string | `""` | PostgreSQL connection string (`DATABASE_URL`), for example `postgresql://manifest:secret@postgres.databases.svc:5432/manifest`. Required unless `existingSecret` provides it. Special characters in the password must be percent-encoded. This chart does not deploy a database; migrations are applied by the application on boot. |

### Manifest: email and OAuth

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| manifest.email.apiKey | string | `""` | API key for the provider (`EMAIL_API_KEY`). |
| manifest.email.domain | string | `""` | Verified sending domain (`EMAIL_DOMAIN`). Mailgun only. |
| manifest.email.from | string | `""` | Sender address (`EMAIL_FROM`). |
| manifest.email.provider | string | `""` | E-mail provider (`EMAIL_PROVIDER`): `resend`, `mailgun` or `sendgrid`. Without one, signup verification is waived, password reset silently does nothing, and threshold alerts only work where a user configured a provider in the dashboard. |
| manifest.oauth | object | `{"discord":{"clientId":"","clientSecret":""},"github":{"clientId":"","clientSecret":""},"google":{"clientId":"","clientSecret":""}}` | OAuth logins. A provider activates as soon as both its client ID and secret are set. Register the callback as `<publicUrl>/api/auth/callback/<provider>`. |
| manifest.oauth.discord.clientId | string | `""` | `DISCORD_CLIENT_ID` |
| manifest.oauth.discord.clientSecret | string | `""` | `DISCORD_CLIENT_SECRET` |
| manifest.oauth.github.clientId | string | `""` | `GITHUB_CLIENT_ID` |
| manifest.oauth.github.clientSecret | string | `""` | `GITHUB_CLIENT_SECRET` |
| manifest.oauth.google.clientId | string | `""` | `GOOGLE_CLIENT_ID` |
| manifest.oauth.google.clientSecret | string | `""` | `GOOGLE_CLIENT_SECRET` |
| manifest.providerOauth | object | `{"minimaxClientId":"","openaiClientId":""}` | Overrides for the OAuth clients Manifest uses to talk to LLM providers on a user's behalf. Only needed if you registered your own apps instead of using the ones shipped with Manifest. |
| manifest.providerOauth.minimaxClientId | string | `""` | `MINIMAX_OAUTH_CLIENT_ID` |
| manifest.providerOauth.openaiClientId | string | `""` | `OPENAI_OAUTH_CLIENT_ID` |

### Manifest: operations

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| manifest.migrations.job | object | `{"activeDeadlineSeconds":900,"annotations":{},"backoffLimit":3,"enabled":true,"podAnnotations":{},"resources":{"limits":{"memory":"512Mi"},"requests":{"cpu":"100m","memory":"256Mi"}},"serviceAccountName":""}` | Apply migrations from a `pre-install`/`pre-upgrade` hook Job instead of on application boot. The Job runs the upstream's own migration entry point, which wraps the run in a PostgreSQL advisory lock, and it runs exactly once per release — so the schema is in place before any pod starts, and a failed migration is a failed Job with readable logs rather than a pod stuck in CrashLoopBackOff. |
| manifest.migrations.job.activeDeadlineSeconds | int | `900` | Hard timeout for the whole Job. A first migration on an empty database builds every index and is not instant. |
| manifest.migrations.job.annotations | object | `{}` | Extra annotations for the Job object. |
| manifest.migrations.job.backoffLimit | int | `3` | Retries before the Job is considered failed. |
| manifest.migrations.job.enabled | bool | `true` | Create the migration Job. |
| manifest.migrations.job.podAnnotations | object | `{}` | Extra annotations for the migration pod. |
| manifest.migrations.job.resources | object | `{"limits":{"memory":"512Mi"},"requests":{"cpu":"100m","memory":"256Mi"}}` | Resource requests and limits for the migration pod. |
| manifest.migrations.job.serviceAccountName | string | `""` | Service account for the migration pod. Empty uses `default`, because the chart's own service account does not exist yet when a `pre-install` hook runs. Point this at a pre-existing account when the migration pod needs an identity of its own — a cloud workload identity for a managed database, say. When `serviceAccount.create` is false, the configured account already exists and is used automatically. |
| manifest.runMigrationsOnBoot | bool | `false` | Also apply migrations when the application boots (`RUN_MIGRATIONS_ON_BOOT`). Off, because `migrations.job` already did it. Turning it on with more than one replica is refused: the boot path does not take the advisory lock the Job's entry point takes, and one pending migration is a `CREATE INDEX CONCURRENTLY` that waits for the other replicas' sessions while those wait for the lock — a cycle PostgreSQL does not detect and does not break. |
| manifest.shutdownDrainMs | int | `10000` | Grace period in ms to finish in-flight requests after SIGTERM (`SHUTDOWN_DRAIN_MS`). Keep `terminationGracePeriodSeconds` above it. |
| manifest.throttle.limit | int | `100` | Maximum requests per window per client (`THROTTLE_LIMIT`). |
| manifest.throttle.ttl | int | `60000` | Rate limit window in ms (`THROTTLE_TTL`). |

### Manifest: request recordings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| manifest.recordings.filesystemPath | string | `"/data/request-recordings"` | Mount path for locally stored recordings (`REQUEST_RECORDING_FILESYSTEM_PATH`). Backed by `persistence` above. |
| manifest.recordings.retentionDays | string | `""` | Retention in days (`REQUEST_RECORDING_RETENTION_DAYS`). The application defaults to 365 for self-hosted installations. |
| manifest.recordings.s3.accessKeyId | string | `""` | Access key ID (`REQUEST_RECORDING_S3_ACCESS_KEY_ID`). |
| manifest.recordings.s3.bucket | string | `""` | Bucket name (`REQUEST_RECORDING_S3_BUCKET`). |
| manifest.recordings.s3.endpoint | string | `""` | Endpoint for S3-compatible storage (`REQUEST_RECORDING_S3_ENDPOINT`). |
| manifest.recordings.s3.forcePathStyle | bool | `false` | Use path-style addressing (`REQUEST_RECORDING_S3_FORCE_PATH_STYLE`). Needed by MinIO and most other S3-compatible backends. |
| manifest.recordings.s3.region | string | `""` | Region (`REQUEST_RECORDING_S3_REGION`). |
| manifest.recordings.s3.secretAccessKey | string | `""` | Secret access key (`REQUEST_RECORDING_S3_SECRET_ACCESS_KEY`). |
| manifest.recordings.storage | string | `"auto"` | Where message bodies are stored (`REQUEST_RECORDING_STORAGE`): `auto` picks S3 when a complete S3 configuration is present and the local volume otherwise. Metadata always lives in the database; only the bodies are affected by this. |

### Manifest: observability

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| manifest.sentry.dsn | string | `""` | Sentry DSN (`SENTRY_DSN`). Sentry stays completely uninitialised while this is empty. Error capture only — no tracing, request bodies, headers or user data. |
| manifest.sentry.environment | string | `""` | Environment tag (`SENTRY_ENVIRONMENT`). |
| manifest.sentry.release | string | `""` | Release tag (`SENTRY_RELEASE`). |
| manifest.telemetry.disabled | bool | `false` | Disable the anonymous usage report the upstream sends once per 24h (`MANIFEST_TELEMETRY_DISABLED`). Aggregates only: no prompts, no message contents, no API keys. |
| manifest.telemetry.endpoint | string | `""` | Send the report to your own collector instead (`TELEMETRY_ENDPOINT`). |

### Persistence

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| persistence | object | `{"accessModes":["ReadWriteOnce"],"annotations":{},"enabled":false,"existingClaim":"","size":"5Gi","storageClass":""}` | Persistent volume for locally stored request recordings, mounted at `manifest.recordings.filesystemPath`. Not needed when recordings go to S3, and not needed at all if you do not record message bodies. |
| persistence.accessModes | list | `["ReadWriteOnce"]` | Access modes for the created claim. |
| persistence.annotations | object | `{}` | Annotations for the created claim. |
| persistence.enabled | bool | `false` | Create and mount a PersistentVolumeClaim. |
| persistence.existingClaim | string | `""` | Use an existing claim instead of creating one. |
| persistence.size | string | `"5Gi"` | Size of the created claim. |
| persistence.storageClass | string | `""` | Storage class. Empty uses the cluster default. |

## Quick start

Generate two independent secrets and hand them to the chart out of band:

```bash
kubectl create namespace manifest

kubectl --namespace manifest create secret generic manifest-llm-gateway \
  --from-literal=BETTER_AUTH_SECRET="$(openssl rand -hex 32)" \
  --from-literal=MANIFEST_ENCRYPTION_KEY="$(openssl rand -hex 32)" \
  --from-literal=DATABASE_URL='postgresql://manifest:...@postgres.databases.svc:5432/manifest'

helm --namespace manifest install manifest rgielen/manifest-llm-gateway \
  --set manifest.existingSecret=manifest-llm-gateway \
  --set manifest.publicUrl=https://manifest.example.com \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=manifest.example.com \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix
```

On first boot the setup wizard at `/setup` creates the admin account — there are no
default credentials. Add a provider, copy the generated harness key (it starts with
`mnfst_`), and point any OpenAI-compatible client at `https://manifest.example.com/v1`.

## Secrets

Sensitive settings can be given two ways:

- `manifest.existingSecret` — the name of a Secret whose **keys are the upstream
  environment variable names** (`BETTER_AUTH_SECRET`, `MANIFEST_ENCRYPTION_KEY`,
  `DATABASE_URL`, `EMAIL_API_KEY`, `GOOGLE_CLIENT_SECRET`, …). It is mounted with
  `envFrom` and wins over anything set in values. This is the right choice for GitOps:
  keep the Secret in sealed-secrets or external-secrets and leave the values empty.
- Plain values (`manifest.auth.secret`, `manifest.database.url`, …) — the chart renders
  them into a Secret of its own. Convenient for a quick `helm install`, but they end up in
  your values file.

Set at least one of them. Without a session secret or a database URL the chart refuses to
render, with a message naming both ways out.

**The chart never generates a secret for you, and that is not an oversight.**
`MANIFEST_ENCRYPTION_KEY` — or `BETTER_AUTH_SECRET`, which it falls back to — encrypts
every stored provider API key and OAuth token at rest. ArgoCD renders charts with
`helm template` and no cluster access, where Helm's `lookup` returns nothing: a generated
value would come out different on every single sync, and every stored credential would
become undecryptable. The same reasoning applies to changing the key later — treat it as
permanent once credentials are stored.

Set `manifest.auth.encryptionKey` to a *second, independent* value rather than letting it
fall back. Otherwise one leaked session-signing secret also decrypts every provider
credential you have stored.

## Reverse proxy and `publicUrl`

`manifest.publicUrl` becomes `BETTER_AUTH_URL` and must match the URL the browser actually
uses, or logins and OAuth callbacks fail in ways that look like unrelated bugs. When an
Ingress is enabled and `publicUrl` is empty, the chart derives it from the first Ingress
host, using `https` if that host appears in `ingress.tls`.

Serve it over HTTPS anywhere reachable from the internet: the application only sends HSTS
for an `https://` origin and logs a warning on every boot otherwise. On an HTTP-only LAN
install, set `manifest.disableHsts=true` to silence that warning.

Streaming responses need a generous read timeout on the ingress controller. The annotation
differs per controller — for ingress-nginx it is
`nginx.ingress.kubernetes.io/proxy-read-timeout`, for Traefik it is a `ServersTransport`.

## Database

`manifest.database.url` is a standard PostgreSQL connection string. Percent-encode special
characters in the password (`@` → `%40`, `:` → `%3A`, `/` → `%2F`). Migrations are applied
by the chart — see [Database migrations](#database-migrations).

Back up the database, not the cluster: it holds accounts, provider credentials, harness
keys and request metadata.

## Request recordings

Message *metadata* always lives in the database. Recorded message *bodies* are separate and
optional, and go to one of two places:

- **A volume**, mounted at `manifest.recordings.filesystemPath`. Set `persistence.enabled`
  to back it with a PersistentVolumeClaim. Without it the mount is an `emptyDir` and the
  bodies are gone on every restart — the mount itself is always present because the root
  filesystem is read-only.
- **S3-compatible storage**, via `manifest.recordings.s3`. A complete S3 configuration
  takes precedence over the volume while `manifest.recordings.storage` is `auto`.

Retention defaults to 365 days upstream; override with
`manifest.recordings.retentionDays`.

## Database migrations

Migrations are applied by a `pre-install`/`pre-upgrade` hook Job that runs the upstream's
own migration entry point, not by the application on boot. The Job runs exactly once per
release, so the schema is in place before any pod starts, and a failed migration is a
failed Job with readable logs instead of a pod in `CrashLoopBackOff`. Its ConfigMap and
Secret are hook-scoped copies — a `pre-install` hook runs before the release's own
resources exist, and on upgrade the release's copies still hold the previous values.

`manifest.runMigrationsOnBoot` is off by default because of this. Turning it on alongside
more than one replica is refused outright, and that is not caution:

> The boot path applies migrations without the advisory lock the migration entry point
> takes. One pending migration is a `CREATE INDEX CONCURRENTLY`, which waits for every
> other session that can see the table — including the replicas blocked on the advisory
> lock, which are waiting for the holder, which is waiting for the index. PostgreSQL does
> not recognise this as a deadlock and does not break it. Observed hanging indefinitely
> with three concurrent runners against an empty database.

If `manifest.database.url` points at a transaction pooler such as PgBouncer, set
`manifest.database.migrationUrl` to a direct connection. The advisory lock is
session-scoped and transaction pooling does not preserve it.

**One migration path the Job cannot cover.** Besides the TypeORM migrations, the
application creates Better Auth's own tables on module init, through a separate code path
with no lock and no entry point of its own. On a *first* install with more than one
replica the pods race on those `CREATE TABLE`s: one exits with a duplicate-object error
and is restarted, then finds the tables in place and starts normally. The end state is
correct, and rolling upgrades never hit it because only one new pod starts at a time. To
avoid the restart entirely, install with `replicaCount: 1` and scale up afterwards.

## High availability

Single-node is not a requirement, and never was — a multi-node cluster with one replica
needs no special configuration. More than one *replica* is a different question.

What the chart handles:

- **Rollout strategy.** With no ReadWriteOnce volume in play it defaults to a surge-first
  `RollingUpdate` (`maxUnavailable: 0`), so an upgrade does not interrupt service. With
  `persistence.enabled` it falls back to `Recreate`, because a rolling update would wait
  forever for a claim the old pod still holds. Override with `updateStrategy`.
- **Migrations.** See above — the hook Job is what makes multiple replicas safe.
- **Recordings.** Configure `manifest.recordings.s3`; a ReadWriteOnce volume cannot be
  shared, and the chart refuses that combination rather than leaving pods `Pending`.
- **Disruption.** Set `podDisruptionBudget.enabled: true`. It is off by default because
  for a single replica it only blocks node drains.
- **Placement.** Nothing is spread across nodes unless you say so. This constraint is a
  no-op on a single-node cluster and spreads on a larger one:

  ```yaml
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: kubernetes.io/hostname
      whenUnsatisfiable: ScheduleAnyway
      labelSelector:
        matchLabels:
          app.kubernetes.io/name: manifest-llm-gateway
  ```

What the chart cannot fix, because it is upstream behaviour:

| | Effect with `n` replicas |
| --- | --- |
| Rate limiting | `THROTTLE_LIMIT` is enforced in memory, per pod. The effective limit is `n ×` the configured value, and a client can draw the full allowance from each pod. |
| Concurrency cap | `manifest.proxy.concurrencyMax` is per backend process, so the per-tenant ceiling multiplies the same way. |
| Threshold alerts | The hourly job checks "already sent?" and then sends, with no lock in between. The same alert can go out more than once. |
| Dashboard cache | A bounded in-memory LRU per pod, so two replicas can report different figures until the entries expire. Cosmetic. |

Recording retention cleanup is *not* on that list: it takes its own advisory lock upstream
and is safe across replicas.

If a strict global rate limit matters to you, enforce it at the ingress rather than
relying on `THROTTLE_LIMIT`.

## Upgrading

Chart `version` and `appVersion` move independently, and both appear in every release. New
upstream releases are picked up automatically: a scheduled workflow in this repository
watches the image, bumps `appVersion` and the chart `version` together, and opens a pull
request that merges itself once the chart still lints and installs.

Because a rollout restarts the single pod, an upgrade is a short outage on a single-node
cluster. Migrations run on boot; take a database backup first for anything that changes the
upstream major version.

## Use from ArgoCD

Always pin `targetRevision` to an explicit chart version:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: manifest
  namespace: argocd
spec:
  project: infrastructure
  source:
    repoURL: https://rgielen.github.io/charts
    chart: manifest-llm-gateway
    targetRevision: 2.2.1
    helm:
      valuesObject:
        manifest:
          existingSecret: manifest-llm-gateway
          publicUrl: https://manifest.example.com
        ingress:
          enabled: true
          hosts:
            - host: manifest.example.com
              paths:
                - path: /
                  pathType: Prefix
  destination:
    server: https://kubernetes.default.svc
    namespace: manifest
```

## Environment variable mapping

Every setting from the upstream `.env.example`, and where it lives here. Values marked
*secret* belong in `manifest.existingSecret` under exactly the environment variable name
in the left column.

| Environment variable | Value |
| -------------------- | ----- |
| `BETTER_AUTH_SECRET` | `manifest.auth.secret` *(secret)* |
| `MANIFEST_ENCRYPTION_KEY` | `manifest.auth.encryptionKey` *(secret)* |
| `PORT` | `manifest.port` |
| `HOST_BIND_ADDRESS`, `HOST_PORT` | not applicable — use `service` and `ingress` |
| `BETTER_AUTH_URL` | `manifest.publicUrl` |
| `MANIFEST_VERSION` | `image.tag`, defaulting to the chart's `appVersion` |
| `MANIFEST_MODE` | `manifest.mode` |
| `DATABASE_URL` | `manifest.database.url` *(secret)* |
| `POSTGRES_PASSWORD` | not applicable — the database is external |
| `DB_POOL_MAX`, `AUTH_DB_POOL_MAX`, `DB_TUNE_SESSION` | `manifest.database.poolMax`, `.authPoolMax`, `.tuneSession` |
| `RUN_MIGRATIONS_ON_BOOT` | `manifest.runMigrationsOnBoot`, off by default — see [Database migrations](#database-migrations) |
| `MIGRATION_DATABASE_URL` | `manifest.database.migrationUrl` *(secret)* |
| `REQUEST_RECORDING_STORAGE` | `manifest.recordings.storage` |
| `REQUEST_RECORDING_FILESYSTEM_PATH` | `manifest.recordings.filesystemPath` |
| `REQUEST_RECORDING_RETENTION_DAYS` | `manifest.recordings.retentionDays` |
| `REQUEST_RECORDING_S3_BUCKET` | `manifest.recordings.s3.bucket` |
| `REQUEST_RECORDING_S3_ENDPOINT` | `manifest.recordings.s3.endpoint` |
| `REQUEST_RECORDING_S3_REGION` | `manifest.recordings.s3.region` |
| `REQUEST_RECORDING_S3_FORCE_PATH_STYLE` | `manifest.recordings.s3.forcePathStyle` |
| `REQUEST_RECORDING_S3_ACCESS_KEY_ID` | `manifest.recordings.s3.accessKeyId` *(secret)* |
| `REQUEST_RECORDING_S3_SECRET_ACCESS_KEY` | `manifest.recordings.s3.secretAccessKey` *(secret)* |
| `PROVIDER_TIMEOUT_MS` | `manifest.proxy.providerTimeoutMs` |
| `STREAM_WARMUP_MS` | `manifest.proxy.streamWarmupMs` |
| `STREAM_IDLE_TIMEOUT_MS` | `manifest.proxy.streamIdleTimeoutMs` |
| `CODEX_SEMANTIC_OUTPUT_TIMEOUT_MS` | `manifest.proxy.codexSemanticOutputTimeoutMs` |
| `MANIFEST_CONCURRENCY_MAX` | `manifest.proxy.concurrencyMax` |
| `OLLAMA_HOST` | `manifest.ollamaHost` |
| `CREDITS_BASE_URL`, `CREDITS_AUTO_PROVISION_ALLOWLIST`, `CREDITS_GEMINI_FREE_MAX_BUDGET` | `manifest.credits.baseUrl`, `.autoProvisionAllowlist`, `.geminiFreeMaxBudget` |
| `CREDITS_MASTER_KEY` | `manifest.credits.masterKey` *(secret)* |
| `EMAIL_PROVIDER`, `EMAIL_DOMAIN`, `EMAIL_FROM` | `manifest.email.provider`, `.domain`, `.from` |
| `EMAIL_API_KEY` | `manifest.email.apiKey` *(secret)* |
| `GOOGLE_CLIENT_ID`, `GITHUB_CLIENT_ID`, `DISCORD_CLIENT_ID` | `manifest.oauth.<provider>.clientId` |
| `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_SECRET`, `DISCORD_CLIENT_SECRET` | `manifest.oauth.<provider>.clientSecret` *(secret)* |
| `OPENAI_OAUTH_CLIENT_ID`, `MINIMAX_OAUTH_CLIENT_ID` | `manifest.providerOauth.openaiClientId`, `.minimaxClientId` |
| `API_KEY` | `manifest.apiKey` *(secret)* |
| `MANIFEST_DISABLE_HSTS` | `manifest.disableHsts` |
| `WINGMAN_CORS_ORIGINS` | `manifest.corsOrigins` (a list; joined with commas) |
| `THROTTLE_TTL`, `THROTTLE_LIMIT` | `manifest.throttle.ttl`, `.limit` |
| `SHUTDOWN_DRAIN_MS` | `manifest.shutdownDrainMs` |
| `SENTRY_DSN` | `manifest.sentry.dsn` *(secret)* |
| `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE` | `manifest.sentry.environment`, `.release` |
| `MANIFEST_TELEMETRY_DISABLED`, `TELEMETRY_ENDPOINT` | `manifest.telemetry.disabled`, `.endpoint` |
| `SEED_DATA`, `NODE_ENV` | fixed, as in the upstream compose file |
| anything else | `extraEnv` |

Every variable is spelled out in full rather than abbreviated with a shared prefix, so
`.github/scripts/chart_audit.py` can check this table for completeness instead of guessing.

### Deliberately not modelled

The upstream reads these and this chart does not expose them. They are decisions, not gaps
— `extraEnv` reaches any of them if you disagree.

| Setting | Why not |
| ------- | ------- |
| `BACKFILL_DATABASE_URL` | The third fallback after `MIGRATION_DATABASE_URL`, which `manifest.database.migrationUrl` already sets, so the backfill resolver is already satisfied. Cloud-only besides. |
| `PLUGIN_OTLP_ENDPOINT` | Documented in the upstream's `.env.example` but read nowhere in the server. |
| `ERROR_PAGE_PUSH_SECRET` | Gates an internal endpoint for publishing curated error pages. Empty rejects every write, which is the right state for a self-hosted install. |
| `MANIFEST_PUBLIC_STATS` | Exposes aggregate `/api/v1/public/*` endpoints **without authentication**. The upstream marks it as being for its own marketing site. |
| `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `NOTIFICATION_FROM_EMAIL` | Legacy fallbacks superseded by the `EMAIL_*` settings above. Modelling both invites a configuration that contradicts itself. |
| `BIND_ADDRESS`, `NODE_ENV` | Already set inside the image. Overriding them only adds a way to break the deployment. |
| `CORS_ORIGIN`, `FRONTEND_PORT`, `MANIFEST_FRONTEND_DIR`, `MANIFEST_EMBEDDED` | Development-only; inert in a production image. |
| `STRIPE_SECRET_KEY`, `STRIPE_PRO_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`, `PLAN_LIMIT_FREE_REQUESTS`, `PLAN_LIMIT_PRO_REQUESTS`, `PLAN_REQUEST_QUOTA_RESET_AT`, `ANNOUNCE_APP_URL`, `DOCTOR_TUTORIAL_URL` | Billing and marketing for the hosted service. |
| `HOST_BIND_ADDRESS`, `HOST_PORT`, `MANIFEST_VERSION`, `POSTGRES_PASSWORD` | Compose-specific. Their Kubernetes equivalents are `service`, `ingress`, `image.tag` and your database's own configuration. |

A value left empty is not passed to the container at all. That matters: the application
reads several settings as `Number(env ?? default)`, where an empty string becomes `0`
rather than the documented default.

## Maintainers

| Name | Email | Url |
| ---- | ------ | --- |
| rgielen |  | <https://github.com/rgielen> |

----
_This file is generated by [helm-docs](https://github.com/norwoodj/helm-docs). Edit `values.yaml` comments, the chart's `README.md.gotmpl`, or the shared `.helm-docs.gotmpl` — not this file._

