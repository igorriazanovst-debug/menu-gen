import React, { useEffect, useState } from 'react';
import { subscriptionsApi } from '../../api/subscriptions';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { PageSpinner } from '../../components/ui/Spinner';
import { getErrorMessage } from '../../utils/api';
import type { SubscriptionPlan, Subscription } from '../../types';

export const SubscriptionsPage: React.FC = () => {
  const [plans, setPlans]     = useState<SubscriptionPlan[]>([]);
  const [current, setCurrent] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState<string | null>(null);

  useEffect(() => {
    Promise.allSettled([
      subscriptionsApi.plans().then((r) => setPlans(r.data)),
      subscriptionsApi.current().then((r) => setCurrent(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  const handleSubscribe = async (plan: SubscriptionPlan) => {
    setSubscribing(plan.code);
    try {
      const returnUrl = window.location.origin + '/subscriptions?status=success';
      const { data } = await subscriptionsApi.subscribe(plan.code, returnUrl);
      window.location.href = data.payment_url;
    } catch (e) { alert(getErrorMessage(e)); }
    finally { setSubscribing(null); }
  };

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-chocolate">Подписка</h1>

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

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {plans.map((plan) => {
          const isCurrent = current?.plan.code === plan.code;
          return (
            <Card key={plan.id}
              className={['p-5 flex flex-col', isCurrent ? 'border-2 border-tomato' : ''].join(' ')}>
              {isCurrent && (
                <div className="text-xs text-tomato font-semibold mb-2">✓ ТЕКУЩИЙ ТАРИФ</div>
              )}
              <h3 className="font-bold text-chocolate text-lg">{plan.name}</h3>
              <div className="mt-1 mb-4">
                <span className="text-3xl font-bold text-tomato">
                  {plan.price === '0.00' ? 'Free' : `${parseInt(plan.price)} ₽`}
                </span>
                {plan.price !== '0.00' && (
                  <span className="text-gray-400 text-sm ml-1">/ {plan.period === 'month' ? 'мес' : 'год'}</span>
                )}
              </div>
              <ul className="space-y-1 text-sm text-gray-600 flex-1">
                <li>👥 До {plan.max_family_members} участника</li>
                {(plan.features as any).country && <li>🌍 Фильтр по стране</li>}
                {(plan.features as any).calories && <li>🔥 Учёт калорийности</li>}
                {(plan.features as any).fridge && <li>🧊 Холодильник</li>}
                {(plan.features as any).allergies_family && <li>⚕️ Аллергии семьи</li>}
              </ul>
              <div className="mt-4">
                {isCurrent ? (
                  <Button variant="ghost" className="w-full" disabled>Текущий</Button>
                ) : plan.price === '0.00' ? (
                  <Button variant="secondary" className="w-full" disabled>Бесплатно</Button>
                ) : (
                  <Button className="w-full" loading={subscribing === plan.code}
                    onClick={() => handleSubscribe(plan)}>
                    Подключить
                  </Button>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
