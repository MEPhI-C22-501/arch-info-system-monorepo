# syntax=docker/dockerfile:1

FROM golang:1.27-alpine AS builder

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" \
  -o /reference-manager ./cmd/reference-manager \
  && CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" \
  -o /healthcheck ./cmd/healthcheck

FROM gcr.io/distroless/static-debian12:nonroot

WORKDIR /app

COPY --from=builder --chmod=0555 /reference-manager /app/reference-manager
# the runtime image has no shell or curl, the probe binary is used by the healthcheck of the container
COPY --from=builder --chmod=0555 /healthcheck /app/healthcheck
USER 65532:65532

ENTRYPOINT [ "/app/reference-manager" ]