// MG_PAYRELIABLE: чем закончилась оплата, когда человек вернулся.
//
// ЮKassa возвращает на return_url без параметров, а идентификатор платежа
// известен только ПОСЛЕ создания — подставить его в return_url заранее нельзя.
// Поэтому запоминаем его перед уходом на оплату и спрашиваем статус по
// возвращении. Ждать уведомления нельзя: оно может опоздать, а человек уже
// смотрит на экран.

const KEY = 'menugen_pending_payment';

export function rememberPayment(paymentId: string): void {
  try {
    localStorage.setItem(KEY, paymentId);
  } catch {
    // приватный режим — переживём, просто не покажем результат
  }
}

export function takePendingPayment(): string | null {
  try {
    const id = localStorage.getItem(KEY);
    if (id) localStorage.removeItem(KEY);
    return id || null;
  } catch {
    return null;
  }
}

export function forgetPayment(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
