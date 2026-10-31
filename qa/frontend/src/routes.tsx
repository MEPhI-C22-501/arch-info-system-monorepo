import { ReactElement } from 'react';
import { Role } from './session';
import { Admin } from './screens/Admin';
import { CaseCard } from './screens/CaseCard';
import { CaseCreate } from './screens/CaseCreate';
import { CasesList } from './screens/CasesList';
import { DefectCard } from './screens/DefectCard';
import { DefectsList } from './screens/DefectsList';
import { ExecuteCase } from './screens/ExecuteCase';
import { Overview } from './screens/Overview';
import { PlanCard } from './screens/PlanCard';
import { PlanCreate } from './screens/PlanCreate';
import { PlansList } from './screens/PlansList';
import { RunCard } from './screens/RunCard';
import { RunCreate } from './screens/RunCreate';
import { RunsList } from './screens/RunsList';
import { SuiteCard } from './screens/SuiteCard';
import { SuiteCreate } from './screens/SuiteCreate';
import { SuitesList } from './screens/SuitesList';

export type AppRoute = {
  path: string;
  element: ReactElement;
  // Подпись в боковом меню; без неё экран открывается только переходом.
  menu?: string;
  // Кому доступен экран; без поля — всем ролям.
  roles?: Role[];
};

const EDITORS: Role[] = ['qa-tester', 'qa-automation', 'qa-lead'];

// Адреса /runs/:id и /test-cases/:id — часть контракта: на них ведут ссылки из «Ошибки» (130, раздел 1).
export const routes: AppRoute[] = [
  { path: '/test-cases', element: <CasesList />, menu: 'Тест-кейсы' },
  { path: '/test-cases/new', element: <CaseCreate />, roles: EDITORS },
  { path: '/test-cases/:id', element: <CaseCard /> },
  { path: '/suites', element: <SuitesList />, menu: 'Наборы' },
  { path: '/suites/new', element: <SuiteCreate />, roles: EDITORS },
  { path: '/suites/:id', element: <SuiteCard /> },
  { path: '/plans', element: <PlansList />, menu: 'Планы' },
  { path: '/plans/new', element: <PlanCreate />, roles: ['qa-lead'] },
  { path: '/plans/:id', element: <PlanCard /> },
  { path: '/runs', element: <RunsList />, menu: 'Прогоны' },
  { path: '/runs/new', element: <RunCreate />, roles: EDITORS },
  { path: '/runs/:id', element: <RunCard /> },
  { path: '/runs/:id/results/:resultId', element: <ExecuteCase /> },
  { path: '/defects', element: <DefectsList />, menu: 'Дефекты' },
  { path: '/defects/:id', element: <DefectCard /> },
  { path: '/overview', element: <Overview />, menu: 'Состояние тестирования' },
  { path: '/admin', element: <Admin />, menu: 'Администрирование', roles: ['qa-admin'] },
];

export function isRouteAllowed(route: Pick<AppRoute, 'roles'>, role: Role): boolean {
  return !route.roles || route.roles.includes(role);
}

export function menuFor(role: Role): { path: string; label: string }[] {
  return routes.flatMap((route) => (route.menu && isRouteAllowed(route, role) ? [{ path: route.path, label: route.menu }] : []));
}

// Стартовый экран по роли (110, раздел 3); экрана «мои кейсы» тестировщика нет, ему — выполняющиеся прогоны.
export function startPath(role: Role): string {
  if (role === 'qa-lead') return '/overview';
  if (role === 'qa-tester') return '/runs?status=IN_PROGRESS';
  return '/test-cases';
}
