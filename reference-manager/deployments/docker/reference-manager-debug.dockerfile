FROM gcr.io/distroless/static-debian12:debug-nonroot

WORKDIR /app
COPY bin/reference-manager /app/reference-manager
USER nonroot:nonroot
ENTRYPOINT [ "/app/reference-manager" ]