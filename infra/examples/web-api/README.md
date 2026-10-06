# Эталон Web API

Сервер: `server.py`. Проверка: `check.py`.

Проверяются успешное создание, повтор с тем же `Idempotency-Key`, ответ 422 и один временный 503. Если задан `API_TOKEN`, запросы идут с bearer-токеном. Команда из корня стенда входит в `infra/scripts/run-examples.sh`.
