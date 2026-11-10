# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope

This file — and this team — covers **`task-tracker/`** only, inside the parent
`arch-info-system-monorepo`. Siblings `core/`, `reference-manager/`, `keycloak/`, `infra/`,
`planning-system/`, `qa/`, and `reports/` are owned by other teams; don't assume their
conventions apply here, and don't add monorepo-wide guidance to this file. The monorepo has
hundreds of commits of sibling-team work (270+ on `main` as of this pass, growing every review
round) that this file doesn't track in detail — when a cross-team claim here matters, re-read
that team's current docs on `main` rather than trusting a stale summary or a stale commit count.

## Start here

`AGENTS.md` in this directory is the contributor guide: stack, build/test commands, doc style,
commit conventions. `README.md` has the quick-start (`docker compose up --build`, URLs, demo
accounts: `member`/`lead`/`admin`, password `demo12345`). Read both before making changes — this
file adds context they don't cover rather than repeating it. Work directly off `main` — there is
no reason to use the old `task-tracker/base-realization` branch, which is a stale snapshot main
has since fast-forwarded far past: besides the original "address review feedback" round, **two
more full rounds have since landed** — PR #174 (`task-tracker/clean-architecture-refactor`: Work
Items/Collaboration/Iterations rebuilt onto `domain`/`application`/`infrastructure` layers) and
PR #177 (`task-tracker/task-tracker-review-2026-11-01`: bulk operations, work-item links, saved
views, overdue notifications, a real S3 attachment store, and a real Kafka outbox). Both are
described in detail below and in `docs/review-2026-11-01.md` — don't assume the file list or
layering you remember from before either PR is still what's on `main`.
`scripts/check.sh` is the repo's own one-shot local verification (compose config for both
compose files, backend `mvn test checkstyle:check`, frontend lint/test/build, `git diff --check`)
— run it instead of re-deriving the check sequence by hand.

## What this is

Task-tracker is a team task-management system: backlog, kanban board, iterations, work-item
decomposition, comments, time tracking, file attachments, audit history, notifications, and
Excel import/export. A real, working **local-release** implementation exists in `backend/` and
`frontend/` (below) — no longer an early/base cut: two review rounds (PR #174, #177) have since
added bulk status/assignee/iteration edits, work-item links (BLOCKS/RELATED), browser-local saved
filter views, overdue highlighting + notification, real browser-URL navigation, a real S3-backed
attachment store, and a real Kafka outbox — see "Real implementation" and "What's solid" below.
It's still not production-ready (see "Known gaps"): several cross-team contracts (Planning's
project/epic ownership, the Kafka topic shape, auth mechanism with Infra's real broker) remain
unsigned, so parts of what's *implemented* are explicitly flagged in `docs/review-2026-11-01.md`
and `166.infrastructure-s3-kafka.md` as not yet usable against the shared stand. As of the
01.10.2026 addendum to `vision.md`/`system-requirements.md`, **Project and Epic are no longer
task-tracker's own data** — see "Planning System now owns Project/Epic" below, which is still
the single biggest scope change since the initial implementation and is **still** not reflected
in the running code (confirmed unchanged as of PR #177 — `WorkItemService.createAs` still accepts
human-created `PROJECT`/`EPIC`).

## Real implementation (`backend/`, `frontend/`)

- **`backend/`** — Java 21 + Spring Boot 4 (webmvc, JDBC, Security/OAuth2 resource server,
  Actuator), PostgreSQL via plain `JdbcTemplate` (no JPA/Hibernate), Liquibase running two SQL
  files (`001-initial.sql`, `002-review.sql`) for the whole schema, Apache POI for real `.xlsx`
  export/import. **The architecture is now a deliberate hybrid, not uniform** — don't assume
  either style applies everywhere:
  - **Work Items, Collaboration, Iterations** are on Clean Architecture: `domain/` (pure entities,
    `WorkItemFactory`, no Spring/JDBC) → `application/{workitem,iteration,collaboration}/`
    (one use case per operation) → `application/port/` (repository/permission interfaces) →
    `infrastructure/{persistence,security,event}/` (`Jdbc*Repository`, `PermissionPortAdapter`,
    Spring `ApplicationEventPublisher`-based domain events). `WorkItemController`/
    `IterationController` depend on the use cases, not on any service class.
  - **Admin, Directory, Excel, and the `/bugs`+`/reports/*` integration endpoints** are still the
    original flat style: `AdminService`/`ExcelService`/`DirectoryService`/`IntegrationController`
    talk to `JdbcTemplate` directly, one class per concern, no layering. This is intentional
    strangler-fig sequencing, not neglect — don't "fix" it by partially migrating one method.
  - **PR #177's new features** (`BulkController`, `LinkController`, `Outbox`, `ObjectStorage`,
    `OverdueJob`) are new top-level classes in the flat root package (not filed under
    `application/`/`infrastructure/`), but they *do* depend on the Clean Architecture ports and
    use cases where one already existed (`BulkController` calls `UpdateWorkItem`/
    `AddWorkItemToIteration`/`RemoveWorkItemFromIteration` through `WorkItemRepository`/
    `PermissionPort`; `LinkController` uses `WorkItemRepository`/`PermissionPort`/
    `EventPublisherPort`). If you add the next feature in this area, match that pattern — reuse
    the ports, don't reintroduce raw `JdbcTemplate` permission checks — but don't assume you must
    also create a new `application/` subpackage just to add one controller.
