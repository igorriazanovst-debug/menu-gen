import React, { useEffect, useState } from 'react';
import { subscriptionsApi } from '../../api/subscriptions';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { PageSpinner } from '../../components/ui/Spinner';
import { getErrorMessage } from '../../utils/api';
import type { PlanOffer, SubscriptionPlan, Subscription } from '../../types';
import { PeriodPicker, offerPriceNote } from '../../components/subscriptions/PeriodPicker';
import { rememberPayment, takePendingPayment } from '../../utils/pendingPayment';

export const SubscriptionsPage: React.FC = () => {
  const [plans, setPlans]     = useState<SubscriptionPlan[]>([]);
  // MG_PAYPERIOD: периоды покупки и выбранный для каждого тарифа.
  const [offers, setOffers]   = useState<PlanOffer[]>([]);
  const [chosen, setChosen]   = useState<Record<string, string>>({});
  const [current, setCurrent] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState<string | null>(null);
  const [promo, setPromo] = useState('');
  const [promoBusy, setPromoBusy] = useState(false);
  const [promoMsg, setPromoMsg] = useState<{ ok: boolean; text: string } | null>(null);
  // MG_PAYSTUB: баннер результата оплаты после возврата с платёжной страницы.
  const [payMsg, setPayMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // MG_PAYRELIABLE: вернулись с оплаты. Параметру в адресе не верим — он ничего
  // не доказывает; спрашиваем бэкенд, а тот спрашивает ЮKassa.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const cancelled = params.get('payment') === 'cancel';
    if (params.get('payment')) window.history.replaceState({}, '', '/subscriptions');

    const paymentId = takePendingPayment();
    if (!paymentId) {
      if (cancelled) setPayMsg({ ok: false, text: 'Оплата отменена.' });
      return;
    }

    subscriptionsApi.paymentStatus(paymentId)
      .then(({ data }) => {
        if (data.status === 'succeeded') {
          const until = data.expires_at ? new Date(data.expires_at).toLocaleDateString('ru') : '';
          setPayMsg({ ok: true, text: `Оплата прошла — премиум действует до ${until}.` });
          subscriptionsApi.current().then((r) => setCurrent(r.data)).catch(() => {});
        } else if (data.status === 'cancelled') {
          setPayMsg({ ok: false, text: 'Оплата отменена.' });
        } else {
          setPayMsg({ ok: false, text: 'Платёж ещё обрабатывается. Обновите страницу через минуту.' });
        }
      })
      .catch(() => setPayMsg({ ok: false, text: 'Не удалось проверить платёж. Обновите страницу позже.' }));
  }, []);

  useEffect(() => {
    Promise.allSettled([
      subscriptionsApi.plans().then((r) => {
        const d = r.data as any;
        if (Array.isArray(d)) setPlans(d);
        else if (d && Array.isArray(d.results)) setPlans(d.results);
        else setPlans([]);
      }),
      subscriptionsApi.current().then((r) => setCurrent(r.data)).catch(() => {}),
      subscriptionsApi.offers().then((r) => {
        const d = r.data as PlanOffer[] | { results: PlanOffer[] };
        const list = Array.isArray(d) ? d : (d?.results ?? []);
        setOffers(list);
        // По умолчанию — первый период тарифа (самый короткий).
        const initial: Record<string, string> = {};
        list.forEach((o) => { if (!initial[o.plan_code]) initial[o.plan_code] = o.code; });
        setChosen(initial);
      }),
    ]).finally(() => setLoading(false));
  }, []);

  const handleRedeem = async () => {
    const code = promo.trim();
    if (!code) return;
    setPromoBusy(true); setPromoMsg(null);
    try {
      const { data } = await subscriptionsApi.redeemPromo(code);
      setCurrent(data);
      setPromo('');
      const until = data.expires_at ? new Date(data.expires_at).toLocaleDateString('ru') : '';
      setPromoMsg({ ok: true, text: `Промокод активирован. Премиум действует до ${until}.` });
    } catch (e) {
      setPromoMsg({ ok: false, text: getErrorMessage(e) || 'Не удалось активировать промокод.' });
    } finally {
      setPromoBusy(false);
    }
  };

  const handleSubscribe = async (offer: PlanOffer) => {
    setSubscribing(offer.plan_code);
    try {
      const returnUrl = window.location.origin + '/subscriptions';
      const { data } = await subscriptionsApi.subscribe(offer.code, returnUrl);
      // Идентификатор известен только сейчас — в return_url его не подставить.
      rememberPayment(data.payment_id);
      window.location.href = data.payment_url;
    } catch (e) { alert(getErrorMessage(e)); }
    finally { setSubscribing(null); }
  };

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-chocolate">Подписка</h1>

      {payMsg && (
        <div className={`rounded-xl px-4 py-3 text-sm ${payMsg.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {payMsg.text}
        </div>
      )}

      {current && (
        <Card className="p-5 border-2 border-avocado/30 bg-green-50/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Активный тариф</p>
              <p className="text-xl font-bold text-chocolate mt-0.5">{current.plan.name}</p>
              <p className="text-sm text-gray-500 mt-1">
                Действует до {new Date(current.expires_at).toLocaleDateString('ru')}
              </p>
            </div>
            <Badge color="green">Активна</Badge>
          </div>
        </Card>
      )}

      <Card className="p-5">
        <p className="text-sm font-semibold text-chocolate">У вас есть промокод?</p>
        <p className="text-xs text-gray-500 mt-0.5 mb-3">
          Введите промокод, чтобы подключить премиум.
        </p>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            value={promo}
            onChange={(e) => setPromo(e.target.value.toUpperCase())}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRedeem(); }}
            placeholder="Например, ABCD-EFGH-JKLM"
            className="flex-1 px-3 py-2 rounded-lg border border-gray-300 uppercase tracking-wide
                       focus:outline-none focus:border-tomato"
          />
          <Button onClick={handleRedeem} loading={promoBusy} disabled={!promo.trim()}>
            Активировать
          </Button>
        </div>
        {promoMsg && (
          <p className={`text-sm mt-2 ${promoMsg.ok ? 'text-avocado' : 'text-red-600'}`}>
            {promoMsg.text}
          </p>
        )}
      </Card>

      {plans.length === 0 ? (
        <p className="text-gray-400 text-sm">Тарифы недоступны.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {plans.map((plan) => {
            const isCurrent = current?.plan.code === plan.code;
            // MG_PAYPERIOD: периоды этого тарифа и выбранный.
            const planOffers = offers.filter((o) => o.plan_code === plan.code);
            const offer = planOffers.find((o) => o.code === chosen[plan.code]) ?? planOffers[0];
            const priceNote = offer ? offerPriceNote(offer) : null;
            return (
              <Card key={plan.id}
                className={['p-5 flex flex-col', isCurrent ? 'border-2 border-tomato' : ''].join(' ')}>
                {isCurrent && (
                  <div className="text-xs text-tomato font-semibold mb-2">✓ ТЕКУЩИЙ ТАРИФ</div>
                )}
                <h3 className="font-bold text-chocolate text-lg">{plan.name}</h3>
                <div className="mt-1 mb-4">
                  <span className="text-3xl font-bold text-tomato">
                    {plan.price === '0.00'
                      ? 'Free'
                      : `${Math.round(Number(offer ? offer.price : plan.price))} ₽`}
                  </span>
                  {plan.price !== '0.00' && (
                    <span className="text-gray-400 text-sm ml-1">
                      / {offer ? offer.title.toLowerCase() : (plan.period === 'month' ? 'мес' : 'год')}
                    </span>
                  )}
                  {priceNote && (
                    <div className="text-xs text-gray-400 mt-0.5">{priceNote}</div>
                  )}
                </div>
                {planOffers.length > 1 && (
                  <PeriodPicker
                    offers={planOffers}
                    value={offer?.code ?? ''}
                    onChange={(code) => setChosen((prev) => ({ ...prev, [plan.code]: code }))}
                  />
                )}
                <ul className="space-y-1 text-sm text-gray-600 flex-1">
                  <li>👥 До {plan.max_family_members} участника</li>
                  <li>🍽 {(plan.features as any)?.menu_generations_per_month
                    ? `${(plan.features as any).menu_generations_per_month} генераций меню/мес`
                    : 'Генерация меню без лимита'}</li>
                  {(plan.features as any)?.country && <li>🌍 Фильтр по стране</li>}
                  {(plan.features as any)?.calories && <li>🔥 Учёт калорийности</li>}
                  {(plan.features as any)?.fridge && <li>🧊 Холодильник</li>}
                  {(plan.features as any)?.allergies_family && <li>⚕️ Аллергии семьи</li>}
                </ul>
                <div className="mt-4">
                  {plan.price === '0.00' ? (
                    <Button variant="secondary" className="w-full" disabled>Бесплатно</Button>
                  ) : !offer ? (
                    <Button variant="ghost" className="w-full" disabled>Оплата недоступна</Button>
                  ) : (
                    /* Текущий тариф тоже можно оплатить — это продление, и срок
                       прибавляется к остатку, а не начинается заново. */
                    <Button className="w-full" loading={subscribing === plan.code}
                      onClick={() => handleSubscribe(offer)}>
                      {isCurrent ? 'Продлить' : 'Подключить'}
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
