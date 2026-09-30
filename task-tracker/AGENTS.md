# Repository Guidelines

## Project Structure & Module Organization

`docs/system-requirements.md` defines the domain, workflows, data model, and acceptance criteria. Keep product and architecture notes under `docs/` and link decisions to IDs such as `FR-IT-05` or `NFR-03`.

The application lives in `backend/` and `frontend/`; local integration fixtures live in `dev/`. Keep tests with their owning module and exclude generated output.

## Required Technology Stack

Implement the backend in Java with Spring Boot and the frontend in React with TypeScript. These are repository constraints; changing frameworks requires an approved, documented architectural decision. Use mutually compatible stable versions and pin them in build files.

Work at senior-engineer quality: clarify ambiguity, preserve domain invariants, choose maintainable abstractions, and consider security, observability, failure modes, migrations, and compatibility. Avoid speculative layers and oversized changes. Record material trade-offs in `docs/`; leave the repository buildable and tested.

## Build, Test, and Development Commands

- `docker compose up --build` — run the local stack from `task-tracker/`.
- `cd backend && mvn test` — compile and test backend code.
- `cd frontend && npm ci && npm run build` — compile the frontend.
- `docker compose config --quiet` and `git diff --check` — validate configuration and patch formatting.

## Documentation Style & Naming Conventions

Use ATX headings (`#`, `##`), short paragraphs, and hyphenated lists. Preserve Russian terminology and define new domain terms. Requirement IDs follow patterns such as `FR-EX-01`, `BR-08`, and `NFR-07`.

Name documentation in lowercase kebab-case, for example `docs/architecture-overview.md`. Keep tables compact; document any requirement-ID migration.

## Testing Guidelines

For documentation changes, verify rendering, consistency, and `git diff --check`. Behavior changes must update relevant acceptance criteria. Backend work must include focused unit or integration tests; frontend work must test user-visible behavior and critical state transitions. Use behavior-focused test names and add regression coverage for bug fixes.

## Commit & Pull Request Guidelines

History favors short, imperative summaries; keep each commit to one logical change. Pull requests should explain motivation, list affected requirements and checks, link the issue, and call out unresolved decisions. Include screenshots for UI or rendered-documentation changes.

## Security & Configuration

Do not commit credentials, production data, or real user information. Future authorization checks must be enforced server-side, consistent with `NFR-03`, rather than relying on hidden interface controls.