- **`Outbox.java`** — Kafka producer + Postgres-backed transactional outbox (`event_outbox` table
  from `002-review.sql`). Publishes on every `DomainEvent` the Work Items/Iterations use cases
  raise, normalizing most of them into `WorkItemFieldsChanged` (diff + version) — only
  `WorkItemCreated`, `TimeLogged`, `IterationActivated`/`IterationCompleted`, and
  `WorkItemHardDeleted` get their own payload shape (see `135.event-catalog.md`'s "Исполняемый
  срез" section for the exact list; comments/attachments/links/membership changes are **not**
  separate event types yet, despite being named in the target catalog). Sends up to 20
  events/5s, retries every 30s, **DEAD after 5 attempts** (blocks that aggregate until an admin
  calls `POST /api/v1/admin/outbox/{id}/retry`, `GET .../admin/outbox` to list). No Kafka
  transactional/DLQ support — PostgreSQL is the only durable retry source. Topic
  `task-tracker.events.v1` is hard-coded; with no `KAFKA_BOOTSTRAP_SERVERS` set, the producer is
  simply `null` and events accumulate in `event_outbox` forever (no cleanup job for `SENT` rows
  either). **Known blocker, not yet resolved**: the code hard-codes SASL `SCRAM-SHA-512`, but
  Infra's actual bootstrap (`infra/scripts/kafka-init.sh`) only enables `PLAIN` — connecting to
  the shared broker needs one side to change first (see `166.infrastructure-s3-kafka.md` §3).
- **`ObjectStorage.java`** — S3-backed attachment storage (AWS SDK v2, path-style, region fixed to
  `us-east-1`, no STS/session tokens). With `S3_ENDPOINT` unset, attachments stay `bytea` in
  Postgres exactly as before. Setting it **automatically starts migrating existing bytea rows**
  in the background (10 rows/30s: upload → download-back → SHA-256 verify → null out `content`) —
  back up the DB first, and know that turning `S3_ENDPOINT` back off afterward does *not* bring
  migrated content back into `bytea`. Deletes go through an `object_cleanup` queue (populated by
  a DB trigger on attachment delete, swept once a minute, with a 1-hour grace window for
  in-flight uploads) rather than deleting synchronously.
- **`BulkController.java`** (`POST /api/v1/work-items/bulk`) — up to 100 unique `{id,version}`
  pairs, one `PROPAGATION_REQUIRES_NEW` transaction per item so one card's failure/stale-version
  conflict never rolls back the others; reuses `UpdateWorkItem`'s and the iteration use cases'
  existing permission/validation rules rather than re-implementing them.
