# syntax=docker/dockerfile:1

FROM nginxinc/nginx-unprivileged:1.28-alpine

# the version of the build (NFR-RM-24): the release workflow passes the commit SHA or the version tag, task build
# passes the short commit, a build without it is "dev"
ARG VERSION=dev
LABEL org.opencontainers.image.version=$VERSION

# the nginx configuration is not baked in, it is mounted to /etc/nginx/conf.d/default.conf at runtime
# the files are copied as root and made world-readable, so the host file modes do not matter
USER 0
COPY admin/ /usr/share/nginx/html/
# the running panel tells which build it is at /admin/version.json
RUN printf '{"version": "%s"}\n' "$VERSION" > /usr/share/nginx/html/version.json \
  && chmod -R a+rX /usr/share/nginx/html
USER 101

EXPOSE 8080
