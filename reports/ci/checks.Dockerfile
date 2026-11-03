# Linux runner for the native Cube/PostgreSQL checks (check_semantics.py, check_cube.py,
# check_cube_matrix.py) on any host, including Windows. Build context: reports/pilots.
#   docker build -f reports/ci/checks.Dockerfile -t reports-checks reports/pilots
#   docker run --rm -u 0 -v "$PWD:/src" -v reports-cube-nm:/src/reports/pilots/cube/node_modules reports-checks \
#     sh -c "npm install --prefix reports/pilots/cube && chown -R 1000:1000 reports/pilots/cube/node_modules"
#   docker run --rm -v "$PWD:/src" -v reports-cube-nm:/src/reports/pilots/cube/node_modules \
#     -w /src/reports/pilots reports-checks python check_cube_matrix.py --record
FROM node:22.20.0-bookworm-slim AS node
FROM python:3.12.14-slim
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-test.txt /tmp/req/
RUN pip install --no-cache-dir -r /tmp/req/requirements-test.txt
# PostgreSQL (pgserver) refuses to run as root and needs a named user.
RUN useradd -m -u 1000 runner
USER runner
WORKDIR /src
