# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope

This file — and this team — covers **`task-tracker/`** only, inside the parent
`arch-info-system-monorepo`. Siblings `core/`, `reference-manager/`, `keycloak/`, `infra/`,
`planning-system/`, `qa/`, and `reports/` are owned by other teams; don't assume their
conventions apply here, and don't add monorepo-wide guidance to this file. The monorepo now has
71+ commits of sibling-team work this file doesn't track in detail — when a cross-team claim
here matters, re-read that team's current docs on `main` rather than trusting a stale summary.

## Start here

`AGENTS.md` in this directory is the contributor guide: stack, build/test commands, doc style,
commit conventions. `README.md` has the quick-start (`docker compose up --build`, URLs, demo
accounts: `member`/`lead`/`admin`, password `demo12345`). Read both before making changes — this
file adds context they don't cover rather than repeating it. Work directly off `main` — there is
no reason to use the old `task-tracker/base-realization` branch, which is a stale snapshot main
has since fast-forwarded past (two "address review feedback" commits landed on `main` that
branch never got: new backend tests, `checkstyle.xml`, `docs/security-check.md`, and a rewritten
block-i integration doc set).

## What this is

Task-tracker is a team task-management system: backlog, kanban board, iterations, work-item
decomposition, comments, time tracking, file attachments, audit history, notifications, and
Excel import/export. A real, working **local-release** implementation exists in `backend/` and
`frontend/` (below) — this is no longer requirements-only, though it's an early/base cut, not a
production-ready one (see "Known gaps" below). As of the 01.10.2026 addendum to `vision.md`/
`system-requirements.md`, **Project and Epic are no longer task-tracker's own data** — see
"Planning System now owns Project/Epic" below, which is the single biggest scope change since
the initial implementation and isn't yet reflected in the running code.

## Real implementation (`backend/`, `frontend/`)

- **`backend/`** — Java 21 + Spring Boot 4 (webmvc, JDBC, Security/OAuth2 resource server,
  Actuator), PostgreSQL via plain `JdbcTemplate` (no JPA/Hibernate), Liquibase running one SQL
  file (`src/main/resources/db/changelog/001-initial.sql`) for the whole schema, Apache POI for
  real `.xlsx` export/import. Controller → Service → `JdbcTemplate`, one class per concern, no
  extra layering — the files are short, just read them directly rather than assuming patterns.
- **`frontend/src/`** — React 19 + TypeScript + Vite, `oidc-client-ts` for the Keycloak
  authorization-code flow. This is the **real app** — distinct from `frontend/prototype/` (the
  static click-through mock, still present and untouched, see below). `App.tsx` holds every
  screen; `api.ts` holds the fetch wrapper and the OIDC `UserManager`; `AttachmentFrame.tsx` is a
  sandboxed `<iframe>` wrapper added specifically so previewing an HTML/text attachment can't
  execute scripts (see `docs/security-check.md`).
- **`dev/keycloak-realm.json`** — demo realm imported by the `keycloak` service in
  `compose.yaml`: three human users (`member`/`lead`/`admin`) whose subject UUIDs exactly match
  what `DirectoryService`'s dev seeder inserts into `user_cache` + `local_access` when
  `DEV_DIRECTORY=true` — that's why `docker compose up --build` gives a working, already-
  permissioned app with no manual setup. Two confidential service clients (`testing-client`,
  `reports-client`) carry the `testing-service`/`reports-service` client roles that
  `AccessService` checks for the integration endpoints. A `planning-service` client role is
  already named in `070.role-matrix.md`'s prose and in `openapi.yaml`, but has no corresponding
  code path or realm entry yet — the Planning endpoints in `openapi.yaml` are spec-only (below).
- **`docs/implementation-decisions.md`** — the concrete answers chosen **for this local release**
  to `system-requirements.md`'s §11 open questions. Read it before assuming an "open question"
  from `system-requirements.md` is still genuinely undecided in code — several have a concrete
  answer here even though `system-requirements.md §11` itself hasn't been edited to mark them
  resolved. It's explicit that Planning/Kafka remain *target* integrations pending agreement, not
  settled exclusions — don't cite "local release doesn't need Kafka" as if it were a closed
  decision; it's a stopgap, and `162.integration-spec.md` (below) is where that's tracked.
