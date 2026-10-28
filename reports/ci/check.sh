#!/bin/sh
set -eu
REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$REPO_ROOT"
"${PYTHON:-python3}" reports/ci/validate.py
if [ "${REPORTS_NATIVE_POSTGRES:-0}" = "1" ]; then
  "${PYTHON:-python3}" reports/pilots/check_postgres.py
else
  "${PYTHON:-python3}" -m unittest discover -s reports/pilots/tests -v
fi
"${NODE:-node}" --test reports/pilots/tests/cube-auth.test.cjs
"${NODE:-node}" --check reports/pilots/ui/app.js
"${NODE:-node}" reports/ci/check_diagrams.mjs
git diff --check -- reports
"${PYTHON:-python3}" reports/ci/check_secrets.py
