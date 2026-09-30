create table currency (
  id uuid primary key,

  code varchar(3) not null unique,
  numeric_code varchar(3) not null unique,
  name varchar(255) not null,
  minor_units smallint,

  created_at timestamp not null,
  updated_at timestamp not null
);

comment on table currency is
  'Справочник валют по стандарту ISO 4217';

comment on column currency.id is
  'Уникальный идентификатор валюты';

comment on column currency.code is
  'Трёхбуквенный алфавитный код валюты по ISO 4217, например USD';

comment on column currency.numeric_code is
  'Трёхзначный цифровой код валюты по ISO 4217, например 840';

comment on column currency.name is
  'Наименование валюты';

comment on column currency.minor_units is
  'Количество десятичных знаков младшей денежной единицы по ISO 4217; NULL, если значение не определено';

comment on column currency.created_at is
  'Дата и время создания записи';

comment on column currency.updated_at is
  'Дата и время последнего изменения записи';