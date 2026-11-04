// what the screens show, without the DOM: the states of a list and of a failed request (document 110), the model
// of the record form by role and record state, the text of a table cell; app.js draws these models
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./catalogs.js'), require('./format.js'));
  else (root.RM = root.RM || {}).views = factory(root.RM.catalogs, root.RM.format);
})(globalThis, function (catalogs, format) {
  'use strict';

  const { can, inputFields, fieldByName, CATALOGS } = catalogs;

  // a selection narrows the list: a filter, the deleted records shown or a moment in the past
  function hasSelection(params) {
    return Boolean(params && (params.filter || params.allowDeleted || params.readTime));
  }

  // the state shown instead of the rows of an empty page
  function emptyState(collection, user, params) {
    if (params && params.readTime) {
      return {
        kind: 'no-match',
        title: 'Ничего не найдено',
        text: 'На выбранный момент таких записей не было. Выберите другой момент или сбросьте отбор.',
        action: 'reset',
      };
    }
    if (hasSelection(params)) {
      return {
        kind: 'no-match',
        title: 'Ничего не найдено',
        text: 'Ни одна запись не подходит под условия отбора. Измените фильтр или сбросьте его.',
        action: 'reset',
      };
    }
    const canCreate = can(user, collection, 'C');
    return {
      kind: 'empty',
      title: 'Записей пока нет',
      text: canCreate ? 'Справочник пуст. Создайте первую запись.' : 'Справочник пуст. Записи появятся, когда их создаст администратор справочника.',
      action: canCreate ? 'create' : null,
    };
  }

  // a failed request as a screen state: the title, the explanation and whether repeating the request can help;
  // an error without a status is a request that has not reached the service
  function errorState(error) {
    const status = error && error.status;
    const message = (error && error.message) || '';
    if (!status) {
      return { kind: 'unavailable', title: 'Сервис недоступен', text: 'Запрос не дошёл до сервиса. Проверьте подключение и повторите.', retry: true };
    }
    switch (status) {
      case 400:
        return { kind: 'invalid', title: 'Запрос отклонён', text: `Сервис отклонил запрос: ${message}.`, retry: false };
      case 401:
        return { kind: 'session', title: 'Сессия истекла', text: 'Выполняется повторный вход через Keycloak.', retry: false };
      case 403:
        return { kind: 'denied', title: 'Нет доступа', text: 'У ваших ролей нет нужного уровня на эту группу справочников. Доступ выдаёт администратор Keycloak.', retry: false };
      case 404:
        return { kind: 'not-found', title: 'Не найдено', text: 'Такой записи нет или она удалена.', retry: false };
      case 409:
        return { kind: 'conflict', title: 'Конфликт изменений', text: 'Запись изменена параллельно или такая запись уже есть. Перечитайте запись и повторите.', retry: true };
      case 429:
        return { kind: 'busy', title: 'Слишком много запросов', text: 'Сервис ограничил частоту запросов. Повторите через несколько секунд.', retry: true };
      case 503:
        return { kind: 'unavailable', title: 'Сервис временно недоступен', text: `Зависимость сервиса не ответила: ${message}. Повторите позже.`, retry: true };
      default:
        if (status >= 500) {
          return { kind: 'error', title: 'Ошибка сервиса', text: 'Сервис не смог выполнить запрос. Повторите позже, при повторе сообщите идентификатор трассы.', retry: true };
        }
        return { kind: 'error', title: `Ошибка ${status}`, text: message, retry: false };
    }
  }

  // the record form: whether it can be saved, the state of every field and the actions in their order
  function formModel(collection, rec, user, query) {
    const isNew = !rec;
    const editable = isNew ? can(user, collection, 'C') : can(user, collection, 'U') && !rec.is_deleted;
    const prefilled = (name) => Boolean(isNew && query && typeof query.has === 'function' && query.has(name));

    const fields = inputFields(collection).map((field) => {
      const notes = [field.name];
      if (field.required) notes.push('обязательно');
      if (field.immutable && !isNew) notes.push('не меняется');
      if (field.hint) notes.push(field.hint);
      if (field.type === 'ref') notes.push(`идентификатор записи ${field.ref}`);
      return {
        field,
        name: field.name,
        label: field.label,
        required: Boolean(field.required),
        locked: !editable || Boolean(field.immutable && (!isNew || prefilled(field.name))),
        notes: notes.join(', '),
      };
    });

    const actions = [];
    if (editable) actions.push('save');
    if (!isNew && can(user, collection, 'D')) actions.push(rec.is_deleted ? 'purge' : 'delete');
    actions.push('back');

    let readOnlyReason = null;
    if (!editable) readOnlyReason = !isNew && rec.is_deleted ? 'deleted' : 'role';

    return { isNew, editable, fields, actions, readOnlyReason };
  }

  const TIME_COLUMNS = new Set(['created_at', 'updated_at', 'deleted_at']);

  // the text and the kind of a table cell, references are resolved to names by the screen itself
  function cell(collection, column, value) {
    if (column === 'id') return { kind: 'id', text: `#${value}` };
    if (column === 'is_deleted') return { kind: 'state', text: value ? 'DELETED' : 'ACTIVE' };
    if (format.isEmpty(value)) return { kind: 'empty', text: 'пусто' };
    if (TIME_COLUMNS.has(column)) return { kind: 'time', text: format.dateTime(value), iso: String(value) };
    const field = fieldByName(collection, column);
    const type = field ? field.type : typeof value;
    switch (type) {
      case 'enum':
        return { kind: 'enum', text: String(value) };
      case 'ref':
        return { kind: 'ref', text: `#${value}`, ref: field.ref };
      case 'date':
        return { kind: 'date', text: format.date(value), iso: String(value) };
      case 'money':
        return { kind: 'num', text: format.money(value) };
      case 'integer':
      case 'number':
        return { kind: 'num', text: String(value) };
      case 'boolean':
        return { kind: 'text', text: value ? 'да' : 'нет' };
      default:
        return { kind: 'text', text: String(value) };
    }
  }

  // a short description of the selection for the caption of the table and the export
  function selectionText(params) {
    const parts = [];
    if (params && params.filter) parts.push(`фильтр ${params.filter}`);
    if (params && params.orderBy) parts.push(`сортировка ${params.orderBy}`);
    if (params && params.allowDeleted) parts.push('с удалёнными записями');
    if (params && params.readTime) parts.push(`на момент ${format.dateTime(params.readTime)}`);
    return parts.length ? parts.join(', ') : 'все активные записи в порядке создания';
  }

  function title(collection) {
    return CATALOGS[collection] ? CATALOGS[collection].title : collection;
  }

  return { hasSelection, emptyState, errorState, formModel, cell, selectionText, title };
});