- **`docs/security-check.md`** (new) — a dated security-review record (PR #129, 12.10.2026) with
  a reproduction section (`mvn checkstyle:check test`, `npm run lint/test/build`, `npm audit`,
  `docker compose config --quiet`). It's explicit about what it *didn't* verify (no Docker daemon
  in that environment either — this is a recurring constraint, see below) and names NFR-003 as
  still only `partial`. Treat its "ограничения" column as a live to-do list, not resolved risk.

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

- **The Reference Manager directory adapter targets a design the code doesn't implement, and the
  design itself had two factual errors that this pass corrected.** `DirectoryService` still does
  a single `GET .../directory/snapshot?sinceVersion=...` call expecting one `{version, users,
  teams, departments}` payload — the "unified snapshot," which Reference Manager's real contract
  explicitly rejects (`162.integration-spec.md`). The *target* design in the same doc (paginated
  `/v1/employees` + `/v1/org_units`) is close to Reference Manager's real API but — before this
  pass — got two field names wrong (now fixed): the filter param is `allowDeleted`, not
  `show_deleted`, and `account_user_id` (for mapping an employee to a JWT `sub`) **doesn't exist
  yet** on Reference Manager's side — it's one of their own planned fields (FR-RM-53..58), not a
  usable field today. Don't build against `account_user_id` until Reference Manager ships it.
- **`120.data-model.md`'s *implemented* ER diagram is behind `001-initial.sql`.** `WORK_ITEM` also
  has `severity`, `environment`, `test_run_url`, `test_case_url` (testing-service bug fields) and
  `version` (optimistic concurrency); `STATUS`/`PRIORITY` real columns are
  `active`/`board_visible`/`category` and `active`/`sort_order`/`code`, not 120's
  `is_active`/`order`. 120 does separately carry a "Предлагаемые физические дополнения
  интеграций" section (MinIO `storage_key`/`sha256`, `event_outbox`, `planning_binding`) that is
  explicitly marked as *not migrated* — don't confuse that proposal with the current schema;
  trust `001-initial.sql` for what's actually there today.
- **Kafka topic name/granularity disagree three ways and nobody's picked a winner.** We and
  Reports agree on one combined topic `task-tracker.events.v1` (3 segments). `infra/vision.md`
  requires `<env>.<domain>.<event>.v1` (4 segments — ours is missing `<env>`). Planning System's
  own `140.event-schema.md` already assumes **five separate** topics, one per event type, in the
  4-segment form (`<env>.task-tracker.task-created.v1`, `.task-changed.v1`, …). This needs an
  actual decision (DEC-TT-02) before any outbox code is written — don't pick a name unilaterally.
- **Backend test coverage improved but is still thin.** `AccessServiceTest`/`ExcelServiceTest`
  (new) cover IDOR-style access denial and formula-injection rejection; nothing exercises
  iteration lifecycle, hierarchy validation, or the audit/notification transaction atomicity that
  `075.nfr.md`'s NFR-001/002/004/005 call for. `pom.xml` already pulls in
  `org.testcontainers:postgresql` for exactly this; it's still unused for anything beyond what's
  there.
- **This dev sandbox has no JDK, Maven, or Docker daemon** (confirmed again via
  `docs/security-check.md`, written in a different environment with the same limitation) — so
  backend/compose changes can only be verified here by careful reading, not by compiling or
  running containers. The frontend *can* be verified here: `npm ci && npm run build && npm test`
  run clean.
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
of them and rolls back the whole batch on a single error.

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
- **Delivery** — task-tracker's `compose.yaml` runs its *own* Postgres and Keycloak, not the
  shared stack `infra/` is designing (root `compose.yaml`/`compose.dev.yaml` are still `services:
  {}` stubs; `.github/workflows/ci.yml` is a disabled placeholder). `infra/vision.md` is
  explicitly silent on whether teams should run their own standalone stack meanwhile — our
  current practice is neither endorsed nor contradicted, just unaddressed. MinIO bucket naming
  (`arch-dev-task-tracker`) already matches infra's convention exactly; the credentials/ACL model
  does *not* need to wait for "shared credentials" — infra already specifies per-team dedicated
  keys and bucket policy (fixed in `162.integration-spec.md` this pass, which previously said the
  opposite).
- **Reference Manager (org/user data)** — no longer scoped out: its README now explicitly states
  it *is* the HR/employee source of truth (reversed 2026-10-02 — if you're holding an older belief
  that it isn't, that's stale). Real endpoints are `/v1/employees` and `/v1/org_units`,
  cursor-paginated (`pageSize`/`pageToken`, no total count), filter param `allowDeleted`;
  `org_units.kind` (`DEPARTMENT`/`TEAM`) is implemented and matches our team/department mapping.
  `account_user_id` (employee → JWT `sub`) is **not implemented yet** on their side — see "Known
  gaps". Their employee lifecycle is `employment_state` (`EMPLOYED`/`DISMISSED`) plus a separate
  `is_deleted` flag; a third, still-unimplemented `account_state` axis (`PENDING`/`ENABLED`/
  `DISABLED`) is about Keycloak account provisioning, not employment — don't conflate the three.
- **Reports** — wants a **hybrid**: the same Kafka topic/key/dedup shape we propose
  (`task-tracker.events.v1`, `aggregateId`, dedup by `eventId` — matches exactly) *and* the REST
  pull API we've implemented (`/reports/{work-items,iterations,time-logs,statuses,history}`).
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
