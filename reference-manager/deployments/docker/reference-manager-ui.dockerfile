# syntax=docker/dockerfile:1

FROM nginxinc/nginx-unprivileged:1.28-alpine

# the nginx configuration is not baked in, it is mounted to /etc/nginx/conf.d/default.conf at runtime
# the files are copied as root and made world-readable, so the host file modes do not matter
USER 0
COPY admin/ /usr/share/nginx/html/
RUN chmod -R a+rX /usr/share/nginx/html
USER 101

EXPOSE 8080
