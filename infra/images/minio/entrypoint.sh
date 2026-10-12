#!/bin/sh
set -eu
mkdir -p /data
chown minio:minio /data
exec runuser -u minio -- minio "$@"
