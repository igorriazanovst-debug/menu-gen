// MG_DIARYSCAN: фасовка из справочника → граммы для дневника.
import { packageGrams } from './packageSize';

describe('packageGrams', () => {
  it('граммы и миллилитры берутся как есть', () => {
    expect(packageGrams('250г')).toBe(250);
    expect(packageGrams('930мл')).toBe(930);
    expect(packageGrams('300 г')).toBe(300);
  });

  it('килограммы и литры переводятся', () => {
    expect(packageGrams('1кг')).toBe(1000);
    expect(packageGrams('1,5л')).toBe(1500);
  });

  it('пачка из нескольких пакетиков считается целиком', () => {
    expect(packageGrams('4.5г x 4 шт')).toBe(18);
    // Кириллическая «х» на этикетках неотличима от латинской — считаем так же.
    expect(packageGrams('2г х 25шт')).toBe(50);
  });

  it('нечитаемая фасовка — не повод выдумывать число', () => {
    expect(packageGrams('упак')).toBeNull();
    expect(packageGrams('')).toBeNull();
    expect(packageGrams(null)).toBeNull();
    expect(packageGrams('шт')).toBeNull();
  });

  it('нелепые величины отбрасываются', () => {
    expect(packageGrams('50кг')).toBeNull();
  });

  it('размер вытаскивается из хвоста названия', () => {
    expect(packageGrams('Молоко Простоквашино 3.2%, 930мл')).toBe(930);
  });
});
