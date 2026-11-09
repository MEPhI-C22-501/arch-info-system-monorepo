# Демо общего стенда в Kubernetes

Отдельный профиль minikube `arch-demo`. Приложения пяти команд заменены **моками**.
PostgreSQL, Keycloak, Kafka, MinIO и OpenTelemetry Collector настоящие. Это локальная
демонстрация инфраструктуры; она не подтверждает бизнес-интеграции команд.

Фактически проверено 29.10.2026: Linux/amd64, Docker 29.9.1, minikube 1.39.0,
Kubernetes/kubectl 1.37.2. Прошли запуск после остановки кластера, HTTP/БД пяти
команд, JWT и 401, свой/чужой S3-бакет, Kafka SASL_SSL, ETL Job, streaming replica,
пересоздание backend и PostgreSQL pod с сохранением контрольной записи на PVC.

## Что запускается

- Namespace `arch-infra`: Keycloak с PostgreSQL, Kafka KRaft (один broker/controller),
  MinIO, Collector, PostgreSQL Reports с read-replica, портал демонстрации.
- Пять namespaces команд: `arch-planning-system`, `arch-task-tracker`,
  `arch-reference-manager`, `arch-qa`, `arch-reports`.
- В каждом — отдельные Deployment `frontend` и `backend`, Service и Job миграции.
  У первых четырёх команд свой PostgreSQL StatefulSet/PVC. Reports использует
  собственную БД в `arch-infra`; её реплика не является БД других команд.
- CronJob `demo-etl` раз в пять минут читает записи mock Task Tracker через REST
  и идемпотентно записывает их в PostgreSQL Reports.

Один образ мока запускается в разных режимах: frontend, API, gateway, migration,
ETL. Frontend проксирует API своего backend; межкомандный HTTP идёт через Kubernetes DNS.

## Запуск

