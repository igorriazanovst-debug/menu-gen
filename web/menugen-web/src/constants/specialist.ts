// MG_SPECACCESS: типы специалистов и права ролей на стороне интерфейса.
//
// Названия и разделы раньше были выписаны в каждой странице кабинета отдельно —
// поэтому «повар» пришлось бы добавлять в трёх местах и где-нибудь забыть.
//
// Уровни доступа приходят с сервера в профиле специалиста (`permissions`):
// таблица живёт в apps/specialists/access.py и здесь не дублируется. Интерфейс
// по ней решает, что показывать, но решение всё равно за сервером — спрятанная
// кнопка защитой не является.

export type SpecialistType = 'dietitian' | 'trainer' | 'cook';

export type AccessSection = 'profile' | 'diary' | 'menu' | 'fridge' | 'shopping';

export type AccessLevel = 'none' | 'read' | 'write';

export type SpecialistPermissions = Record<AccessSection, AccessLevel>;

export const SPECIALIST_TYPE_LABELS: Record<SpecialistType, string> = {
  dietitian: 'Диетолог (нутрициолог)',
  trainer: 'Фитнес-тренер',
  cook: 'Личный повар',
};

export const SPECIALIST_TYPES: SpecialistType[] = ['dietitian', 'trainer', 'cook'];

export const SECTION_LABELS: Record<AccessSection, string> = {
  profile: 'Профиль и коридор калорий',
  diary: 'Дневник питания',
  menu: 'Меню',
  fridge: 'Холодильник',
  shopping: 'Списки покупок',
};

export const LEVEL_LABELS: Record<AccessLevel, string> = {
  none: 'нет доступа',
  read: 'чтение',
  write: 'правка',
};

export const specialistTypeLabel = (type?: string | null): string =>
  SPECIALIST_TYPE_LABELS[(type ?? '') as SpecialistType] ?? 'Специалист';

/** Может ли специалист открыть раздел. */
export const canRead = (perms: SpecialistPermissions | undefined, section: AccessSection): boolean =>
  perms?.[section] === 'read' || perms?.[section] === 'write';

/** Может ли специалист менять данные раздела. */
export const canWrite = (perms: SpecialistPermissions | undefined, section: AccessSection): boolean =>
  perms?.[section] === 'write';
