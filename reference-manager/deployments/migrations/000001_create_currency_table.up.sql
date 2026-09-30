create table currency (
  uid uuid primary key,

  name varchar(255) not null unique,

  code varchar(3) not null unique,
  numeric_code varchar(3) not null unique,
  display_name varchar(255) not null,
  minor_units smallint not null,

  create_time timestamptz not null,
  update_time timestamptz not null,
);