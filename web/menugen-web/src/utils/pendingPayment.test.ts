// MG_PAYRELIABLE: идентификатор платежа переживает уход на страницу оплаты.
import { forgetPayment, rememberPayment, takePendingPayment } from './pendingPayment';

describe('pendingPayment', () => {
  beforeEach(() => localStorage.clear());

  it('запомненный платёж возвращается ровно один раз', () => {
    // Второй возврат на страницу не должен повторно показывать результат.
    rememberPayment('pay-1');

    expect(takePendingPayment()).toBe('pay-1');
    expect(takePendingPayment()).toBeNull();
  });

  it('без платежа — ничего', () => {
    expect(takePendingPayment()).toBeNull();
  });

  it('отменённый платёж забывается', () => {
    rememberPayment('pay-2');
    forgetPayment();

    expect(takePendingPayment()).toBeNull();
  });

  it('недоступное хранилище не роняет оплату', () => {
    // Приватный режим: setItem бросает. Оплата важнее показа результата.
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error('QuotaExceeded');
    };

    expect(() => rememberPayment('pay-3')).not.toThrow();

    Storage.prototype.setItem = original;
  });
});