- **`LinkController.java`** (`/api/v1/work-items/{id}/links`) — `BLOCKS` (directed, cycle-checked
  via a recursive CTE) and `RELATED` (symmetric, canonicalized to the lexicographically-smaller
  UUID as `source_id` so the same pair can't be linked twice in reverse); only `TASK`/`BUG`/
  `SUBTASK` can be linked (not `PROJECT`/`EPIC`); a link doesn't widen read access to the other
  side — listing silently skips a linked item the caller can't read.
- **`OverdueJob.java`** — hourly cron (`Europe/Moscow`), flags unfinished (`status.category =
  'OPEN'`), assigned, past-`due_date` items; notifies once per `(work_item_id, due_date,
  assignee_id)` via a `PRIMARY KEY`-deduplicated `overdue_delivery` table, so re-running the job
  (or a due-date edit and revert) can't double-notify the same combination. Still goes through
  the old `ChangeRecorder.notify`, not a domain event — this flow was never migrated.
- **`frontend/src/`** — React 19 + TypeScript + Vite, `oidc-client-ts` for the Keycloak
  authorization-code flow, now also `react-router-dom` (`BrowserRouter` in `main.tsx`). This is
  the **real app** — distinct from `frontend/prototype/` (the static click-through mock, still
  present and untouched, see below). `App.tsx` is a slim nav/layout shell (not "every screen" —
  that was true before PR #174's frontend refactor split it into `screens/`/`components/`/
  `hooks/`); it now derives `screen`/`selected` from the URL instead of local state, so
  `/work-items/{id}`, `/board`, `/iterations` etc. are real deep-linkable addresses, survive
  reload, and participate in browser back/forward. Login preserves the originally-requested path
  across the Keycloak redirect via `sessionStorage['returnTo']`. `api.ts` holds the fetch wrapper
  (`ApiError` now carries `status`/`errors`/`correlationId`, not just a message string) and the
  OIDC `UserManager`; `AttachmentFrame.tsx` is a sandboxed `<iframe>` wrapper added specifically so
  previewing an HTML/text attachment can't execute scripts (see `docs/security-check.md`).
  `BulkActions.tsx`, `SavedViews.tsx` (filters saved to `localStorage`, namespaced per
  `issuer+userId` — no server sync, no cross-device sharing), and `components/Links.tsx` are new,
  deliberately kept local to the screens that use them rather than folded into `hooks/`.
  `frontend/e2e/tracker.spec.ts` is a **separate** Playwright suite (`npm run test:e2e`, not part
  of `npm test`/`vitest`) that drives a real Keycloak login against a real running stand —
  needs `TRACKER_E2E_URL` (and optionally `TRACKER_E2E_USER`/`PASSWORD`, `TRACKER_CHROME_PATH`);
  it is not run by `scripts/check.sh` and has no default target to run against.
- **`compose.integrations.yaml`** — optional standalone Kafka (`apache/kafka`, single
  broker/controller combo, PLAINTEXT) + MinIO (built from `../infra/images/minio`, bootstrapped
  with a one-shot `mc mb` sidecar) overlay: `docker compose -f compose.yaml -f
  compose.integrations.yaml up --build -d`. This is for exercising the S3/Kafka code paths
  locally only — it does **not** stand in for the shared Infra stand's auth (PLAINTEXT here vs.
  the SASL_SSL/SCRAM the shared broker needs) or TLS.
