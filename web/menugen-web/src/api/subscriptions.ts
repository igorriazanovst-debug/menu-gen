import client from './client';
import type { PaymentStatus, PlanOffer, Subscription, SubscriptionPlan } from '../types';

export const subscriptionsApi = {
  plans: () => client.get<SubscriptionPlan[]>('/subscriptions/plans/'),
  // MG_PAYPERIOD: периоды и цены — из чего выбирает пользователь.
  offers: () => client.get<PlanOffer[] | { results: PlanOffer[] }>('/subscriptions/offers/'),
  current: () => client.get<Subscription>('/subscriptions/current/'),
  subscribe: (offer_code: string, return_url: string) =>
    client.post<{ payment_url: string; payment_id: string }>(
      '/subscriptions/subscribe/', { offer_code, return_url }
    ),
  // MG_PAYRELIABLE: уведомление от ЮKassa может опоздать — спрашиваем сами.
  paymentStatus: (paymentId: string) =>
    client.get<PaymentStatus>(`/payments/${encodeURIComponent(paymentId)}/status/`),
  cancel: () => client.post('/subscriptions/cancel/'),
  // Активация промокода: выдаёт/продлевает премиум семье пользователя.
  redeemPromo: (code: string) =>
    client.post<Subscription & { detail?: string }>('/subscriptions/promo/redeem/', { code }),
};
