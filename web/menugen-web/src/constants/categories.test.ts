// MG_CATRU: чипы категорий в карточках рецептов должны быть по-русски.
// Баг возвращался — тест фиксирует перевод ключевых токенов.
import { categoryLabel } from './categories';

describe('categoryLabel', () => {
  it('переводит типы блюд (DishType)', () => {
    expect(categoryLabel('dessert')).toBe('Десерт');
    expect(categoryLabel('bakery')).toBe('Выпечка');
    expect(categoryLabel('side')).toBe('Гарнир');
    expect(categoryLabel('main')).toBe('Второе/горячее');
    expect(categoryLabel('soup')).toBe('Первое (суп)');
  });

  it('переводит типы приёмов пищи', () => {
    expect(categoryLabel('breakfast')).toBe('Завтрак');
    expect(categoryLabel('lunch')).toBe('Обед');
    expect(categoryLabel('dinner')).toBe('Ужин');
  });

  it('не зависит от регистра и пробелов', () => {
    expect(categoryLabel(' Dessert ')).toBe('Десерт');
    expect(categoryLabel('SIDE')).toBe('Гарнир');
  });

  it('незнакомый токен возвращает как есть', () => {
    expect(categoryLabel('пельмени')).toBe('пельмени');
    expect(categoryLabel('unknown_token')).toBe('unknown_token');
  });
});
