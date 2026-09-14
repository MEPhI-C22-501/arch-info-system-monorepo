# Reference Manager

**Reference Manager** is a reference data management service within an ERP system.

The service provides centralized storage and management of reference data such as countries, currencies, users, and other master data. It exposes a REST API for creating, retrieving, updating, and deleting reference directories and their entries.

## Requirements

Make sure the following tools are installed: [Go](https://go.dev/doc/install), [Docker](https://docs.docker.com/engine/install/), [Docker Compose](https://docs.docker.com/compose/install/), [task](https://github.com/go-task/task) and [migrate](https://github.com/golang-migrate/migrate)

## Configuration

Application configuration is stored in:

```text
deployments/configs/reference-manager/<environment>/
```

Configuration is split into separate files by responsibility:

| File             | Description                                         |
| ---------------- | --------------------------------------------------- |
| `transport.yaml` | HTTP transport configuration                        |
| `log.yaml`       | Logging configuration                               |
| `databases.yaml` | Database connections, retries, and connection pools |

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

## Run local environment

The local development environment is managed using [Task](https://taskfile.dev/) and Docker Compose.

Build the application, create Docker images, and start all required services:

```bash
task up
```

The command builds the application binary and Docker images before starting the environment defined in `deployments/docker-compose.yaml`.

To stop the local environment and remove its associated volumes:

```bash
task down
```

After making changes to the application, run `task up` again to rebuild the binary and Docker images and restart the local environment.
