# Reference Manager

Кратко:

Сервис **«Справочник»** — это централизованный сервис ERP для хранения общих справочных данных: стран, валют, языков, единиц измерения, типов оплаты, налоговых категорий и т.д.

Основная модель простая: есть **справочник** (`Catalog`), например `currencies`, и есть его **значения** (`CatalogItem`), например `EUR`, `USD`, `GBP`.

Главные принципы:

* каждый элемент имеет `id`, `code`, `name`, `status`, дополнительные `attributes`;
* `id` и `code` стабильны;
* вместо удаления используется `ACTIVE / INACTIVE`;
* поддерживаются системные и tenant-specific справочники;
* изменения справочников публикуются через события;
* другие ERP-сервисы не ходят напрямую в БД справочника, только через API/события;
* справочник хранит только reference data, но не бизнес-сущности вроде `User`, `Employee`, `Product`, `Invoice`;
* все изменения аудируются и версионируются;
* для расширяемых данных используется `JSONB` + schema validation.

Пример API:

```http
GET  /api/reference-data/v1/catalogs
GET  /api/reference-data/v1/catalogs/currencies/items
GET  /api/reference-data/v1/catalogs/currencies/items/by-code/EUR
POST /api/reference-data/v1/catalogs/currencies/items
PATCH /api/reference-data/v1/catalogs/currencies/items/{id}
```