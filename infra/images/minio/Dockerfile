# Воспроизводимая сборка MinIO из зафиксированного исходного релиза.
# Официальный репозиторий архивирован. Страница релиза указывает установку
# `go install github.com/minio/minio@RELEASE.2025-10-15T17-29-55Z`.
# Клон git:// внутри сборки обрывался (connection reset), поэтому те же теги
# ставятся через модульный прокси Go. Базовые образы проверены 2026-10-06.

FROM golang:1.24.8-bookworm@sha256:39e2f344b68e61144a5de3d3bd166ea746ee8e1965e6fc2ad046df5cd6c8369e AS build

ARG MINIO_REF=RELEASE.2025-10-15T17-29-55Z
ARG MC_REF=RELEASE.2025-08-13T08-35-41Z

ENV CGO_ENABLED=0
RUN go install -trimpath "github.com/minio/minio@${MINIO_REF}" \
    && go install -trimpath "github.com/minio/mc@${MC_REF}"

FROM debian:trixie-slim@sha256:918311b7b6c4c6f68b232ba516584925f6c78ad82b6fd534b98979df6438e483

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --home /data --shell /usr/sbin/nologin minio \
    && mkdir -p /data

COPY --from=build /go/bin/minio /usr/local/bin/minio
COPY --from=build /go/bin/mc /usr/local/bin/mc
COPY entrypoint.sh /usr/local/bin/minio-entrypoint.sh

RUN chmod 755 /usr/local/bin/minio /usr/local/bin/mc /usr/local/bin/minio-entrypoint.sh

EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/minio-entrypoint.sh"]
CMD ["server", "/data", "--console-address", ":9001"]
