// MG_SCANSRC: строка КБЖУ при скане.
import { productKbjuLine } from './productKbju';
import type { Product } from '../types';

const p = (over: Partial<Product>): Product => ({ id: 1, name: 'Творог', ...over }) as Product;

describe('productKbjuLine', () => {
  it('собирает калории и БЖУ', () => {
    const line = productKbjuLine(p({ calories_per_100g: 121, nutrition: { proteins: 16, fats: 5, carbs: 3 } }));

    expect(line).toBe('121 ккал · Б 16 · Ж 5 · У 3 (на 100 г)');
  });

  it('калории приходят строкой из DecimalField — это не текст «121.00»', () => {
    expect(productKbjuLine(p({ calories_per_100g: '121.00' }))).toBe('121 ккал (на 100 г)');
  });

  it('дробное не округляет до нуля знаков', () => {
    expect(productKbjuLine(p({ calories_per_100g: 250, nutrition: { fats: 3.2 } }))).toBe(
      '250 ккал · Ж 3.2 (на 100 г)',
    );
  });

  it('без данных строки нет — пустое «0 ккал» хуже молчания', () => {
    expect(productKbjuLine(p({ calories_per_100g: null, nutrition: {} }))).toBeNull();
    expect(productKbjuLine(p({}))).toBeNull();
    expect(productKbjuLine(null)).toBeNull();
  });

  it('показывает то, что есть, даже если известны не все поля', () => {
    expect(productKbjuLine(p({ nutrition: { proteins: 0.2 } }))).toBe('Б 0.2 (на 100 г)');
  });
});
