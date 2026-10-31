# arch-info-system-monorepo

Учебный монорепозиторий. Общая среда описана в [infra/README.md](infra/README.md).

Локальный стенд:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

Модули Task Tracker и Reference Manager подключаются отдельно файлом `compose.modules.yaml` и в этот запуск не входят. Секреты локальной демонстрации перечислены в `.env.example`; боевые значения туда не кладутся.

QA System подключается тем же файлом `compose.modules.yaml` (профиль `modules`), запускается и отдельно: [qa/README.md](qa/README.md).
