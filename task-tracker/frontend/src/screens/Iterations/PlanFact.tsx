import { hours } from '../../api';
import type { Item, Iteration, Json } from '../../api';
import { selectName } from '../../context';
import type { Context } from '../../context';
import { compareAssignee } from '../../metrics';

export function PlanFact({ baseline, result, context }: { baseline: Json; result: Json; context: Context }) {
  const actual = (result.actual || {}) as Json;
  const plannedItems = (Array.isArray(baseline.items) ? baseline.items : []) as Item[];
  const actualItems = (Array.isArray(actual.items) ? actual.items : []) as Item[];
  const baselineCapacity = (Array.isArray(baseline.capacity) ? baseline.capacity : []) as Iteration['capacity'];
  const actualCapacity = (Array.isArray(actual.capacity) ? actual.capacity : []) as Iteration['capacity'];
  return <div className="panel">
    <h3>Сравнение плана и факта</h3>
    <div className="metric-grid">
      <div><small>Базовый план</small><strong>{hours(baseline.plannedHours)}</strong></div>
      <div><small>Факт на завершение</small><strong>{hours(actual.actualHours)}</strong></div>
      <div><small>Отклонение</small><strong>{hours(result.deviationHours)}</strong></div>
    </div>
    <h4>По элементам</h4>
    <div className="table-scroll"><table>
      <thead><tr><th>Элемент</th><th>План при запуске</th><th>План при завершении</th><th>Факт</th><th>Отклонение</th></tr></thead>
      <tbody>{plannedItems.map(item => {
        const current = actualItems.find(row => row.id === item.id);
        return <tr key={item.id}>
          <td>{item.title}</td><td>{hours(item.plannedHours)}</td>
          <td>{current ? hours(current.plannedHours) : 'Исключён'}</td><td>{hours(current?.actualHours)}</td>
          <td className={Number(current?.actualHours || 0) > Number(item.plannedHours) ? 'negative' : ''}>{hours(Number(current?.actualHours || 0) - Number(item.plannedHours))}</td>
        </tr>;
      })}</tbody>
    </table></div>
    <h4>По исполнителям</h4>
    <div className="table-scroll"><table>
      <thead><tr><th>Исполнитель</th><th>План при запуске</th><th>План при завершении</th><th>Факт</th><th>Отклонение</th><th>Ёмкость</th></tr></thead>
      <tbody>{baselineCapacity.map(entry => {
        const current = actualCapacity.find(row => row.userId === entry.userId);
        const comparison = compareAssignee(entry, current);
        return <tr key={entry.userId}>
          <td>{selectName(context.users, entry.userId)}</td><td>{hours(comparison.planned)}</td><td>{hours(comparison.currentPlan)}</td>
          <td>{hours(comparison.actual)}</td>
          <td className={comparison.deviation > 0 ? 'negative' : ''}>{hours(comparison.deviation)}</td>
          <td>{hours(comparison.available)}</td>
        </tr>;
      })}</tbody>
    </table></div>
  </div>;
}
