# Keycloak

Готовый Keycloak, без своего auth-сервиса. Желаемое состояние realm — [realm/desired.json](realm/desired.json). Его применяет [`keycloak_converge.py`](../scripts/keycloak_converge.py): существующие пользователи не удаляются и не получают новый пароль.

Браузерный issuer локального стенда: `http://localhost:8081/realms/arch-info-system`. Из контейнера JWKS читается по `http://keycloak:8080/.../certs`. Общий TLS-адрес не задан.

Служебный клиент `reference-manager-provisioner` имеет роли `manage-users`, `view-users`, `query-users`, `view-realm` и не является администратором сервера.
