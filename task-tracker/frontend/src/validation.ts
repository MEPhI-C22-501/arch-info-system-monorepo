export function validateItem(form: Record<string,unknown>): Record<string,string> {
  const errors:Record<string,string>={};
  if (!String(form.title || '').trim()) errors.title='Введите название';
  if (String(form.title || '').length>255) errors.title='Не более 255 символов';
  if (String(form.description || '').length>50000) errors.description='Не более 50 000 символов';
  if (form.startDate && form.dueDate && String(form.dueDate)<String(form.startDate)) errors.dueDate='Срок раньше даты начала';
  if (form.plannedHours!=='' && form.plannedHours!=null && (!/^\d+(\.\d{1,2})?$/.test(String(form.plannedHours)) || Number(form.plannedHours)>9999999999.99)) errors.plannedHours='Введите неотрицательное число, не более двух знаков после запятой';
  if (['PROJECT','EPIC'].includes(String(form.type)) && form.plannedHours) errors.plannedHours='Оценка рассчитывается по дочерним задачам';
  if (['EPIC','SUBTASK'].includes(String(form.type)) && !form.parentId) errors.parentId='Выберите родительский элемент';
  return errors;
}
