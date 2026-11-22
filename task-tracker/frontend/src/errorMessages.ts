type ErrorDetail = { row?: number; field: string; reason: string };

const reasons: Record<string, string> = {
  internal_error: 'На сервере произошла ошибка. Попробуйте ещё раз.',
  not_planned: 'Запустить можно только запланированную итерацию. Обновите страницу.',
  not_active: 'Завершить можно только активную итерацию. Обновите страницу.',
  completed: 'Завершённую итерацию нельзя изменять.',
  forbidden: 'Недостаточно прав для этого действия.',
  insufficient_scope: 'Недостаточно прав для этого действия.',
  stale_work_item: 'Задача уже изменена. Обновите карточку и повторите действие.',
  already_in_unfinished_iteration: 'Задача уже включена в другую незавершённую итерацию.',
  required: 'Заполните обязательное поле.',
  invalid_hours: 'Укажите корректное количество часов с точностью до сотых.',
  invalid_range: 'Дата окончания должна быть не раньше даты начала.',
  before_start_date: 'Срок должен быть не раньше даты начала.',
  not_found: 'Запись не найдена. Возможно, она была удалена.',
  constraint_violation: 'Действие не удалось выполнить из-за связанных данных. Обновите страницу и проверьте изменения.',
};

const fields: Record<string, string> = {
  name: 'Название', startDate: 'Дата начала', endDate: 'Дата окончания',
  dueDate: 'Срок', hours: 'Часы', availableHours: 'Доступные часы',
  userId: 'Участник', title: 'Название', plannedHours: 'Плановая оценка',
};

export function errorMessage(status: number, errors: ErrorDetail[] = []): string {
  if (status >= 500) return reasons.internal_error;
  if (!errors.length) return status === 403 ? reasons.forbidden : 'Не удалось выполнить действие. Проверьте данные и повторите попытку.';
  return errors.map(error => {
    const message = reasons[error.reason] ?? 'Не удалось выполнить действие. Проверьте данные и повторите попытку.';
    const field = fields[error.field];
    return `${error.row ? `Строка ${error.row}. ` : ''}${field ? `${field}: ` : ''}${message}`;
  }).join(' ');
}
