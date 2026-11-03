#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose config --quiet
docker compose -f compose.yaml -f compose.integrations.yaml config --quiet
(cd backend && mvn -B test checkstyle:check)
(cd frontend && npm ci && npm run lint && npm test && npm run build)
git diff --check
# E2E against an explicitly started disposable environment:
# cd frontend && npx playwright install chromium && npx playwright test
