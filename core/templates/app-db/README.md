# Шаблон приложения и его базы

Скопируйте каталог в модуль и замените имя. База слушает только сеть `data` и не публикуется, пока команда явно не добавит порт. Чужие сервисы роль базы не получают.

Переменные:

| Переменная | Назначение |
| --- | --- |
| `DATABASE_URL` | своя база |
| `OIDC_ISSUER` | `http://localhost:8081/realms/arch-info-system` для браузера |
| `OIDC_JWKS_URI` | `http://keycloak:8080/realms/arch-info-system/protocol/openid-connect/certs` |
| `S3_ENDPOINT` | `http://minio:9000` |
| `S3_BUCKET` | бакет команды |
| `KAFKA_BOOTSTRAP` | `kafka:9092` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4318` |

Миграции запускает одноразовый сервис до readiness приложения. Второй экземпляр миграции не стартует, пока первый не завершился: в Compose это `service_completed_successfully`.

Файл [compose.yaml](compose.yaml) подключают к общему проекту отдельным `-f`, не вливая его вслепую в базовый стенд.
