# api

OpenAPI-спецификации модулей и код, сгенерированный по ним. Спецификации лежат в `openapi/`, результат генерации попадает в `out/`.

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

Ставить ничего не нужно, достаточно запущенного Docker:

```bash
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/local" \
  openapitools/openapi-generator-cli version
```

### Проверка

```bash
openapi-generator-cli version
```

## Генерация

```bash
task generate
```

Задача описана в [Taskfile.yaml](Taskfile.yaml) и сейчас запускает генератор через Docker.
