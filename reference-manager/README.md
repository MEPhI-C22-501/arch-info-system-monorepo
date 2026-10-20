# Reference Manager

**Reference Manager** is a reference data management service within an ERP system.

The service is the single source of reference data and HR master data: employees (HR profiles), organizational units, positions with dated assignments, salaries and absences, and shared classifiers such as currencies and countries. User accounts, passwords and access roles live in Keycloak; the service creates an account when an employee is hired and disables it on dismissal. It exposes a REST API with one collection per catalog for listing, reading, creating, updating and soft-deleting records. Requirements and design documents are in [documents/](documents/README.md).

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/` | Go service: `cmd/`, `internal/`, `pkg/`, OpenAPI specs in `api/openapi/`, the catalog generator in `tools/gencatalog/`, integration tests in `tests/`, `go.mod`, lint and Docker ignore files |
| `frontend/` | Administration interface: `frontend/admin/` is the step 1 admin panel on mock data (see its README), `frontend/prototype/index.html` is the original single-file prototype |
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

Employees carry `employment_state` and `dismissal_date`, both set by the service. `POST /v1/employees/{employeeID}/dismiss` closes the assignment and the salary in effect with the dismissal date. The unit and the position of an employee are computed from the assignment in effect today (migration `000011`). Keycloak accounts for employees are not implemented yet.

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
| `auth.yaml`      | Verification of Keycloak access tokens              |

Environment-specific configuration examples are stored separately in the examples directory.

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

### Logging

Logging configuration is defined under `log`.

#### Metadata

The `log.meta` section defines metadata associated with application logs.

| Parameter     | Type     | Description                                  |
| ------------- | -------- | -------------------------------------------- |
| `service`     | `string` | Service name included in log metadata        |
| `environment` | `string` | Runtime environment included in log metadata |

#### Handlers

The `log.handlers` section defines one or more log outputs.

| Parameter | Type     | Description                                  |
| --------- | -------- | -------------------------------------------- |
| `name`    | `string` | Unique handler name                          |
| `type`    | `string` | Log output type, such as `file` or `console` |
| `level`   | `string` | Minimum log level processed by the handler   |
| `format`  | `string` | Log output format, such as `json` or `text`  |

For file handlers, additional settings are available under `file`.

| Parameter                   | Type       | Description                              |
| --------------------------- | ---------- | ---------------------------------------- |
| `location`                  | `string`   | Directory where log files are stored     |
| `rotation.enabled`          | `bool`     | Enables automatic log rotation           |
| `rotation.filename_pattern` | `string`   | Naming pattern for rotated log files     |
| `rotation.max_size`         | `int`      | Maximum log file size before rotation    |
| `rotation.max_age`          | `duration` | Maximum lifetime of rotated log files    |
| `rotation.max_backups`      | `int`      | Maximum number of old log files to keep  |
| `rotation.compress`         | `bool`     | Enables compression of rotated log files |

### Work with databases

Database configuration is defined under `databases`.

#### PostgreSQL connection

PostgreSQL connection settings are defined under `databases.postgres`.

| Parameter  | Type     | Description                |
| ---------- | -------- | -------------------------- |
| `host`     | `string` | PostgreSQL server hostname |
| `port`     | `int`    | PostgreSQL server port     |
| `user`     | `string` | Database user              |
| `password` | `string` | Database password          |
| `database` | `string` | Database name              |

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

Every API request except `/v1/health/*` needs a Keycloak access token in the `Authorization: Bearer <token>` header. The service verifies the token signature with the realm keys (JWKS), its issuer, audience, lifetime and type, and takes the actor from it: the user ID from `sub` and the roles from `realm_access.roles` together with `resource_access.<client_id>.roles`. A request without a valid token gets `401`, an operation the roles do not grant gets `403`. Roles are checked by the matrix "role - reference group - access level" from [documents/070.role-matrix.md](documents/070.role-matrix.md): classifiers are read and exported by every role of the service and changed by `reference-admin` only, HR catalogs are changed by `reference-hr-admin`, salaries and absences are hidden from `reference-reader` and `reference-admin` (see [Catalogs](#catalogs)).

The keys are cached and refreshed in the background and when a token is signed by an unknown key, so key rotation needs no restart and requests keep working while Keycloak is unavailable. The service starts without Keycloak as well.

Token verification is configured under `auth.keycloak`.

| Parameter                           | Type       | Description                                                                                       |
| ----------------------------------- | ---------- | ------------------------------------------------------------------------------------------------- |
| `issuer_url`                        | `string`   | Realm URL, the `iss` claim must match it exactly. Required                                        |
| `jwks_url`                          | `string`   | Realm keys URL when the service reaches Keycloak by another address, derived from the issuer otherwise |
| `audience`                          | `string`   | Required value of the `aud` claim, not checked when empty                                         |
| `client_id`                         | `string`   | Client whose roles are taken from `resource_access` in addition to the realm roles                |
| `algorithms`                        | `[]string` | Accepted signing algorithms, `RS256` by default                                                   |
| `leeway`                            | `duration` | Allowed clock skew when checking the token lifetime, `30s` by default                             |
| `jwks.refresh_interval`             | `duration` | Period of the background refresh of the keys, `1h` by default                                     |
| `jwks.unknown_key_refresh_interval` | `duration` | Minimal period between refreshes caused by unknown keys, `1m` by default                          |
| `jwks.request_timeout`              | `duration` | Timeout of a request for the keys, `5s` by default                                                |

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

The local development environment is managed using [Task](https://taskfile.dev/) and Docker Compose.

Build the application, create Docker images, and start all required services:

```bash
task up
```

The command builds the application binary and Docker images before starting the environment defined in `deployments/docker-compose.yaml`. The admin panel from `frontend/admin/` is served at `http://localhost:8081/admin/` (port `REFERENCE_MANAGER_UI_PORT` in `deployments/.env`).

The environment includes a local Keycloak at `http://localhost:8180` (admin console credentials `KEYCLOAK_ADMIN_USERNAME` / `KEYCLOAK_ADMIN_PASSWORD` in `deployments/.env`). It imports the realm `arch-info-system` from `deployments/configs/keycloak/arch-info-system-realm.json` with the roles of the service, the client `reference-manager` (token audience), the public client `reference-manager-ui` and test users whose password equals the username: `admin`, `second-admin`, `reader`, `hr-admin`, `hr-reader` and `outsider` (no roles). The realm is for local development and integration tests only, on the shared stand Keycloak and its realm are provided by Infra.

The environment also includes the telemetry stack:

| Service                 | Address                 | Purpose                                                                                     |
| ----------------------- | ----------------------- | ------------------------------------------------------------------------------------------- |
| OpenTelemetry Collector | `localhost:4317` (gRPC), `localhost:4318` (HTTP) | Receives OTLP from the service and writes it to Elasticsearch, config `deployments/configs/otel-collector/local/otel-collector.yaml` |
| Elasticsearch           | `http://localhost:9200` | Stores logs, traces and metrics in the data streams `logs-*.otel-*`, `traces-*.otel-*`, `metrics-*.otel-*` |
| Kibana                  | `http://localhost:5601` | Browsing the telemetry                                                                      |

Elasticsearch runs as a single node without security and is meant for local development only. Ports and the heap size are set by `ELASTICSEARCH_PORT`, `ELASTICSEARCH_HEAP` and `KIBANA_PORT` in `deployments/.env`. Logstash is not used: the collector writes to Elasticsearch directly.

On startup `reference-manager-kibana-setup` creates the data views `reference-manager logs`, `reference-manager traces` and `reference-manager metrics`, open them in Kibana under **Discover**. A trace of a request is found by the `X-Trace-Id` of the response: filter `trace_id : "<id>"` in the traces or the logs data view. On the shared stand the collector and the storage are provided by Infra and only `telemetry.exporter.endpoint` changes.

Get a token and call the API:

```bash
TOKEN=$(curl -s -d grant_type=password -d client_id=reference-manager-ui -d username=admin -d password=admin \
  http://localhost:8180/realms/arch-info-system/protocol/openid-connect/token | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/v1/currencies/
```

To stop the local environment and remove its associated volumes:

```bash
task down
```

After making changes to the application, run `task up` again to rebuild the binary and Docker images and restart the local environment.
