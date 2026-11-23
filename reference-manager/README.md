# Reference Manager

**Reference Manager** is a reference data management service within an ERP system.

The service is the single source of reference data and HR master data: employees (HR profiles), organizational units, positions with dated assignments, salaries and absences, and shared classifiers such as currencies and countries. User accounts, passwords and access roles live in Keycloak; the service creates an account when an employee is hired and disables it on dismissal. It exposes a REST API with one collection per catalog for listing, reading, creating, updating and soft-deleting records. Requirements and design documents are in [documents/](documents/README.md).

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/` | Go service: `cmd/`, `internal/`, `pkg/`, OpenAPI specs in `api/openapi/`, the catalog generator in `tools/gencatalog/`, integration tests in `tests/`, `go.mod`, lint and Docker ignore files |
| `frontend/` | Administration interface: `frontend/admin/` is the admin panel on the service API with the Keycloak login (see its README), `frontend/prototype/index.html` is the original single-file prototype |
| `deployments/` | Dockerfiles, Docker Compose, configuration examples and database migrations of both parts |
| `documents/` | Requirements and design documents (in Russian) |
| `Taskfile.yaml` | Entry point for every command below. Run `task` from this directory, it switches into `backend/` where needed |

## Catalogs

Every catalog is a collection under `/v1/` with the same methods: create, list, get, patch, delete (soft, or permanent with `force=true`), `POST .../export` to an `.xlsx` file and the revision history under `.../revisions`. Currencies are implemented by hand (`internal/domains/currency`, `internal/services/currency`, `internal/repositories/postgres/currency`, `internal/transport/http/server/v1/currency`). The other catalogs share one generic implementation and are described in `backend/tools/gencatalog/defs.go`:

| Collection | Group | Changed by |
| --- | --- | --- |
| `currencies`, `countries`, `project_roles`, `grades` | classifiers | `reference-admin` |
| `employees`, `org_units`, `positions`, `assignments` | HR | `reference-hr-admin` |
| `salaries`, `absences` | restricted HR, read by `reference-hr-reader` and `reference-hr-admin` only | `reference-hr-admin` |

`task generate` runs the generator before oapi-codegen. For each definition it writes the OpenAPI spec and the codegen configs under `api/openapi/v1/<catalog>/`, the fields struct and the descriptor in `internal/domains/<catalog>/<catalog>.gen.go`, the HTTP adapter in `internal/transport/http/server/v1/<catalog>/handler.gen.go` and the migration pair in `deployments/migrations/`. Generated files carry a `DO NOT EDIT` header. Catalog rules (references, periods, hierarchy) live next to them in hand-written `rules.go` files. Catalog-specific methods, such as the employee dismissal, have their own service and handler files.

To add a catalog: append a definition to `defs.go`, run `task generate`, write `rules.go` when the catalog has cross-field rules, register the service in `internal/app/reference-manager/catalogs.go` and add feature files under `tests/features/`.

Lists and exports take `readTime` (RFC 3339): the records are returned as they were at that moment, rebuilt from their revisions by the last JSON Patch operation of every field before it, with the usual filter, ordering and pages. A record created later is absent, a purged one too, the computed unit and position of an employee are empty in a slice. The export takes `filter` and `order_by` of the list as well. Without parameters both behave as before (specs `1.1.0`, ADR-023).

Two operations change a whole org unit from one date in one transaction: `POST /v1/salaries/revise` (new salaries by `percent` or `amount`) and `POST /v1/assignments/transfer` (a move to `target_org_unit_id`). The record in effect of every employee of the unit (with `include_subunits`, of the units below it too) ends the day before, the new one starts on the date. `validate_only` returns the plan and rolls everything back. The decisions are a pure plan in `internal/services/groupops/plan.go`, the writes go through the standard methods of the catalog, so every record passes its rules and gets a revision.

### API contract: source and publication

The source of the contract is `backend/api/openapi/v1/<resource>/openapi.yaml` of this module, 12 specs: the nine generated catalogs, `currency`, `health` and the hand-written `profile` (ADR-025). The shared `api/openapi/reference-manager/` folder of the monorepo is the publication for the other teams: it keeps copies of these specs and the clients generated from them. Never edit a copy there, change the spec here and publish it:

```bash
task api:sync     # copies every spec of the module into api/openapi/reference-manager/
task api:check    # part of task lint and CI: fails when a copy differs from its source
```

`api/sync-specs.py` of the shared folder copies from the same source. The clients are regenerated in `api/` with its own `task generate`.

Employees carry `employment_state` and `dismissal_date`, both set by the service. `POST /v1/employees/{employeeID}/dismiss` closes the assignment and the salary in effect with the dismissal date. The unit and the position of an employee are computed from the assignment in effect today (migration `000011`).

Every employee has a Keycloak account managed by the service through the Admin REST API under the client `reference-manager-provisioner` (FR-RM-53..58). `account_state` and `account_user_id` are read-only fields of the record: the creation stores the record with `PENDING`, creates a disabled account with a random temporary password (the employee changes it at the first login), enables it and stores its ID with `ENABLED`. The new account gets no roles of the service: it signs in and reads its own profile (`GET /v1/profiles/me`), a Keycloak administrator assigns the catalog roles (ADR-024). The dismissal disables the account (`DISABLED`, the ID stays), a changed name or email is passed to the account, a working employee with an account cannot be deleted. When Keycloak is unavailable the record stays `PENDING` and the method answers `503`. `POST /v1/employees/{employeeID}/syncAccount` repeats the operation and never creates a second account (the account is found by its ID, or by username when the email matches). The `pkg/keycloak` package holds the client, `internal/services/employee` the coordination.

## Requirements

Make sure the following tools are installed: [Go](https://go.dev/doc/install), [Docker](https://docs.docker.com/engine/install/), [Docker Compose](https://docs.docker.com/compose/install/), [task](https://github.com/go-task/task) and [migrate](https://github.com/golang-migrate/migrate). [Node.js](https://nodejs.org/) 18 or newer runs the frontend tests (`task tests:frontend`).

## Configuration

Application configuration is stored in:

```text
deployments/configs/reference-manager/<environment>/
```

Configuration is split into separate files by responsibility:

| File             | Description                                         |
| ---------------- | --------------------------------------------------- |
| `transport.yaml` | HTTP transport configuration                        |
| `telemetry.yaml` | Logs, traces and metrics, export to the collector   |
| `databases.yaml` | Database connections, retries, and connection pools |
| `auth.yaml`      | Verification of Keycloak access tokens, the provisioner client of employee accounts |

Environment-specific configuration examples are stored separately in the examples directory.

Secrets are never written to the configuration files: the database password comes from `POSTGRES_PASSWORD` and the secret of the provisioner client from `KEYCLOAK_PROVISIONER_SECRET` of the environment. Compose takes both from `deployments/.env`.

### Transport layer

HTTP server configuration is defined under `transport.http`.

| Parameter             | Type       | Description                                           |
| --------------------- | ---------- | ----------------------------------------------------- |
| `listen_host`         | `string`   | Network interface the HTTP server listens on          |
| `listen_port`         | `int`      | Port the HTTP server listens on                       |
| `read_header_timeout` | `duration` | Maximum time allowed for reading request headers      |
| `read_timeout`        | `duration` | Maximum time allowed for reading the complete request |
| `write_timeout`       | `duration` | Maximum time allowed for writing a response           |
| `idle_timeout`        | `duration` | Maximum time an idle connection can remain open       |

Request limits of the router are defined under `transport.limits`.

| Parameter             | Type       | Description                                                   |
| --------------------- | ---------- | ------------------------------------------------------------- |
| `requests_per_second` | `float`    | Sustained rate of accepted requests, `10` by default          |
| `burst`               | `int`      | Size of the token bucket, `100` by default                    |
| `request_timeout`     | `duration` | Timeout of one request, the context is cancelled after it, `1s` by default |

### Service endpoints

The service endpoints need no token and are not published outside the cluster on the shared stand ([documents/070.role-matrix.md](documents/070.role-matrix.md), section 4).

| Endpoint | Answer |
| --- | --- |
| `GET /v1/health/livez` | `200` without a body while the process runs (FR-RM-30) |
| `GET /v1/health/readyz` | `200` `{"ready": true}` when the database answers, otherwise `503` `{"ready": false, "failedDependencies": [{"name": "postgres", "error": "..."}]}` (FR-RM-31). The schema version is not checked yet (K-02, issue #46) |

### Logging

The service logs through `log/slog` to stdout. The level and the format are set under `telemetry.log` (see [Telemetry](#telemetry)): `level` is `debug`, `info`, `warn` or `error`, `format` is `text` or `json`, an unknown format stops the start. With `telemetry.exporter.enabled` the same records also go to the collector over OTLP. There are no log files and no rotation, the container runtime collects stdout.

Records worth knowing:

| Message | Level | When |
| --- | --- | --- |
| `access denied` | `WARN` | A request lacks the roles for the operation (FR-RM-65), with `method`, `path`, `group`, `level`, `sub`, `roles` and `azp` of the token |
| `account operation is pending` | `WARN` | Keycloak did not confirm an operation with an employee account, the record stays `PENDING` |
| `readiness check failed` | `ERROR` | `/v1/health/readyz` found the database down |

### Work with databases

Database configuration is defined under `databases`.

#### PostgreSQL connection

PostgreSQL connection settings are defined under `databases.postgres`.

| Parameter  | Type     | Description                |
| ---------- | -------- | -------------------------- |
| `host`     | `string` | PostgreSQL server hostname |
| `port`     | `int`    | PostgreSQL server port     |
| `user`     | `string` | Database user              |
| `password` | `string` | Database password, read from `POSTGRES_PASSWORD` of the environment |
| `database` | `string` | Database name              |

The service connects as `reference_manager_app`, an account with data rights only (select, insert, update, delete on the tables, usage on the sequences). The schema belongs to `reference_manager`, the account of the migrations and the seed. In the local environment `deployments/postgres/init/10-app-role.sh` creates the service account on the first start of the database with the password `POSTGRES_APP_PASSWORD`, on the shared stand both accounts are provided by Infra.

#### Connection retry

Retry behavior for establishing a database connection is configured under `databases.postgres.connect_retry`.

| Parameter         | Type       | Description                                                      |
| ----------------- | ---------- | ---------------------------------------------------------------- |
| `enabled`         | `bool`     | Enables retries when a database connection cannot be established |
| `attempts_count`  | `int`      | Maximum number of connection attempts                            |
| `attempt_timeout` | `duration` | Timeout for a single connection attempt                          |
| `initial_delay`   | `duration` | Delay before the first retry                                     |
| `max_delay`       | `duration` | Maximum delay between retry attempts                             |
| `backoff_scale`   | `float`    | Multiplier applied to the retry delay after each failed attempt  |

#### Connection pool

PostgreSQL connection pool settings are configured under `databases.postgres.pool`.

| Parameter                  | Type       | Description                                              |
| -------------------------- | ---------- | -------------------------------------------------------- |
| `max_connections`          | `int`      | Maximum number of connections maintained by the pool     |
| `min_connections`          | `int`      | Minimum number of connections maintained by the pool     |
| `min_idle_connections`     | `int`      | Minimum number of idle connections kept available        |
| `max_connection_lifetime`  | `duration` | Maximum lifetime of a connection before it is recreated  |
| `max_connection_idle_time` | `duration` | Maximum time an unused connection can remain in the pool |
| `health_check_period`      | `duration` | Interval between connection pool health checks           |

### Authentication and authorization

Every API request except `/v1/health/*` needs a Keycloak access token in the `Authorization: Bearer <token>` header. The service verifies the token signature with the realm keys (JWKS), its issuer, audience, lifetime and type, and takes the actor from it: the user ID from `sub` and the roles from `resource_access.<client_id>.roles` (realm roles are not read). A request without a valid token gets `401`, an operation the roles do not grant gets `403`. Roles are checked by the matrix "role - reference group - access level" from [documents/070.role-matrix.md](documents/070.role-matrix.md): classifiers are read and exported by every role of the service and changed by `reference-admin` only, HR catalogs are changed by `reference-hr-admin`, salaries and absences are hidden from `reference-reader` and `reference-admin` (see [Catalogs](#catalogs)).

The keys are cached and refreshed in the background and when a token is signed by an unknown key, so key rotation needs no restart and requests keep working while Keycloak is unavailable. The service starts without Keycloak as well.

Token verification is configured under `auth.keycloak`.

| Parameter                           | Type       | Description                                                                                       |
| ----------------------------------- | ---------- | ------------------------------------------------------------------------------------------------- |
| `issuer_url`                        | `string`   | Realm URL, the `iss` claim must match it exactly. Required                                        |
| `jwks_url`                          | `string`   | Realm keys URL when the service reaches Keycloak by another address, derived from the issuer otherwise |
| `audience`                          | `string`   | Required value of the `aud` claim, `reference-manager` by default, always checked                 |
| `client_id`                         | `string`   | Client whose roles are taken from `resource_access`, `reference-manager` by default               |
| `algorithms`                        | `[]string` | Signing algorithms, only `[RS256]` is accepted (the default)                                      |
| `leeway`                            | `duration` | Allowed clock skew when checking the token lifetime, `30s` by default                             |
| `jwks.refresh_interval`             | `duration` | Period of the background refresh of the keys, `1h` by default                                     |
| `jwks.unknown_key_refresh_interval` | `duration` | Minimal period between refreshes caused by unknown keys, `1m` by default                          |
| `jwks.request_timeout`              | `duration` | Timeout of a request for the keys, `5s` by default                                                |

### Employee accounts

The accounts of employees are managed under `auth.keycloak.provisioner` (see [Catalogs](#catalogs)). The client needs the roles `manage-users`, `view-users`, `query-users` and `view-realm` of the `realm-management` client.

| Parameter             | Type       | Description                                                                                       |
| --------------------- | ---------- | ------------------------------------------------------------------------------------------------- |
| `base_url`            | `string`   | Address of Keycloak for the Admin REST API, derived from `jwks_url` (or the issuer) by default     |
| `realm`               | `string`   | Realm of the accounts, derived from `jwks_url` (or the issuer) by default                          |
| `client_id`           | `string`   | Service client, `reference-manager-provisioner` by default                                        |
| `client_secret`       | `string`   | Secret of the client, read from `KEYCLOAK_PROVISIONER_SECRET` of the environment only. Required   |
| `request_timeout`     | `duration` | Timeout of one call to Keycloak, `5s` by default                                                  |

The service assigns no roles, so the client needs no rights on the roles of other clients (ADR-024).

On the shared stand Infra provides Keycloak, the realm, the clients and their secrets: the issuer and the clients of the service are set in `infra/config/reference-manager/auth.yaml`, the provisioner secret comes from the environment of the stand. Secrets never come from this repository, the realm JSON of this module and `deployments/.env.example` serve the local environment and the integration tests only.

### Telemetry

Logs are written to stdout and, together with traces and metrics, sent over OTLP gRPC to the OpenTelemetry Collector. Every HTTP request except `/v1/health/*` gets a span named after its route with child spans of the database queries (query parameters are not recorded); an incoming `traceparent` is continued and the trace ID is returned in the `X-Trace-Id` header. Metrics cover HTTP requests, database queries, the connection pool and the Go runtime. The exporters connect lazily, so an unavailable collector neither blocks the startup nor affects requests: export errors are logged to stdout and the data is dropped.

Telemetry is configured under `telemetry`.

| Parameter                  | Type       | Description                                                                      |
| -------------------------- | ---------- | -------------------------------------------------------------------------------- |
| `resource.service_name`    | `string`   | `service.name` of the telemetry                                                  |
| `resource.service_version` | `string`   | `service.version` of the telemetry, `0.0.0` by default                           |
| `resource.environment`     | `string`   | `deployment.environment.name` of the telemetry                                   |
| `exporter.enabled`         | `bool`     | Send telemetry to the collector, `false` by default: logs go to stdout only      |
| `exporter.endpoint`        | `string`   | Collector OTLP gRPC address `host:port`, `localhost:4317` by default             |
| `exporter.insecure`        | `bool`     | Connect without TLS, `false` by default                                          |
| `exporter.timeout`         | `duration` | Timeout of one export, `10s` by default                                          |
| `traces.sampling_ratio`    | `float`    | Share of the sampled root traces from 0 to 1, `1` by default                     |
| `metrics.export_interval`  | `duration` | Period of the metrics export, `15s` by default                                   |
| `log.level`                | `string`   | `debug`, `info`, `warn` or `error`, applies to stdout and the exported logs      |
| `log.format`               | `string`   | Format of the stdout logs: `text` or `json`                                      |

## Run local environment

The local development environment is managed using [Task](https://taskfile.dev/) and Docker Compose. One command starts it on a clean machine:

```bash
task up
```

When `deployments/.env` is missing, the command creates it from `deployments/.env.example`, which holds every secret of the environment (`POSTGRES_PASSWORD`, `POSTGRES_APP_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_PROVISIONER_SECRET`, `KEYCLOAK_CONSUMER_SECRET`), the configuration files hold none. Then it builds the images and starts `deployments/docker-compose.yaml`: the database, the one-shot jobs of the migrations, the demonstration data set and the Keycloak accounts of its employees, Keycloak, the collector, the service and the admin panel. The service account of the database is created on the first start of the database, so run `task down` before `task up` on an environment created before this version.

`task up` keeps the order the schema needs. The one-shot job of the migrations (`migrate up` over `deployments/migrations`) starts when the database is healthy. After it finishes successfully, the demonstration data set and the service start, the service also waits for a healthy Keycloak. The admin panel waits for a healthy service, the accounts job for a healthy service and a loaded data set. There is therefore no separate `task migrate`. `task migration -- <name>` only creates the files of a new migration. On the shared stand the schema changes run as a separate job before the service (issue #35).

The host ports leave room for the stands of the other modules and the shared environment of Infra, which take 8080, 8081, 8180, 4317 and 4318:

| Component | Address | Variable |
| --- | --- | --- |
| Admin panel | `http://localhost:8084/admin/` | `REFERENCE_MANAGER_UI_PORT` |
| Service API | `http://localhost:8083/v1/` | `REFERENCE_MANAGER_PORT` |
| Keycloak | `http://localhost:8183` | fixed: it is the token issuer, the panel config and its CSP name it |
| PostgreSQL | `localhost:5437` | `POSTGRES_PORT` |
| Collector | `localhost:14317` gRPC, `localhost:14318` HTTP | `OTEL_COLLECTOR_GRPC_PORT`, `OTEL_COLLECTOR_HTTP_PORT` |
| Swagger UI | `http://localhost:8089`, after `task swagger` | `SWAGGER_PORT` |

The panel logs in through Keycloak (users of the local realm, the password equals the username: `admin`, `hr-admin`, `reader`, `hr-reader`) and talks to the service through the `/v1/` proxy of its own nginx, so the browser uses one origin. `task swagger` starts Swagger UI of every spec on the same network: the Authorize button logs in with PKCE through the local Keycloak and "Try it out" goes through the `/v1/` proxy of its nginx.

The local Keycloak imports the realm `arch-info-system` from `deployments/configs/keycloak/arch-info-system-realm.json` with the roles of the service, the client `reference-manager` (token audience), the public client `reference-manager-ui`, the service client `reference-manager-provisioner` and test users whose password equals the username: `admin`, `second-admin`, `reader`, `hr-admin`, `hr-reader` and `outsider` (no roles). For the consumers it has service clients with the client ids and roles of the realm of Infra: `reports-client` and `tracker-directory` (`reference-reader`), `planning-service` (`reference-hr-reader`), `qa-executor` (`reference-profile-reader` only). The scenarios of `backend/tests/features/catalogs/consumers.feature` read through each of them. `deployments/configs/keycloak/import-realm.sh` substitutes `KEYCLOAK_PROVISIONER_SECRET` and `KEYCLOAK_CONSUMER_SECRET` into the realm on the start of Keycloak. The realm is for local development and integration tests only, on the shared stand Keycloak and its realm are provided by Infra.

The collector prints a summary of every received batch to its log (`docker logs reference_manager_otel_collector`) and stores nothing. The storage and the browsing of telemetry are provided by Infra on the shared stand, where only `telemetry.exporter.endpoint` changes. A trace of a request is found there by the `X-Trace-Id` of the response.

Get a token of a consumer and call the API. The secret and the token go through files, so they never reach the command line:

```bash
umask 077
sed -n 's/^KEYCLOAK_CONSUMER_SECRET=/client_secret=/p' deployments/.env > /tmp/rm-secret.form
curl -s -d @/tmp/rm-secret.form -d grant_type=client_credentials -d client_id=reports-client \
  http://localhost:8183/realms/arch-info-system/protocol/openid-connect/token \
  | jq -r '"Authorization: Bearer " + .access_token' > /tmp/rm-token.hdr
curl -H @/tmp/rm-token.hdr 'http://localhost:8083/v1/employees/?readTime=2026-10-01T00:00:00Z'
rm /tmp/rm-secret.form /tmp/rm-token.hdr
```

### Demonstration data

`task up` loads the demonstration data set and creates the Keycloak accounts of its employees. Both jobs can be repeated by hand:

```bash
task demo:data      # loads deployments/seed/demo.sql: classifiers, units, positions, 8 employees with assignments, salaries and absences
task demo:accounts  # calls POST /v1/employees/{id}/syncAccount for every employee as hr-admin (backend/tools/demoaccounts)
```

The data set is loaded once: a second run finds the employees and changes nothing. Every record has its first revision. The accounts appear in the Keycloak admin console under the realm `arch-info-system`, each with a temporary password and a forced password change, and the accounts job is safe to repeat. A typical demonstration: hire an employee (`POST /v1/employees/`), show the enabled account in Keycloak, export `POST /v1/employees/export`, plan new salaries of a unit (`POST /v1/salaries/revise` with `validate_only`), dismiss the employee (`POST /v1/employees/{id}/dismiss`) and show the disabled account and the revisions of the record.

### Integration tests

`task tests:integration` starts PostgreSQL with all migrations on an empty database, Keycloak with the realm and the collector through testcontainers, then runs the godog scenarios of `backend/tests/` (see [backend/tests/README.md](backend/tests/README.md)). CI runs the same target in the job `Integration tests` of every pull request that changes `reference-manager/`, so every run starts from a clean environment. Last local run, 2026-11-24: 248 scenarios and 2300 steps, all passed, about one minute after the images are built.

### Browser tests

`task tests:e2e` runs the Playwright tests of the admin panel in `frontend/e2e/` against the running environment (not in CI). It needs Node 18+ and a Chromium: `npx playwright install chromium` in `frontend/e2e/`, or `E2E_CHROMIUM` with the path of a Chromium already on the machine. `E2E_BASE_URL` points the tests at another stand.

To stop the local environment and remove its associated volumes:

```bash
task down
```

After making changes to the application, run `task up` again to rebuild the binary and Docker images and restart the local environment.
