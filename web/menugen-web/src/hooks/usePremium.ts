import { useAppSelector } from './useAppDispatch';

// Страницы, доступные только при активном Premium (free туда не пускаем
// и не грузим — иначе backend отдаёт 403). Должно совпадать с premium-гейтом
// бэкенда: fridge (+ dashboard построен на premium-дневнике).
// freemium: /diary открыт free-юзерам (ручное ведение дневника + квота).
export const PREMIUM_PATHS = ['/dashboard', '/fridge'];

/** Активна ли Premium-подписка у текущего пользователя. */
export const useIsPremium = (): boolean =>
  useAppSelector((s) => !!s.auth.user?.subscription_status?.is_active_premium);