Нужны Linux/amd64, работающий Docker, minikube, совместимый kubectl, Bash,
curl, openssl, setsid и Python 3 для проверок. PyYAML не требуется.
Инструменты также ищутся в `~/.local/bin`. Инструкции установки:
[minikube](https://minikube.sigs.k8s.io/docs/start/),
[kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/).
По умолчанию кластер получает 2 CPU / 4096 MiB RAM. Первая загрузка образов,
Kubernetes и сборка MinIO требуют интернета и могут занять значительное время.
Подготовьте стенд **до** показа; повторный запуск использует кэш.

Из корня репозитория:

```bash
./infra/scripts/k8s-demo.sh up
```

Скрипт создаёт только профиль `arch-demo`, не использует текущий kubectl context
для применения ресурсов (`--context=arch-demo` указан явно). Порядок: кластер,
образы, namespaces/secrets, хранилища, bootstrap, миграции, API/UI, port-forward,
проверки. При ошибке bootstrap или проверки команда завершится с ошибкой.
Повтор сохраняет пароли, БД и объекты; миграции/инициализация идемпотентны.

Откройте **http://localhost:18080**. Keycloak: http://localhost:18081/admin/;
MinIO: http://localhost:19001. Туннели слушают только `127.0.0.1`.
Пароли генерируются один раз и лежат вне Git:
`~/.local/state/arch-info-demo/arch-demo/access.txt`
(или `$XDG_STATE_HOME/arch-info-demo/arch-demo/access.txt`).

## Сценарий показа на 5–7 минут

1. Показать узел и namespaces:

   ```bash
   ~/.local/bin/kubectl --context=arch-demo get nodes
   ~/.local/bin/kubectl --context=arch-demo get namespaces
   ./infra/scripts/k8s-demo.sh status
   ```

2. Открыть портал, затем Task Tracker. Нажать «Pod и БД»: видны имя pod,
   namespace, успешное подключение к БД и число записей.
3. Нажать «Сохранить запись» и «Прочитать записи»: данные действительно в PostgreSQL.
4. «HTTP в соседний сервис» — backend другого namespace отвечает через Service/DNS.
5. «Keycloak / S3 / OTLP» — получен и проверен настоящий JWT, файл записан/прочитан
   в приватном бакете команды, чтение чужого бакета запрещено, лог принят Collector.
6. Запустить:

   ```bash
   ./infra/scripts/k8s-demo.sh check
   ```

   Помимо предыдущих проверок, mock Task Tracker отправляет событие в Kafka,
   mock Reports читает именно это событие. Создаётся Job по шаблону CronJob ETL,
   и запись появляется в БД Reports. Процесс завершается ненулевым кодом при ошибке.

7. Показать автоматическое восстановление:

   ```bash
   ./infra/scripts/k8s-demo.sh restart
   ```

   Сначала выполняются проверки, затем создаётся контрольная запись. Удаляются
   backend pod и PostgreSQL pod Task Tracker. Kubernetes создаёт новые pod;
   проверка требует смены backend pod и сохранности записи через PVC.
   Это не проверка потери узла и не доказательство высокой доступности.

Трасса проверок без паролей: `verification.json` рядом с `access.txt`.
Полезно держать рядом терминал:

```bash
~/.local/bin/kubectl --context=arch-demo get pods -A -w
```

## Управление и диагностика

```bash
./infra/scripts/k8s-demo.sh open    # заново открыть port-forward после перезапуска
./infra/scripts/k8s-demo.sh stop    # остановить кластер и туннели, сохранить данные
./infra/scripts/k8s-demo.sh up      # снова запустить и проверить
```

Диагностика:

```bash
~/.local/bin/kubectl --context=arch-demo get pods -A
~/.local/bin/kubectl --context=arch-demo get events -A --sort-by=.lastTimestamp
~/.local/bin/kubectl --context=arch-demo -n arch-infra logs job/demo-keycloak-bootstrap
~/.local/bin/kubectl --context=arch-demo -n arch-infra logs job/demo-minio-bootstrap
~/.local/bin/kubectl --context=arch-demo -n arch-infra logs kafka-0 -c bootstrap
~/.local/bin/kubectl --context=arch-demo -n arch-task-tracker logs deployment/backend
```

Удаление профиля/PVC не выполняется автоматически. Обычная остановка сохраняет
данные. Скрипты не выключают чужие контейнеры и не чистят Docker volumes.

## Границы демонстрации

- HTTP и синтетические данные допустимы только в этом локальном демо.
- API моков намеренно доступен без пользовательского входа. Отдельная точка
  `/api/protected` проверяет JWT; без токена возвращает 401. Это не авторизация
  будущих продуктов. Keycloak использует пример `example-caller`/`example-api`.
- S3 проверяется с отдельным ключом и бакетом каждой команды. RM получает бакет
  только для демонстрации механизма; настоящий RM его не требует.
- Kafka использует отдельный учебный topic `dev.infra.examples.v1`, principal
  `example`, SASL/PLAIN поверх TLS и примерные группы `example-workers-*`.
  Это не бизнес-события трекера; сертификат содержит внутрикластерное DNS-имя.
- Демо использует отдельные явные YAML-манифесты с локальными hostname,
  DNS Kafka, ресурсами и bootstrap/моками. MinIO собирается существующим
  Dockerfile из исходников; сторонний образ S3-имитатора не используется.
- Стандартный CNI minikube может не применять NetworkPolicy. Демо не доказывает
  сетевую изоляцию namespaces; это требует отдельной проверки с подходящим CNI.
- Проверка `check` подтверждает SQL-запросами recovery на read-replica и
  streaming replication на primary. Проверка `restart` дополнительно проверяет PVC.
- Восстановление из backup, TLS внешнего входа, HA и реальные контракты команд
  не входят в этот показ.

## Где описаны ресурсы

- `00-namespaces.yaml` — namespaces общей инфраструктуры и пяти команд.
- `shared/` — PostgreSQL, Keycloak, Kafka, MinIO и Collector.
- `bootstrap/` — Jobs начальной настройки Keycloak и MinIO.
- `teams/` — отдельный YAML каждой команды: БД, миграции, backend, frontend
  и Services. В `reports.yaml` также находится CronJob ETL.
- `60-gateway.yaml` — портал демонстрации и его Service.
- `config/kafka-init.sh` — настройка Kafka для внутрикластерных DNS-имён.

Скрипт `infra/scripts/k8s-demo.sh` написан на Bash: подготавливает кластер и
образы, создаёт Secrets/ConfigMaps из файлов и применяет эти манифесты через
`kubectl apply -f`. Python не генерирует Kubernetes-объекты; он используется
внутри моков, при настройке Keycloak и в `check.py` для проверок.
Образ моков имеет локальный тег `arch-info-demo:local`; после сборки скрипт
загружает его в minikube и перезапускает Deployment.

Например, проверить YAML общих сервисов без применения:

```bash
kubectl --context=arch-demo apply --dry-run=server -f infra/k8s/demo/shared/
```

Пароли хранятся вне Git; в YAML используются ссылки `secretKeyRef` на Secrets.
