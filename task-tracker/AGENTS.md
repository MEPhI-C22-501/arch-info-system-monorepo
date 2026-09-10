# Repository Guidelines

## Project Structure & Module Organization

The project is currently in the requirements phase. `docs/system-requirements.md` defines the domain, workflows, data model, and acceptance criteria. Keep product and architecture notes under `docs/` and link decisions to IDs such as `FR-IT-05` or `NFR-03`.

No application source or build configuration exists yet. When implementation begins, use top-level `backend/` and `frontend/` modules, keep tests with their owning module, document layout changes here, and exclude generated output.

## Required Technology Stack

Implement the backend in Java with Spring Boot and the frontend in React with TypeScript. These are repository constraints; changing frameworks requires an approved, documented architectural decision. Use mutually compatible stable versions and pin them in build files.

Work at senior-engineer quality: clarify ambiguity, preserve domain invariants, choose maintainable abstractions, and consider security, observability, failure modes, migrations, and compatibility. Avoid speculative layers and oversized changes. Record material trade-offs in `docs/`; leave the repository buildable and tested.

## Build, Test, and Development Commands

There is no configured build or application runtime yet. Useful repository checks are:

- `rg --files` — list the files currently in scope.
- `git diff --check` — detect trailing whitespace and malformed patch formatting.
- `git diff -- docs/` — review requirement changes before committing.

Add reproducible build, test, lint, and local-run commands here with the toolchain.

## Documentation Style & Naming Conventions

Use ATX headings (`#`, `##`), short paragraphs, and hyphenated lists. Preserve Russian terminology and define new domain terms. Requirement IDs follow patterns such as `FR-EX-01`, `BR-08`, and `NFR-07`.

Name documentation in lowercase kebab-case, for example `docs/architecture-overview.md`. Keep tables compact; document any requirement-ID migration.

## Testing Guidelines

For documentation changes, verify rendering, consistency, and `git diff --check`. Behavior changes must update relevant acceptance criteria. Backend work must include focused unit or integration tests; frontend work must test user-visible behavior and critical state transitions. Use behavior-focused test names and add regression coverage for bug fixes.

## Commit & Pull Request Guidelines

History favors short, imperative summaries; keep each commit to one logical change. Pull requests should explain motivation, list affected requirements and checks, link the issue, and call out unresolved decisions. Include screenshots for UI or rendered-documentation changes.

## Security & Configuration

Do not commit credentials, production data, or real user information. Future authorization checks must be enforced server-side, consistent with `NFR-03`, rather than relying on hidden interface controls.
