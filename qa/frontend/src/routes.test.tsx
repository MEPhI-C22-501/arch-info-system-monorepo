import { generatePath, matchPath } from 'react-router';
import { describe, expect, test } from 'vitest';
import { isRouteAllowed, menuFor, routes, startPath } from './routes';
import { ROLES } from './session';

describe('маршруты', () => {
  test('пути не повторяются', () => {
    const paths = routes.map((route) => route.path);
    expect(new Set(paths).size).toBe(paths.length);
  });

  test('меню строится из маршрутов и не ведёт на экраны с параметрами', () => {
    for (const role of ROLES) {
      for (const item of menuFor(role)) {
        expect(routes.some((route) => route.path === item.path && route.menu === item.label)).toBe(true);
        expect(item.path).not.toContain(':');
      }
    }
  });

  test('меню читателя содержит разделы без администрирования', () => {
    expect(menuFor('qa-viewer').map((item) => item.label)).toEqual(['Тест-кейсы', 'Наборы', 'Планы', 'Прогоны', 'Дефекты', 'Состояние тестирования']);
  });

  test('администрирование видит только qa-admin (070, раздел 5)', () => {
    for (const role of ROLES) {
      expect(menuFor(role).some((item) => item.path === '/admin')).toBe(role === 'qa-admin');
    }
  });

  test('экраны создания недоступны ролям без права', () => {
    const route = (path: string) => routes.find((item) => item.path === path)!;
    expect(isRouteAllowed(route('/plans/new'), 'qa-tester')).toBe(false);
    expect(isRouteAllowed(route('/plans/new'), 'qa-lead')).toBe(true);
    expect(isRouteAllowed(route('/test-cases/new'), 'qa-viewer')).toBe(false);
    expect(isRouteAllowed(route('/runs/new'), 'qa-admin')).toBe(false);
  });

  test('ссылки из «Ошибки» Task Tracker открывают карточки (130, раздел 1)', () => {
    const paths = routes.map((route) => route.path);
    expect(paths).toContain('/runs/:id');
    expect(paths).toContain('/test-cases/:id');
    expect(matchPath('/runs/:id', generatePath('/runs/:id', { id: 'abc' }))?.params.id).toBe('abc');
  });

  test('стартовый экран зависит от роли (110, раздел 3)', () => {
    expect(startPath('qa-lead')).toBe('/overview');
    expect(startPath('qa-tester')).toBe('/runs?status=IN_PROGRESS');
    expect(startPath('qa-viewer')).toBe('/test-cases');
    expect(startPath('qa-admin')).toBe('/test-cases');
  });
});
