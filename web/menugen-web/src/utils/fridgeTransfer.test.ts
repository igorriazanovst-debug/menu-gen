// MG_SHOP2FRIDGE / MG_SHAREERR: отбор позиций для холодильника и разбор ошибок API.
import { fridgeCandidates, fridgeConfirmText } from './fridgeTransfer';
import { apiErrorMessage } from './apiError';
import type { ShoppingV2Item } from '../types';

const item = (over: Partial<ShoppingV2Item>): ShoppingV2Item =>
  ({
    id: 1,
    name: 'Молоко',
    is_purchased: true,
    in_fridge: false,
    fridge_eligible: true,
    ...over,
  }) as ShoppingV2Item;

describe('fridgeCandidates', () => {
  it('берёт только купленное', () => {
    const items = [item({ id: 1 }), item({ id: 2, is_purchased: false })];

    expect(fridgeCandidates(items).map((i) => i.id)).toEqual([1]);
  });

  it('пропускает уже лежащее в холодильнике', () => {
    expect(fridgeCandidates([item({ id: 1, in_fridge: true })])).toEqual([]);
  });

  it('пропускает несъедобное (корм, химия, гигиена)', () => {
    expect(fridgeCandidates([item({ id: 1, fridge_eligible: false })])).toEqual([]);
  });

  it('на пустом списке ничего не предлагает', () => {
    expect(fridgeCandidates([])).toEqual([]);
  });
});

describe('fridgeConfirmText', () => {
  it('называет количество и перечисляет позиции', () => {
    const text = fridgeConfirmText([item({ id: 1, name: 'Молоко' }), item({ id: 2, name: 'Сыр' })]);

    expect(text).toContain('Добавить в холодильник: 2?');
    expect(text).toContain('Молоко, Сыр');
  });

  it('длинный список сворачивает', () => {
    const many = Array.from({ length: 8 }, (_, i) => item({ id: i, name: `Товар${i}` }));

    const text = fridgeConfirmText(many);

    expect(text).toContain('Добавить в холодильник: 8?');
    expect(text).toContain('и ещё 3');
  });
});

describe('apiErrorMessage', () => {
  const err = (data: unknown) => ({ response: { data } });

  it('читает поле-строку — раньше отсюда бралась первая буква', () => {
    expect(apiErrorMessage(err({ email: 'Пользователь не найден.' }), ['email'])).toBe(
      'Пользователь не найден.',
    );
  });

  it('читает поле-список', () => {
    expect(apiErrorMessage(err({ email: ['Пользователь не найден.'] }), ['email'])).toBe(
      'Пользователь не найден.',
    );
  });

  it('detail и non_field_errors тоже подходят', () => {
    expect(apiErrorMessage(err({ detail: 'Нет прав.' }))).toBe('Нет прав.');
    expect(apiErrorMessage(err({ non_field_errors: ['Неверные данные.'] }))).toBe('Неверные данные.');
  });

  it('приоритет у названных полей', () => {
    const message = apiErrorMessage(err({ detail: 'Общая', phone: ['Номер не найден.'] }), ['phone']);

    expect(message).toBe('Номер не найден.');
  });

  it('код ошибки за сообщение не выдаётся', () => {
    expect(apiErrorMessage(err({ code: 'in_fridge' }))).toBeNull();
  });

  it('пустой ответ и не-объект переживает молча', () => {
    expect(apiErrorMessage(err(undefined))).toBeNull();
    expect(apiErrorMessage(new Error('boom'))).toBeNull();
    expect(apiErrorMessage(err('Ошибка сервера'))).toBe('Ошибка сервера');
  });
});
