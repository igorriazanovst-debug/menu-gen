// MG_VERIFYDEEPLINK: возврат в приложение после подтверждения e-mail.
//
// Ссылка из письма ведёт на веб-страницу — иначе её не открыть на компьютере.
// На телефоне это раздражало: человек регистрировался в приложении, а
// оказывался в мобильном вебе. Страница после успеха предлагает вернуться.
//
// Токен в схему не кладём: любое приложение может зарегистрировать ту же схему
// и перехватить ссылку. Токен гасит эта страница, приложению достаётся только
// адрес — чтобы подставить его в форму входа.

export const APP_SCHEME = 'menugen';

/** Ссылка «открыть приложение на экране входа, e-mail подтверждён». */
export function verifiedAppLink(email?: string | null): string {
  const base = `${APP_SCHEME}://verified`;
  return email ? `${base}?email=${encodeURIComponent(email)}` : base;
}

/**
 * Есть ли смысл предлагать приложение. Оно только под Android, поэтому всем
 * остальным (включая iOS) предложение не показываем — вести некуда.
 */
export function canOpenApp(userAgent: string = navigator.userAgent): boolean {
  return /android/i.test(userAgent);
}
