FROM busybox:1.37 AS prepare

RUN mkdir -p /app/log/reference-manager \
    && chown -R 65532:65532 /app/log

FROM gcr.io/distroless/static-debian12:debug-nonroot

WORKDIR /app

COPY --from=prepare /app/log /app/log
COPY --chown=65532:65532 bin/reference-manager /app/reference-manager

USER nonroot:nonroot

ENTRYPOINT ["/app/reference-manager"]