- **`dev/keycloak-realm.json`** — demo realm imported by the `keycloak` service in
  `compose.yaml`: three human users (`member`/`lead`/`admin`) whose subject UUIDs exactly match
  what `DirectoryService`'s dev seeder inserts into `user_cache` + `local_access` when
  `DEV_DIRECTORY=true` — that's why `docker compose up --build` gives a working, already-
  permissioned app with no manual setup. Confidential service clients `testing-client`/
  `reports-client`/**`qa-tracker-reader`** carry the `testing-service`/`reports-service`/
  `qa-tracker-reader` client roles `AccessService` checks for the integration endpoints —
  `qa-tracker-reader` is QA's own read-only account (their Q-09), scoped to exactly
  `GET /work-items/{id}` + that item's comments (see `070.role-matrix.md` and
  `162.integration-spec.md`'s QA section); the review doc for PR #177 confirms this wasn't
  touched/expanded in that round. A `planning-service` client role is already named in
  `070.role-matrix.md`'s prose and in `openapi.yaml`, but has no corresponding code path or realm
  entry yet — the Planning endpoints in `openapi.yaml` are spec-only (below).
- **`docs/implementation-decisions.md`** — the concrete answers chosen **for this local release**
  to `system-requirements.md`'s §11 open questions. Read it before assuming an "open question"
  from `system-requirements.md` is still genuinely undecided in code — several have a concrete
  answer here even though `system-requirements.md §11` itself hasn't been edited to mark them
  resolved. It's explicit that Planning/Kafka remain *target* integrations pending agreement, not
  settled exclusions — don't cite "local release doesn't need Kafka" as if it were a closed
  decision; it's a stopgap, and `162.integration-spec.md` (below) is where that's tracked.
- **`docs/security-check.md`** — a dated security-review record (PR #129, 12.10.2026) with
  a reproduction section (`mvn checkstyle:check test`, `npm run lint/test/build`, `npm audit`,
  `docker compose config --quiet`). It's explicit about what it *didn't* verify in *that*
  environment (no Docker daemon there) and names NFR-003 as still only `partial` — that was true
  of that session, not a standing fact about every environment (see "Known gaps" below). Treat
  its "ограничения" column as a live to-do list, not resolved risk.

### Planning System now owns Project/Epic — code hasn't caught up

The 01.10.2026 addendum (`vision.md`, `system-requirements.md`, `020.system-context.md`,
`050.entities.md`, `070.role-matrix.md`, ADR-008 in `145.architecture-decisions.md`) reassigns
**Project and Epic** to Planning System as master: it pushes a versioned plan via (target, not yet
implemented) `PUT /api/v1/planning/projects/{externalId}`, task-tracker keeps the operational
fields (status, description, priority, iteration, actuals) and a local projection bound by an
immutable `externalId` — `050.entities.md` says in plain words **"Создание проекта/эпика
человеком запрещено"** (human creation of Project/Epic is forbidden).

**The running code does not enforce this.** `WorkItemService.createAs`/`Values.type` still accept
`type=PROJECT`/`EPIC` from any caller with plain `item.create` (i.e. any MEMBER or LEAD), exactly
like before the addendum — there is no Planning-only gate, no `planning_binding` table (it's
listed only as a "proposed physical addition" in `120.data-model.md`, explicitly not migrated:
"Новая Liquibase-миграция в этот коммит не входит"), and the `/planning/projects/{externalId}`
endpoints exist only as a draft in `openapi.yaml` — `PlanningController`/`PlanningService` don't
exist. If you're asked to implement Planning System integration, this is the actual starting
line: schema (`planning_binding`, `event_outbox` per 120's proposed table), a service, and a
`createAs`/`updateAs` change that rejects human `PROJECT`/`EPIC` creation outside that path. If
you're just fixing docs, don't "fix" this by softening 050/070's wording — the business rule is
correct and deliberate, the code is what's behind.

Field-shape-wise, what already exists lines up well: `openapi.yaml`'s `PlanEpic`/`PlanTask`
schemas (`title`, `startDate`, `dueDate`, `externalId`, optional `localWorkItemId` for first-time
manual binding) match field-for-field what Planning System's own `worker.py` already sends
(verified against their code in this pass) — that part of the contract is in good shape even
though nothing on our side reads it yet.

### The permission model is entirely DB-seeded, not hardcoded

`role_permission(role, permission, allowed)` and `local_access(external_user_id, role, allowed)`
in `001-initial.sql` are the real source of truth for who can do what. `AccessService.role()`
reads `local_access` (or short-circuits to `ADMIN` if the caller's JWT subject matches
`BOOTSTRAP_ADMIN_SUBJECT`), and `AccessService.require(permission)` checks `role_permission`.
Admins can change both at runtime via `/admin/access/{userId}` and
`/admin/permissions/{role}/{permission}` — `070.role-matrix.md` is the seed's source document and
the two match **exactly**, row for row, including the finer "own items/comments/attachments only"
rules for Участник. If you add a new permission-gated action: pick a `lower.case` permission
string, seed it for the right roles in `001-initial.sql`, call `access.require("...")` (or the
assignee-scoped `itemRead`/`itemWrite`) in the service method — there's no annotation-based
security layer here.

A brand-new deployment with an empty `local_access` table and no `BOOTSTRAP_ADMIN_SUBJECT` set
has **no way to ever create its first admin** through the API (chicken-and-egg: granting a role
itself requires `access.admin`). The dev compose setup sidesteps this with `DEV_DIRECTORY=true`'s
seeder; a real deployment needs `BOOTSTRAP_ADMIN_SUBJECT` set to a real IdP subject before first
use — not currently called out in `README.md`'s "running outside Docker" env-var list.

### "Backlog" is a query filter, not a status reset — don't "fix" it

Completing an iteration (`IterationService.complete`) only freezes `result_snapshot` and flips
`state`; it deliberately does **not** touch `work_item_iteration.removed_at` or any item's kanban
status. Unfinished items still satisfy `system-requirements.md`'s "return to the backlog" rule,
but structurally: both the current-iteration lookup in `WorkItemService.view()` and the
double-booking check in `IterationService.add()` filter on `iteration.state <> 'COMPLETED'`, so a
completed iteration's membership rows stop counting as "still committed" without being deleted —
which is what lets an unfinished item be re-planned into a new iteration while the old iteration's
historical composition stays intact (matches `120.data-model.md`'s "moving to the next iteration
must not destroy the completed one's data" rule). Don't add a bulk status-reset or
membership-clearing step on completion — that would violate history-preservation instead of
satisfying the backlog rule.

### Known gaps vs. the design docs

- **The Reference Manager directory adapter gap (previously the top item here) is now closed.**
  As of PR #177, `DirectoryService` does real paginated `GET /v1/employees` + `/v1/org_units`
  (`allowDeleted`, `pageSize`/`pageToken`, looping until `nextPageToken` is empty), derives
  team/department from `org_units.parent_id` chains (cycle-guarded), uses the now-real
  `account_user_id`, and treats `employment_state`/`account_state`/`is_deleted` as the three
  separate axes they actually are. The cache version is now a local SHA-256 hash of the fetched
  pages (Reference Manager's API has no snapshot version to echo). If you're told this adapter
  "still expects a unified snapshot," that's stale — verify against the current
  `DirectoryService.java` before repeating it.
- **Kafka auth mismatch blocks connecting to the shared broker — a concrete, named blocker, not
  just an unconfirmed proposal.** `Outbox.java` hard-codes `SCRAM-SHA-512` whenever a JAAS config
  is supplied; Infra's real bootstrap (`infra/scripts/kafka-init.sh`) only enables `PLAIN`. Only
  one `KAFKA_SASL_JAAS_CONFIG` env var is read — there's no mechanism-selection, so this can't be
  worked around from the task-tracker side without a code change. See
  `166.infrastructure-s3-kafka.md` §3 for the exact ask to Infra (add a SCRAM listener + SCRAM
  credentials for principal `task_tracker`) and what task-tracker would need to do instead if
  Infra keeps PLAIN-only.
- **Kafka topic name/granularity disagreement (DEC-TT-02) is still open, but the outbox shipped
  anyway with the topic hard-coded.** `task-tracker.events.v1` (3 segments) is now live in
  `Outbox.java` even though `infra/vision.md` wants a 4-segment `<env>.<domain>.<event>.v1` and
  Planning System's docs assume five separate per-event-type topics — shipping the code did not
  resolve the naming disagreement, and `166.infrastructure-s3-kafka.md` is explicit that "создание
  топика не является согласованием бизнес-контракта." Don't treat the outbox's existence as
  evidence DEC-TT-02 is settled.
- **`120.data-model.md`'s *implemented* ER diagram is behind `001-initial.sql` *and* now also
  behind `002-review.sql`.** Beyond the pre-existing gaps (`severity`/`environment`/
  `test_run_url`/`test_case_url`/`version` on `WORK_ITEM`; `STATUS`/`PRIORITY`'s real column
  names), `002-review.sql` added `work_item_link`, `event_outbox`, `object_cleanup`,
  `overdue_delivery`, and `attachment.object_key`/`sha256` — none of these are in 120's diagram.
  120's "Предлагаемые физические дополнения" section (which named `event_outbox`/MinIO fields as
  *proposed*) is now partly stale in the other direction: those specific tables exist for real,
  just not with 120's exact proposed shape. Trust the two `changelog` SQL files over 120 either
  way.
- **Backend test coverage is now substantially broader** (58 tests per `docs/review-2026-11-01.md`,
  up from the ~49 the clean-architecture pass left): `BulkControllerTest` (duplicate/invalid
  entries, partial success), `ReviewIntegrationTest` (outbox retry-preserves-eventId, overdue job
  re-run, directory second-page failure), and `JdbcWorkItemRepositoryTest` gained a links
  cycle/duplicate-reverse-link case. Two tests talk to real external protocol endpoints and are
  **skipped unless you set env vars**: `TRACKER_KAFKA_TEST_BOOTSTRAP` (real send) and
  `TRACKER_S3_TEST_ENDPOINT` (Moto S3-compatible server) — don't read a green `mvn test` as proof
  those two ran unless you confirm the vars were set. Iteration lifecycle and hierarchy-validation
  unit coverage (the original gap this bullet flagged) is now covered by the clean-architecture
  pass's use-case tests (`AddWorkItemToIterationTest`, `WorkItemFactoryTest`, etc.) — this bullet
  no longer needs to flag that part as thin.
- **MinIO's actual runtime image is still unverified; only the S3 protocol is.** Per
  `docs/review-2026-11-01.md`: "Runtime MinIO из образа Infra отдельно не подтверждён: его
  исходная сборка требует загрузки Go-зависимостей; S3-протокол проверен на Moto." Don't treat
  `ObjectStorage`'s test coverage as proof it works against Infra's real MinIO build.
- **Environments vary — don't assume this sandbox has no JDK/Maven/Docker without checking.** An
  earlier pass of this file asserted that as a standing fact; it isn't one — both the
  clean-architecture and the 2026-11-01 review rounds ran `mvn test`, `docker compose up`, and
  Playwright successfully in their respective sessions (the latter: 58 backend tests including
  real Postgres via Testcontainers, frontend lint/test/build, 4 live Playwright scenarios,
  `docker compose config --quiet` on both compose files). If tools seem missing, check for a
  Homebrew-installed JDK/Maven not yet on `PATH` before concluding they're absent.
- `AGENTS.md` still cites two-digit requirement IDs (`NFR-03`, `FR-IT-05`, `BR-08`) against the
  real three-digit IDs in `095.requirements-check.md` (`NFR-003`, …) — pre-existing, known,
  intentionally left alone.
- The `162.integration-spec.md` registry's target dates (И-M2 16.10.2026, И-M3 19.10.2026) have
  now passed with no confirmation recorded on any DEC-TT row — flagged explicitly in that doc as
  of this pass rather than left silently stale. If you're asked to update 162 again, check
  whether any DEC-TT row has since gotten a real answer before re-flagging it as overdue.

### What's solid

RBAC matches `070.role-matrix.md` exactly. Hard delete is a real atomic transaction blocked on
children, and the resulting notification correctly keeps a denormalized snapshot
(`work_item_public_id`, `work_item_title`) with a nulled FK instead of disappearing (NFR-005).
Every mutating call wraps its data change + audit entry + notification in one `@Transactional`
method (ADR-007). Bug creation from the testing service is deduplicated with a Postgres advisory
lock around the check-then-insert, so concurrent retries with the same external defect ID can't
race into two rows. `openapi.yaml` documents every real controller route — verified 1:1 against
the Java controllers — and its draft Planning schemas already match Planning System's real
client code field-for-field (see above). Excel import validates every row before committing any
of them and rolls back the whole batch on a single error. Server-side length limits now exist for
free-text fields (`Values.checkLength`: 255 for title/name, 50000 for description, 10000 for
comment body) and `hours`/`plannedHours` reject anything above `9999999999.99`, closing a
previously-unaddressed input-validation gap.

PR #177's additions hold up under the same bar: bulk edits run each item in its own
`REQUIRES_NEW` transaction with an explicit version check, so one stale/invalid card in a batch
of 100 can't roll back or block the others. Link creation takes a dedicated advisory lock and
canonicalizes `RELATED` pairs to avoid duplicate reverse links, and checks `BLOCKS` cycles with a
recursive CTE before inserting. The overdue job's notification table has a `(work_item_id,
due_date, assignee_id)` primary key, so re-running the hourly cron (or an edit-then-revert of
`due_date`) can't double-notify. The S3 attachment migration verifies a round-trip SHA-256 before
clearing the `bytea` column, and object deletion goes through a DB-trigger-populated cleanup
queue rather than an immediate, potentially-rolled-back delete. Navigation is now real browser
URLs with OIDC-redirect-safe return paths, verified live end-to-end with Playwright against a
real Keycloak login (not just unit-tested).

## Spec docs: system-requirements.md is senior, vision.md must match it

- `docs/system-requirements.md` is the authoritative, detailed spec: exact fields, business
  rules, interface/data requirements, acceptance criteria. When it and `vision.md` disagree,
  **system-requirements.md wins** — fix vision.md (or flag the conflict) rather than treating
  vision.md's version as current. Both carry an identical "Дополнение по замечаниям 01.10.2026"
  section (Keycloak confirmed, Planning System ownership, MinIO, Reference Manager collections) —
  keep any future addendum duplicated in both files the same way, not added to just one.
- `docs/vision.md` is the higher-level product narrative built on top of system-requirements.md.
  Historically it has drifted ahead of or behind system-requirements.md during rewrites (e.g.
  Excel once briefly disappeared from vision.md and had to be re-added) — the fix is always to
  resync both, never to let one silently win by accident.
- Neither doc has `FR-*`/`BR-*`/`NFR-*` requirement-ID labels (stripped in commit `b8cc8e6`, not
  reintroduced; `AGENTS.md` still uses the old two-digit convention, see "Known gaps"). Working
  IDs for traceability live in `block-d-verification/095.requirements-check.md`: 15 FR / 9 NFR /
  10 BR, matching vision.md's bullet counts — re-count both sides if either doc changes again.
  PR #177 added five more FR IDs directly in `system-requirements.md`'s own "Дополнения по
  разбору 01.11.2026" section (`FR-BULK-01`, `FR-VIEW-01`, `FR-LINK-01`, `FR-OVERDUE-01`,
  `FR-NAV-01`, each with its own acceptance criteria), with matching verification entries added
  to `095.requirements-check.md` — these are the exception to "no FR labels in the prose," not a
  sign the stripping decision was reversed project-wide.

### Structured design docs

`docs/block-a-context-and-scope/` through `docs/block-i-integration-and-deployment/` hold the
course-project-style document set defined by `docs/documents-composition.md` (block A–I, numbered
docs 010–165, one subfolder per block). `120.data-model.md` and the Reference Manager/Kafka
sections of `162.integration-spec.md` are the known exceptions to "kept in sync" — see "Known
gaps" above. Cross-block links use `../block-x-name/NNN.filename.md`; same-block links stay bare
filenames.

`block-i-integration-and-deployment/162.integration-spec.md` is the single most useful doc for
cross-team work: it's a dated registry (`DEC-TT-01`…`07`) of exactly what's proposed vs. confirmed
with each neighboring team, with target dates. Update it (not scattered mentions elsewhere) when
a cross-team fact changes, and check its registry rows before asserting a cross-team question is
either open or settled.

### Live UI/UX prototype

`frontend/prototype/` is a separate, static HTML/CSS/JS click-through mock (own `README.md`, plus
a `CHECKLIST.md` added since) for `block-e-ui-ux-design/115.live-prototype.md` — **not** related
to the real `frontend/src/` app beyond sharing a directory root. Treat it as a frozen UI/UX
reference artifact, not a WIP version of the real app.

## Integration points owned by other teams

The app here integrates with the rest of the monorepo but doesn't own any of this. Everything
below reflects a full cross-team doc pass (reading each neighbor's current `main`), not just our
own side's assumptions — re-verify against their docs again if much time has passed.

- **Auth** — Keycloak OIDC is now the *uniformly adopted* choice across every task-tracker doc
  (ADR-003, `020`/`030`, the system-requirements/vision addendum) — no more "provider TBD"
  hedging anywhere in this subsystem's docs as of this pass. That said, it's still a
  **task-tracker-local** Keycloak instance/realm (`dev/keycloak-realm.json`, standalone, named
  `arch-info-system`), not the shared one. `infra/vision.md` plans exactly one shared Keycloak
  realm (also named `arch-info-system`) for every team, but documents no migration path or ETA
  for folding our standalone dev realm into it — don't assume that's coming soon.
- **Delivery / Infra** — task-tracker's `compose.yaml` still runs its *own* Postgres and Keycloak,
  not the shared stack `infra/` is designing. But as of PR #177 there's now a real, concrete
  integration surface with Infra beyond that: `166.infrastructure-s3-kafka.md` is a full
  connection request (S3 bucket/ACL, Kafka topic/ACL, TLS truststores, env vars) with one **named
  blocker** — Infra's Kafka bootstrap enables `PLAIN` SASL, task-tracker's `Outbox` hard-codes
  `SCRAM-SHA-512`, and nothing on either side currently makes them compatible (see "Known gaps").
  MinIO bucket naming (`arch-dev-task-tracker`) matches infra's convention; infra's actual bucket
  policy (`task-tracker.json`, grants `s3:*` on the bucket) is wider than task-tracker's own
  minimal ask (`PutObject`/`GetObject`/`DeleteObject` only) — functional but not tightened yet.
  Infra's MinIO image build (Go deps) hasn't been verified to actually run; only the S3 wire
  protocol has (via Moto in tests).
- **Reference Manager (org/user data)** — **integration is now real, not just planned.**
  `DirectoryService` consumes their actual `/v1/employees` + `/v1/org_units` (cursor-paginated,
  `allowDeleted`), and `account_user_id` — flagged as recently as the clean-architecture pass as
  "not implemented yet on their side" — is now real and is what task-tracker keys human accounts
  on. `employment_state`/`account_state`/`is_deleted` are read as the three separate axes they
  actually are (see "Known gaps" for the history of that distinction). If anything downstream
  still assumes the old single-snapshot shape or `show_deleted`, that's the stale thing, not this
  note.
- **Reports** — wants a **hybrid**: the same Kafka topic/key/dedup shape we propose
  (`task-tracker.events.v1`, `aggregateId`, dedup by `eventId` — matches exactly, and as of PR
  #177 this Kafka side is now actually implemented in `Outbox.java`, not just proposed — though
  see the SCRAM/PLAIN blocker above before assuming Reports can connect to it on the shared
  stand) *and* the REST pull API we've implemented
  (`/reports/{work-items,iterations,time-logs,statuses,history}` — `/reports/history` with
  `periodFrom`/`periodTo`/paging up to 500 is new in PR #177, added specifically for Reports).
  Their documented polling interval for the REST stopgap is **5 minutes**, not 60 seconds — our
  docs said 60s for both Reports and QA until this pass; that was wrong for Reports specifically
  (fixed in `162.integration-spec.md`/`160.integration-plan.md`/`implementation-decisions.md`).
  They treat our `severity` field as non-authoritative (QA's system owns severity in their model)
  and resolve the Project/Epic master conflict the same way we now do (Planning System as master).
- **Testing service (QA)** — `POST /bugs`'s field shape matches QA's own docs exactly, severity
  scale conversion included (QA's Blocker/Critical/Major/Minor/Trivial → our
  critical/high/medium/low, pending our confirmation under DEC-TT-04). QA's separate read-only
  account request (their Q-09) is now wired up: client `qa-tracker-reader` in
  `dev/keycloak-realm.json`, checked by `AccessService.itemReadOrQa`
  (`PermissionPort.requireItemReadableOrQa` in the Clean Architecture layer) — it bypasses
  `local_access`/`role_permission` entirely (it's a client role, not a human role) and only
  covers `GET /work-items/{id}` plus that item's comments; list/search, history, time logs,
  attachments, and every write still go through the normal checks and reject it. QA separately
  expects milestone/release context to come from Planning System, not from us — nothing for
  task-tracker to build there; `162.integration-spec.md`'s DEC-TT-04 row has our (unconfirmed)
  proposal that Planning System should be the source for that.
- **Planning System** — see "Planning System now owns Project/Epic" above; it's the most
  consequential of these integrations and the only one with a confirmed field-shape match already
  in place (`openapi.yaml` vs. their `worker.py`) despite zero corresponding backend code here yet.
