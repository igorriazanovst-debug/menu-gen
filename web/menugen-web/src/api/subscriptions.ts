import client from './client';
import type { Subscription, SubscriptionPlan } from '../types';

export const subscriptionsApi = {
  plans: () => client.get<SubscriptionPlan[]>('/subscriptions/plans/'),
  current: () => client.get<Subscription>('/subscriptions/current/'),
  subscribe: (plan_code: string, return_url: string) =>
    client.post<{ payment_url: string; payment_id: string }>(
      '/subscriptions/subscribe/', { plan_code, return_url }
    ),
  cancel: () => client.post('/subscriptions/cancel/'),
};
