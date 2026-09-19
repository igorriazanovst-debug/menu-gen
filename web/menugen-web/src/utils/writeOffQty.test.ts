import { fmtWriteOffQty } from './writeOffQty';

describe('fmtWriteOffQty', () => {
  it('убирает хвостовые нули дробной части', () => {
    expect(fmtWriteOffQty('200.00')).toBe('200');
    expect(fmtWriteOffQty('1.00')).toBe('1');
    expect(fmtWriteOffQty('0.50')).toBe('0.5');
  });

  it('целое без точки не трогает', () => {
    // Иначе «1000» превратилось бы в «1» — цена такой ошибки в холодильнике
    // видна не сразу.
    expect(fmtWriteOffQty('1000')).toBe('1000');
    expect(fmtWriteOffQty('30')).toBe('30');
  });

  it('значащие цифры сохраняет', () => {
    expect(fmtWriteOffQty('1.25')).toBe('1.25');
    expect(fmtWriteOffQty('1030.00')).toBe('1030');
  });

  it('пустое и число переживает', () => {
    expect(fmtWriteOffQty(null)).toBe('');
    expect(fmtWriteOffQty(undefined)).toBe('');
    expect(fmtWriteOffQty(7)).toBe('7');
  });
});
