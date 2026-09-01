---
name: manifest-migration-paths
description: Manifest has two independent migration paths with different multi-replica hazards; only one has a lock and only one has a CLI
metadata:
  type: reference
---

Findings from reading and running `manifestdotbuild/manifest` 6.19.1 on 2026-09-01. They
are why `manifest-llm-gateway` 2.0.0 migrates from a hook Job.

**Path 1 — TypeORM migrations.**
`packages/backend/dist/database/migrate.js` is present in the image and runs standalone
(`node packages/backend/dist/database/migrate.js`, `DATABASE_URL` is enough, exits 0). It
wraps the run in `pg_advisory_lock(4011985)` and reads `MIGRATION_DATABASE_URL` →
`DATABASE_UNPOOLED_URL` → `DATABASE_URL`, in that order, because the lock is
session-scoped and a transaction pooler would not preserve it.

The boot path (`RUN_MIGRATIONS_ON_BOOT` → TypeORM `migrationsRun`) does **not** take that
lock — `runMigrationsWithAdvisoryLock` is called only from `migrate.js`.

**Running several `migrate.js` at once against a database with pending migrations
deadlocks.** Observed with three concurrent runners on an empty database, hung
indefinitely: one holds the advisory lock and is executing
`CREATE INDEX CONCURRENTLY ... agent_messages ...`, which waits for every session with a
visible virtual XID — including the two blocked on the advisory lock, which wait for the
holder. PostgreSQL does not report this as a deadlock and does not break it. So the Job
must be the *only* migration runner: hook Job plus `runMigrationsOnBoot: false`, never an
initContainer per replica.

**Path 2 — Better Auth migrations.**
`DatabaseSeederService.runBetterAuthMigrations` creates Better Auth's tables through kysely
on module init. No lock, no CLI, so the Job cannot cover it. On a first install with more
than one replica the pods race on those `CREATE TABLE`s: one exits 1 and is restarted, then
succeeds. Self-correcting, and rolling upgrades avoid it because `maxSurge: 1` starts one
new pod at a time.

**How to apply:** if a future upstream release adds a Better Auth migration CLI, fold it
into the same Job. Until then the chart documents the first-install restart rather than
pretending it does not happen.
