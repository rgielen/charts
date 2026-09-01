# Calibration

What this chart is built on, what the drift being hunted actually looks like, and
how to tell a real gap from noise. Read before judging a candidate.

## The chart's load-bearing assumptions about the image

`chart_audit.py` checks each of these. They are here so a failure is
recognisable rather than merely red.

| Assumption | Where the chart depends on it | If it breaks |
| --- | --- | --- |
| `packages/backend/dist/database/migrate.js` exists | `templates/migration-job.yaml` runs it as the container argument | The pre-upgrade hook fails and blocks every release |
| Runs as UID 65532 | `podSecurityContext.runAsUser` | Pods fail to start, or run as the wrong user |
| Listens on 2099 | `manifest.port`, the Service, every probe | Probes fail, the rollout never becomes ready |
| Entrypoint is `node`, argument is a script path | The migration Job replaces the argument | The Job runs the server instead of migrating, and never exits |
| No shell in the image | The Helm test pod uses a separate curl image; probes are `httpGet`, never `exec` | Nothing breaks, but the reason for that design is gone and it can be simplified |
| `/api/v1/health` answers, and 503s while draining | All three probes | Readiness stops matching reality; drains cut connections |

## Three worked examples of the drift being hunted

**A pinned default moved, with no variable added or removed.** Between upstream
6.18.0 and 6.19.1, `DB_POOL_MAX` went 30 → 10 and `AUTH_DB_POOL_MAX` 10 → 5. The
chart pins both in `values.yaml`. No name-level diff notices this; only comparing
the upstream's default against the chart's pinned value does. **This is the
motivating case — look for it first.**

**A setting the upstream reads and documents nowhere.** `MIGRATION_DATABASE_URL`
is read by `packages/backend/src/database/datasource.ts` and appears in neither
`.env.example`. It matters: the migration entry point takes a *session*-scoped
advisory lock, which a transaction pooler does not preserve. Found only by reading
the source. `app.config.ts` is the authoritative list, not the examples.

**Behaviour with no configuration surface at all.** Better Auth's tables are
created on module init through a separate, unlocked code path with no CLI, so a
first install with several replicas races on `CREATE TABLE`. Nothing in any
`.env.example` hints at it. Changes like this show up in migration files and boot
services, not in configuration.

See the `manifest-migration-paths` project memory for the full findings.

## Classifying an unmodelled upstream setting

`chart_audit.py` reports every variable the upstream reads that the chart neither
emits nor documents. Most are legitimate omissions. Sort them:

- **Cloud-only** — billing, plans, marketing. `STRIPE_*`, `PLAN_LIMIT_*`,
  `ANNOUNCE_APP_URL`, `MANIFEST_PUBLIC_STATS`. Not for a self-hosted chart. Worth
  one line saying so, not a value.
- **Set by the image already** — `BIND_ADDRESS`, `NODE_ENV`. Emitting them again
  adds a way to break the deployment.
- **Development-only** — `CORS_ORIGIN`, `FRONTEND_PORT`, `MANIFEST_FRONTEND_DIR`,
  `MANIFEST_EMBEDDED`. Dead in a production image.
- **Legacy fallbacks** — `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`,
  `NOTIFICATION_FROM_EMAIL`. Superseded by the `EMAIL_*` path the chart models.
  Modelling both invites a configuration that contradicts itself.
- **Genuinely operational, and a real candidate** — anything touching timeouts,
  pools, storage, auth, migrations or the proxy path. `STREAM_IDLE_TIMEOUT_MS` and
  `BACKFILL_DATABASE_URL` are current examples.

A setting whose category you cannot determine is `uncertain`, not "probably
cloud-only".

## What the chart deliberately does not do

Do not propose these back. They were decided, with reasons:

- **No bundled PostgreSQL.** The database is external so its backup and major
  upgrade stay visible.
- **No generated secrets.** ArgoCD renders without `lookup`, so a generated value
  would rotate on every sync and take every stored provider credential with it.
- **No NetworkPolicy.** A gateway needs egress to every provider.
- **No distributed rate limiting.** The upstream's throttler is in-memory per
  process; a shared store would be upstream work, not chart work.
- **`runMigrationsOnBoot: false` with more than one replica is refused.** The boot
  path takes no advisory lock, and a pending `CREATE INDEX CONCURRENTLY` waits on
  the replicas blocked on that lock. Observed hanging indefinitely.

## Where the numbers live

- Pinned upstream defaults: `manifest.database.poolMax`, `.authPoolMax`,
  `manifest.proxy.*`, `manifest.throttle.*`, `manifest.shutdownDrainMs`,
  `manifest.migrations.job.activeDeadlineSeconds`.
- Enums that can go stale: `manifest.email.provider`,
  `manifest.recordings.storage`, `manifest.mode`.
- The mapping table in `README.md.gotmpl` is the chart's claim to be complete;
  every environment variable is spelled out in full so the audit can check it.
