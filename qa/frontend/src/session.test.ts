import { afterEach, expect, test } from 'vitest';
import { clearSession, isValidName, loadSession, saveSession, tokenOf } from './session';

afterEach(() => clearSession());

test('токен собирается из роли и имени', () => {
  expect(tokenOf({ role: 'qa-viewer', name: 'petrov' })).toBe('demo-qa-viewer@petrov');
});

test('кириллица и @ в имени недопустимы: заголовок не примет такой токен', () => {
  expect(isValidName('ivanov.a-1_b')).toBe(true);
  expect(isValidName('Иванов')).toBe(false);
  expect(isValidName('a@b')).toBe(false);
  expect(isValidName('')).toBe(false);
});

test('сессия переживает перезагрузку, а повреждённая — отбрасывается', () => {
  saveSession({ role: 'qa-lead', name: 'ivanov' });
  expect(loadSession()).toEqual({ role: 'qa-lead', name: 'ivanov' });
  localStorage.setItem('qa.session', '{не json');
  expect(loadSession()).toBeNull();
  localStorage.setItem('qa.session', JSON.stringify({ role: 'root', name: 'x' }));
  expect(loadSession()).toBeNull();
});
