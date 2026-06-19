// MG_SKIN: реестр скинов оформления + утилиты применения/хранения.

export type Skin = 'main' | 'second';

export const SKINS: Skin[] = ['main', 'second'];

export const SKIN_LABELS: Record<Skin, string> = {
  main: 'Основная',
  second: 'Альтернативная',
};

export const DEFAULT_SKIN: Skin = 'main';

const STORAGE_KEY = 'ui_skin';

export function isSkin(v: unknown): v is Skin {
  return v === 'main' || v === 'second';
}

/** Скин из localStorage (для мгновенного применения до загрузки профиля). */
export function getStoredSkin(): Skin {
  return isSkin(localStorage.getItem(STORAGE_KEY))
    ? (localStorage.getItem(STORAGE_KEY) as Skin)
    : DEFAULT_SKIN;
}

export function storeSkin(skin: Skin): void {
  localStorage.setItem(STORAGE_KEY, skin);
}

/** Проставляет data-skin на <html> — переключает CSS-переменные. */
export function applySkin(skin: Skin): void {
  document.documentElement.setAttribute('data-skin', skin);
}
