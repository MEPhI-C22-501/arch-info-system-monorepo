# Моки

`mocks/README.md` относится к профилю параллельной разработки. Мок не доказывает авторизацию и не заменяет сервер команды.

Эталон Web API — отдельный учебный сервер в `infra/examples/web-api`. Он проверяет токен Keycloak, когда заданы `OIDC_ISSUER` и `OIDC_JWKS_URI`.

Спецификации команд монтируются из путей [../contracts/catalog.yaml](../contracts/catalog.yaml) и здесь не копируются.
