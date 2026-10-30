import { useSearchParams } from 'react-router';
import { AdminClassifiers } from './AdminClassifiers';
import { AdminEnvironments } from './AdminEnvironments';
import { AdminMapping } from './AdminMapping';
import { AdminTemplates } from './AdminTemplates';

const TABS = [
  { id: 'templates', label: 'Шаблоны', element: <AdminTemplates /> },
  { id: 'classifiers', label: 'Классификаторы', element: <AdminClassifiers /> },
  { id: 'environments', label: 'Окружения', element: <AdminEnvironments /> },
  { id: 'mapping', label: 'Маппинг статусов «Ошибки»', element: <AdminMapping /> },
];

export function Admin() {
  const [params, setParams] = useSearchParams();
  const active = TABS.find((tab) => tab.id === params.get('tab')) ?? TABS[0];
  return (
    <>
      <h2>Администрирование</h2>
      <div className="tabs" role="tablist">
        {TABS.map((tab) => (
          <button key={tab.id} type="button" role="tab" aria-selected={tab.id === active.id} onClick={() => setParams({ tab: tab.id })}>{tab.label}</button>
        ))}
      </div>
      {active.element}
    </>
  );
}
