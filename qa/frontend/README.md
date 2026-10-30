# QA System — веб-интерфейс

React, TypeScript, Vite, react-router ([ADR-001](../docs/145.architecture-decisions.md)). Версии закреплены, как в `task-tracker/frontend`.

## Запуск

```bash
# Всё в контейнерах: http://127.0.0.1:8091, /api/ проксируется в qa-api
docker compose -f qa/compose.yaml up -d --build --wait qa-api qa-frontend

# Разработка: API из Compose на 127.0.0.1:8090, интерфейс — http://127.0.0.1:5175
cd qa/frontend
npm ci
npm run dev

# Проверки
npm run lint && npm test && npm run build

# После изменения qa/api/openapi/v1/openapi.yaml: тест падает, пока типы не пересобраны
npm run gen:api
```

Вход демонстрационный: роль и имя на экране входа становятся токеном `Bearer demo-<роль>@<имя>` и хранятся в `localStorage`. Вход через Keycloak появится вместе с TECH-09: тогда меняются только `src/session.ts` и экран `src/screens/Login.tsx`.

## Структура

| Путь | Что |
| --- | --- |
| `src/routes.tsx` | Массив `{path, element, menu, roles}`; меню строится из него. `/runs/:id` и `/test-cases/:id` не менять: на них ведут ссылки из «Ошибки» ([130, раздел 1](../docs/130.api-contracts.md)) |
| `src/api/client.ts` | `request(method, path, body, headers)`: токен, разбор ошибки `{code, message, errors[]}` в `ApiError` |
| `src/api/<область>.ts` | Клиенты областей; типы — из сгенерированного `src/api/schema.d.ts` |
| `src/permissions.ts` | Какие кнопки показывать по роли и статусу: [070](../docs/070.role-matrix.md) и [050](../docs/050.entities.md). Это удобство, права проверяет сервер |
| `src/caseForm.ts`, `src/resultForm.ts` | Проверка и сборка запросов форм кейса и результата, без React |
| `src/components/` | `StatusBadge`, `DataTable`, `Pagination`, `FilterBar`, `ErrorMessage`, `Toast`, `StepsEditor`, `CasePicker` |
| `src/screens/` | Экраны [110, раздел 2](../docs/110.ui-ux.md) |

## Правила

- Списки устроены одинаково: `FilterBar`, `DataTable` с состояниями loading, empty, error, `Pagination`; фильтры и страница живут в адресе (`useListParams`).
- Ошибка показывается компонентом `ErrorMessage`: код и причина с сервера. Новую причину вида `префикс:значение` объясните в `formatErrorItem`.
- Если API неудобен, его меняют в спецификации и на сервере, а не обходят в интерфейсе.
