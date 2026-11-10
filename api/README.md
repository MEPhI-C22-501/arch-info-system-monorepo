# api

OpenAPI-спецификации модулей и код, сгенерированный по ним.

| Путь | Что лежит |
| --- | --- |
| `openapi/<модуль>/.../openapi.yaml` или `openapi.json` | Общий каталог спецификаций. Путь от `openapi/` до файла задаёт имена пакетов |
| `configs/<язык>.yaml` | Настройки генератора, общие для всех спецификаций одного языка |
| `out/<язык>/` | Сгенерированный код. На каждый язык один проект: Go-модуль, Python-пакет, Maven-проект, npm-пакет |
| `Taskfile.yaml` | Команды `generate` и `swagger` |

## Что нужно установить

- [Task](https://taskfile.dev/installation/)
- openapi-generator-cli 7.26.0, см. ниже
- Python 3 для синхронизации спецификаций
- Go: после генерации Go-кода запускаются `goimports` и `go mod tidy`
- Docker: для `task swagger`

## Установка openapi-generator-cli

Генератору нужна Java 11 или новее (`java -version`).

### Arch Linux

```bash
sudo pacman -S openapi-generator
```

Пакет есть в официальном репозитории `extra` и обновляется вместе с системой. Команда называется `openapi-generator-cli`.

### Любая система, без прав администратора

Скачайте jar с Maven Central и создайте команду-обёртку в `~/.local/bin` (эта папка должна быть в `PATH`):

```bash
V=7.26.0
D=~/.local/share/openapi-generator
mkdir -p "$D" ~/.local/bin
curl -fsSL -o "$D/openapi-generator-cli.jar" \
  "https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/$V/openapi-generator-cli-$V.jar"

cat > ~/.local/bin/openapi-generator-cli <<'EOF'
#!/bin/sh
exec java ${JAVA_OPTS} -jar "$HOME/.local/share/openapi-generator/openapi-generator-cli.jar" "$@"
EOF
chmod +x ~/.local/bin/openapi-generator-cli
```

Для обновления повторите команды с новым номером в `V`. Последняя версия указана на [странице релизов](https://github.com/OpenAPITools/openapi-generator/releases).

### Через Docker

Java не нужна. Обёртка запускает генератор из образа и монтирует текущую папку под тем же путём, поэтому абсолютные пути из `Taskfile.yaml` работают внутри контейнера:

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/openapi-generator-cli <<'EOF'
#!/bin/sh
exec docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:$PWD" -w "$PWD" \
  openapitools/openapi-generator-cli:v7.26.0 "$@"
EOF
chmod +x ~/.local/bin/openapi-generator-cli
```

Запускайте `task` из папки `api/`, иначе спецификации окажутся вне смонтированной папки.

### Проверка

```bash
openapi-generator-cli version
```

## Генерация

```bash
task generate                         # все языки, все спецификации
task generate TARGET=go               # один язык
task generate SPEC=qa/v1              # одна спецификация
task generate TARGET=java SPEC=qa/v1
task generate SPEC=planning-system/v1  # сервер и клиенты к основному API Planning System
```

`TARGET` принимает `go`, `python`, `java`, `typescript`. `SPEC` задаётся путём относительно `openapi/`. Перед генерацией папка пакета удаляется, так что правки в сгенерированных файлах не сохраняются.

Для Go генерируется сервер, для остальных языков клиент:

| Язык | Генератор | Что получается |
| --- | --- | --- |
| Go | `go-server`, роутер chi | Модели, интерфейсы сервисов `...Servicer` и роутер. Реализацию сервиса пишете сами |
| Python | `python`, библиотека httpx | Асинхронный клиент на pydantic 2 |
| Java | `java`, библиотека `native` | Клиент на `java.net.http.HttpClient` и Jackson |
| TypeScript | `typescript-fetch` | Клиент на `fetch` |

Имена пакетов выводятся из пути к спецификации:

| Спецификация | Go | Python | Java | TypeScript |
| --- | --- | --- | --- | --- |
| `reference-manager/currency/v1` | `currency_v1` | `reference_manager.currency.v1` | `ru.mephi.arch.api.referencemanager.currency.v1` | `arch-api/reference-manager/currency/v1` |
| `qa/v1` | `qa_v1` | `qa.v1` | `ru.mephi.arch.api.qa.v1` | `arch-api/qa/v1` |
| `planning-system/v1` | `planning_system_v1` | `planning_system.v1` | `ru.mephi.arch.api.planningsystem.v1` | `arch-api/planning-system/v1` |
| `planning-system/runtime/v1` | `runtime_v1` | `planning_system.runtime.v1` | `ru.mephi.arch.api.planningsystem.runtime.v1` | `arch-api/planning-system/runtime/v1` |
| `reports/v1` | `reports_v1` | `reports.v1` | `ru.mephi.arch.api.reports.v1` | `arch-api/reports/v1` |
| `task-tracker/v1` | `task_tracker_v1` | `task_tracker.v1` | `ru.mephi.arch.api.tasktracker.v1` | `arch-api/task-tracker/v1` |

Файлы `out/go/go.mod`, `out/python/pyproject.toml`, `out/java/pom.xml` и `out/typescript/package.json` написаны вручную, генератор их не трогает. Если сгенерированному коду понадобится новая зависимость, её нужно добавить туда (кроме Go: там это делает `go mod tidy`).

### Новая спецификация

Исходники спецификаций хранятся у команд. Пути к ним указаны в
[`sync-specs.py`](sync-specs.py). После правки исходника выполните из `api/`:

```bash
task sync-specs
task generate SPEC=planning-system/v1  # подставьте путь нужной спецификации
```

Включите обновлённую копию из `openapi/` в тот же PR. CI проверяет её совпадение
с исходником. У Planning System два отдельных контракта — основной HTTP API и
дополнительные маршруты приложения. Историческое предложение D-01 по приёмнику
Task Tracker остаётся в документации Planning System. В общем каталоге для
Task Tracker используется спецификация самого Task Tracker.

При добавлении спецификации укажите исходник и путь в каталоге в `sync-specs.py`.
Для каждого пакета используйте один файл `openapi.yaml` или `openapi.json`.
После удаления или переименования спецификации удалите её старую копию и
сгенерированный пакет вручную.

### Новый язык

Добавьте язык в `ALL_LANGS`, создайте `configs/<язык>.yaml` и задачу `generate:<язык>` по образцу существующих.

### Что исправляется после генерации

Генератор выдаёт код, который в некоторых случаях не собирается, поэтому задачи его дорабатывают:

- Go: `goimports` убирает неиспользуемые импорты, `go-server` иногда добавляет лишний `errors`. В `configs/go.yaml` включён `enumClassPrefix`, иначе значения разных enum с одинаковыми именами (`DRAFT`, `ARCHIVED`) конфликтуют в одном пакете. Поэтому константы называются `TESTPLANSTATUS_DRAFT`, а не `DRAFT`.
- TypeScript: в начало каждого файла дописывается `// @ts-nocheck`. В сгенерированном коде есть неиспользуемые переменные, и без этой строки `tsc` во фронтендах с `noUnusedLocals` падает.
- Java и Go: удаляются пустые папки, которые генератор создаёт для пропущенных файлов.
- Go: модель Planning System `Operation` называется `ApiOperation` в сгенерированном пакете, чтобы избежать конфликта со служебным типом генератора.
- Java: метод Task Tracker для создания дефекта принимает `JsonNode`. Генератор 7.26.0 не строит класс для сочетания `anyOf` и `allOf` в `CreateBugRequest`. Правила запроса сохраняются в OpenAPI.

Генератор не умеет `default` у полей `format: date-time`: Java-код с таким полем не компилируется. Не указывайте `default` для дат.

## Подключение

Go, в `go.mod` сервиса (путь в `replace` указан относительно `reference-manager/backend`):

```
require github.com/MEPhI-C22-501/arch-info-system-monorepo/api/out/go v0.0.0

replace github.com/MEPhI-C22-501/arch-info-system-monorepo/api/out/go => ../../api/out/go
```

Python:

```bash
uv add ../../api/out/python
```

```python
from qa.v1 import ApiClient, Configuration, TestCasesApi
```

Java: выполните `mvn install` в `out/java` и добавьте зависимость `ru.mephi.arch:arch-api:0.1.0`.

TypeScript, в `package.json`:

```json
"arch-api": "file:../../api/out/typescript"
```

```ts
import { Configuration, TestCasesApi } from "arch-api/qa/v1";
```

## Swagger UI

```bash
task swagger                    # http://localhost:8080
task swagger SWAGGER_PORT=8081
```

Открывает в Docker Swagger UI со всеми спецификациями из `openapi/`, переключаются они списком в правом верхнем углу. Файлы читаются с диска: после правки спецификации обновите страницу. Остановка: `Ctrl+C`.

Контейнер называется `api_swagger_ui` и не конфликтует с `task swagger` из `reference-manager`, если порты разные.
