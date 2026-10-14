# syntax=docker/dockerfile:1

FROM nginxinc/nginx-unprivileged:1.28-alpine

# the files are copied as root and made world-readable, so the host file modes do not matter
USER 0
COPY deployments/nginx/reference-manager-ui.conf /etc/nginx/conf.d/default.conf
COPY frontend/admin/ /usr/share/nginx/html/
RUN chmod -R a+rX /usr/share/nginx/html /etc/nginx/conf.d/default.conf
USER 101

EXPOSE 8080
