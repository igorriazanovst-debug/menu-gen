// MG_SHELFLIFE: даты в окне переноса покупок в холодильник.
//
// Проверяем именно то, что легко перепутать: «поле пустое» и «срока нет» —
// разные вещи. Первое значит «сервер, подставь», второе — «не подставляй».
import { initialExpiry, toPayload } from './TransferToFridgeModal';
import type { ShoppingV2Item } from '../../types';

const item = (over: Partial<ShoppingV2Item>): ShoppingV2Item =>
  ({ id: 1, name: 'Молоко', is_purchased: true, ...over }) as ShoppingV2Item;

describe('initialExpiry', () => {
  it('подставляет подсказку сервера', () => {
    const items = [item({ id: 1, suggested_expiry: '2026-09-01' })];

    expect(initialExpiry(items, true)).toEqual({ 1: '2026-09-01' });
  });

  it('без подсказки поле остаётся пустым — дату не выдумываем', () => {
    const items = [item({ id: 1, suggested_expiry: null }), item({ id: 2 })];

    expect(initialExpiry(items, true)).toEqual({});
  });

  it('семья отключила подстановку — предзаполнения нет', () => {
    const items = [item({ id: 1, suggested_expiry: '2026-09-01' })];

    expect(initialExpiry(items, false)).toEqual({});
  });
});

describe('toPayload', () => {
  it('стёртая дата шлётся как null: это «без срока», а не «подставь сам»', () => {
    expect(toPayload({ 1: '' })).toEqual({ 1: null });
  });

  it('исправленная дата уходит как есть', () => {
    expect(toPayload({ 7: '2026-12-31' })).toEqual({ 7: '2026-12-31' });
  });

  it('ключи — числа: сервер сопоставляет их с id позиций', () => {
    const payload = toPayload({ 3: '2026-01-02' });

    expect(Object.keys(payload).map(Number)).toEqual([3]);
  });

  it('нетронутых позиций в теле нет — по ним решает сервер', () => {
    expect(toPayload({})).toEqual({});
  });
});
