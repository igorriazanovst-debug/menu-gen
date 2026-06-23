import { useAppSelector } from './useAppDispatch';

// Страницы, доступные только при активном Premium (free туда не пускаем
// и не грузим — иначе backend отдаёт 403). Должно совпадать с premium-гейтом
// бэкенда: diary / fridge (+ dashboard построен на premium-дневнике).
export const PREMIUM_PATHS = ['/dashboard', '/diary', '/fridge'];

/** Активна ли Premium-подписка у текущего пользователя. */
export const useIsPremium = (): boolean =>
  useAppSelector((s) => !!s.auth.user?.subscription_status?.is_active_premium);
